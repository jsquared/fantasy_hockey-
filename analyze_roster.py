import json
import os
from datetime import datetime, timezone
from collections import defaultdict
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"
WEEKS = 12  # Number of weeks to analyze
SWING_THRESHOLD = 0.10  # 10%

# =========================
# STAT MAP
# =========================
STAT_MAP = {
    "1": "Goals",
    "2": "Assists",
    "4": "+/-",
    "5": "PIM",
    "8": "PPP",
    "11": "SHP",
    "12": "GWG",
    "14": "SOG",
    "16": "FW",
    "31": "Hits",
    "32": "Blocks",
    "19": "Wins",
    "22": "GA",
    "23": "GAA",
    "24": "Shots Against",
    "25": "Saves",
    "26": "SV%",
    "27": "Shutouts"
}

LOWER_IS_BETTER = {"GA", "GAA", "Shots Against"}

# =========================
# OAuth
# =========================
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

# =========================
# Yahoo League Objects
# =========================
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

my_team_key = league.team_key()
current_week = league.current_week()
teams_meta = league.teams()  # This returns dicts, not Team objects

# =========================
# Helpers
# =========================
def normalize(value, min_v, max_v):
    if max_v == min_v:
        return 0.5
    return (value - min_v) / (max_v - min_v)

# =========================
# COLLECT PLAYER ROSTER & STATS
# =========================
my_team_obj = league.to_team(my_team_key)  # ✅ proper Team object

roster_data = []

for player in my_team_obj.roster():  # returns list of dicts
    pid = player["player_id"]
    name = player["name"]["full"]
    pos = player["selected_position"]
    stats = {}
    for s in player.get("player_stats", {}).get("stats", []):
        sid = str(s["stat"]["stat_id"])
        stats[sid] = float(s["value"]) if s["value"] not in (None, "") else None

    roster_data.append({
        "player_id": pid,
        "name": name,
        "position": pos,
        "stats": stats
    })

# =========================
# CALCULATE WEEKLY AVERAGES + TRENDS
# =========================
weekly_stats = defaultdict(dict)
weekly_ranks = defaultdict(dict)

for week in range(1, WEEKS + 1):
    raw = league.yhandler.get_scoreboard_raw(league.league_id, week)
    matchups = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

    for _, matchup_block in matchups.items():
        if _ == "count":
            continue

        teams_block = matchup_block["matchup"]["0"]["teams"]
        for _, team_entry in teams_block.items():
            if _ == "count":
                continue

            team_block = team_entry["team"]
            team_key = team_block[0][0]["team_key"]
            stats = {}
            for item in team_block[1]["team_stats"]["stats"]:
                sid = str(item["stat"]["stat_id"])
                val = item["stat"]["value"]
                try:
                    stats[sid] = float(val)
                except (TypeError, ValueError):
                    stats[sid] = None
            weekly_stats[week][team_key] = stats

    # Weekly ranking
    for stat_id, stat_name in STAT_MAP.items():
        values = {t: s.get(stat_id) for t, s in weekly_stats[week].items() if s.get(stat_id) is not None}
        reverse = stat_name not in LOWER_IS_BETTER
        ranked = sorted(values.items(), key=lambda x: x[1], reverse=reverse)
        for rank, (team_key, _) in enumerate(ranked, start=1):
            weekly_ranks[week].setdefault(team_key, {})[stat_name] = rank

# Compute average stats and trends
avg_stats = defaultdict(dict)
avg_ranks = defaultdict(dict)
trends = defaultdict(dict)

for team_key in teams_meta.keys():
    for stat_id, stat_name in STAT_MAP.items():
        values, ranks = [], []
        for week in range(1, WEEKS + 1):
            v = weekly_stats[week].get(team_key, {}).get(stat_id)
            r = weekly_ranks[week].get(team_key, {}).get(stat_name)
            if v is not None:
                values.append(v)
            if r is not None:
                ranks.append(r)

        avg_stats[team_key][stat_name] = sum(values) / len(values) if values else None
        avg_ranks[team_key][stat_name] = sum(ranks) / len(ranks) if ranks else None

        # Trend calculation
        if len(values) >= 6:
            recent = sum(values[-3:]) / 3
            earlier = sum(values[:-3]) / (len(values) - 3)
            trends[team_key][stat_name] = recent - earlier
        else:
            trends[team_key][stat_name] = 0

# =========================
# WRITE OUTPUT
# =========================
output = {
    "league": league.settings()["name"],
    "current_week": current_week,
    "weeks_analyzed": WEEKS,
    "my_team": my_team_key,
    "roster": roster_data,
    "weekly_stats": weekly_stats,
    "weekly_ranks": weekly_ranks,
    "average_stats": avg_stats,
    "average_ranks": avg_ranks,
    "trends": trends,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(output, f, indent=2)

print("✅ docs/roster.json updated with full player stats and trends")
