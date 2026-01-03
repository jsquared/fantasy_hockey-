import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
from collections import defaultdict
import itertools

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"
WEEKS = 12
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
# OAuth (GitHub-safe)
# =========================
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

# =========================
# Yahoo Objects
# =========================
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

my_team_key = league.team_key()
current_week = league.current_week()
teams_meta = league.teams()

# =========================
# HELPERS
# =========================
def normalize(value, min_v, max_v):
    if max_v == min_v:
        return 0.5
    return (value - min_v) / (max_v - min_v)

def extract_team_stats(team_block):
    stats = {}
    for item in team_block[1]["team_stats"]["stats"]:
        stat_id = str(item["stat"]["stat_id"])
        raw = item["stat"]["value"]
        try:
            stats[stat_id] = float(raw)
        except (TypeError, ValueError):
            stats[stat_id] = None
    return stats

# =========================
# DATA COLLECTION
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
            weekly_stats[week][team_key] = extract_team_stats(team_block)

    # Weekly ranking
    for stat_id, stat_name in STAT_MAP.items():
        values = {
            t: s.get(stat_id)
            for t, s in weekly_stats[week].items()
            if s.get(stat_id) is not None
        }
        reverse = stat_name not in LOWER_IS_BETTER
        ranked = sorted(values.items(), key=lambda x: x[1], reverse=reverse)
        for rank, (team_key, _) in enumerate(ranked, start=1):
            weekly_ranks[week].setdefault(team_key, {})[stat_name] = rank

# =========================
# AVERAGES + TRENDS
# =========================
avg_stats = defaultdict(dict)
avg_ranks = defaultdict(dict)
trends = defaultdict(dict)

for team_key in teams_meta.keys():
    for stat_id, stat_name in STAT_MAP.items():
        values = []
        ranks = []
        for week in range(1, WEEKS + 1):
            v = weekly_stats[week].get(team_key, {}).get(stat_id)
            r = weekly_ranks[week].get(team_key, {}).get(stat_name)
            if v is not None:
                values.append(v)
            if r is not None:
                ranks.append(r)
        avg_stats[team_key][stat_name] = sum(values)/len(values) if values else None
        avg_ranks[team_key][stat_name] = sum(ranks)/len(ranks) if ranks else None
        if len(values) >= 6:
            recent = sum(values[-3:])/3
            earlier = sum(values[:-3])/(len(values)-3)
            trends[team_key][stat_name] = recent - earlier
        else:
            trends[team_key][stat_name] = 0

# =========================
# COLLECT PLAYER ROSTER & STATS
# =========================
my_team_obj = league.to_team(my_team_key)
roster_data = []

for player in my_team_obj.roster():  # returns list of dicts
    pid = player["player_id"]
    # Handle name being string or dict
    if isinstance(player["name"], dict):
        name = player["name"].get("full", "")
    else:
        name = str(player["name"])
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
# GENERATE TRADE RECOMMENDATIONS (1-for-1, 2-for-1)
# =========================
trade_recs = []

def calc_player_value(player):
    # Average normalized stats
    val = 0
    for sid, stat_name in STAT_MAP.items():
        v = player["stats"].get(sid)
        if v is not None:
            # normalize across league
            league_vals = [avg_stats[t][stat_name] for t in avg_stats if avg_stats[t][stat_name] is not None]
            if league_vals:
                min_v, max_v = min(league_vals), max(league_vals)
                val += normalize(v, min_v, max_v)
    return val

my_values = {p["player_id"]: calc_player_value(p) for p in roster_data}

# Simple 1-for-1 trade logic
for pid_give, pid_get in itertools.product(my_values.keys(), my_values.keys()):
    if pid_give == pid_get:
        continue
    net_gain = my_values[pid_get] - my_values[pid_give]
    if net_gain > 0.05:  # minimal gain threshold
        trade_recs.append({
            "partner": "Any",
            "type": "1-for-1",
            "i_give": pid_give,
            "i_get": pid_get,
            "net_gain": round(net_gain, 3)
        })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "weeks_analyzed": WEEKS,
    "current_week": current_week,
    "my_team": my_team_key,
    "average_stats": avg_stats,
    "average_ranks": avg_ranks,
    "trends": trends,
    "roster": roster_data,
    "trade_recommendations": trade_recs,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with roster and trade recommendations")
