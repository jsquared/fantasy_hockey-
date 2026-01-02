import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
from collections import defaultdict

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
current_week = int(league.current_week())

# IMPORTANT: league.teams() RETURNS RAW METADATA (DICT)
teams_meta = league.teams()

# Safe team name map (THIS IS THE FIX)
teams = {
    team_key: team_data["name"]
    for team_key, team_data in teams_meta.items()
}

# =========================
# Helpers
# =========================
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

def normalize(value, min_v, max_v):
    if max_v == min_v:
        return 0.5
    return (value - min_v) / (max_v - min_v)

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

for team_key in teams.keys():
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

        avg_stats[team_key][stat_name] = sum(values) / len(values) if values else None
        avg_ranks[team_key][stat_name] = sum(ranks) / len(ranks) if ranks else None

        # Trend: last 3 weeks vs prior
        if len(values) >= 6:
            recent = sum(values[-3:]) / 3
            earlier = sum(values[:-3]) / (len(values) - 3)
            trends[team_key][stat_name] = round(recent - earlier, 3)
        else:
            trends[team_key][stat_name] = 0

# =========================
# CURRENT MATCHUP
# =========================
raw = league.yhandler.get_scoreboard_raw(league.league_id, current_week)
matchups = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

opp_key = None
for _, matchup in matchups.items():
    if _ == "count":
        continue

    teams_block = matchup["matchup"]["0"]["teams"]
    keys = [
        team_entry["team"][0][0]["team_key"]
        for tk, team_entry in teams_block.items()
        if tk != "count"
    ]

    if my_team_key in keys:
        opp_key = next(k for k in keys if k != my_team_key)
        break

# =========================
# CATEGORY PREDICTIONS
# =========================
predictions = {}

for stat_name in STAT_MAP.values():
    my_val = avg_stats[my_team_key].get(stat_name)
    opp_val = avg_stats[opp_key].get(stat_name)

    my_rank = avg_ranks[my_team_key].get(stat_name)
    opp_rank = avg_ranks[opp_key].get(stat_name)

    if None in (my_val, opp_val, my_rank, opp_rank):
        continue

    vals = [
        avg_stats[t][stat_name]
        for t in avg_stats
        if avg_stats[t][stat_name] is not None
    ]

    min_v, max_v = min(vals), max(vals)

    my_score = normalize(my_val, min_v, max_v) + (1 / my_rank)
    opp_score = normalize(opp_val, min_v, max_v) + (1 / opp_rank)

    diff = my_score - opp_score
    confidence = abs(diff) / max(my_score, opp_score)

    predictions[stat_name] = {
        "winner": "me" if diff > 0 else "opponent",
        "confidence": round(confidence, 3),
        "swing": confidence < SWING_THRESHOLD,
        "trend": trends[my_team_key].get(stat_name, 0)
    }

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "weeks_analyzed": WEEKS,
    "current_week": current_week,
    "my_team": my_team_key,
    "my_team_name": teams.get(my_team_key),
    "opponent": opp_key,
    "opponent_name": teams.get(opp_key),
    "teams": teams,
    "average_stats": avg_stats,
    "average_ranks": avg_ranks,
    "trends": trends,
    "predictions": predictions,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/team_analysis.json updated successfully")
