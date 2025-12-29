import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"
WEEK = 1
TOP_N = 5  # number of top stats to call strengths
BOTTOM_N = 5  # number of bottom stats to call weaknesses

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

# =========================
# Fetch scoreboard raw for the week
# =========================
raw = league.yhandler.get_scoreboard_raw(LEAGUE_ID, WEEK)
league_data = raw["fantasy_content"]["league"][1]
scoreboard = league_data["scoreboard"]["0"]
matchups = scoreboard["matchups"]

# =========================
# Stat ID → Name Map
# =========================
STAT_MAP = {
    "1": "Goals", "2": "Assists", "4": "+/-", "5": "PIM", "8": "PPP",
    "11": "SHP", "12": "GWG", "14": "SOG", "16": "FW", "19": "Wins",
    "22": "GA", "23": "GAA", "24": "Shots Against", "25": "Saves",
    "26": "SV%", "27": "Shutouts", "31": "Hit", "32": "Blk"
}

# =========================
# Collect all team stats
# =========================
league_stats = {}

for k, v in matchups.items():
    if k == "count":
        continue
    matchup = v["matchup"]
    teams = matchup["0"]["teams"]
    for tk, tv in teams.items():
        if tk == "count":
            continue
        team_block = tv["team"]
        meta = team_block[0]
        team_key = meta[0]["team_key"]
        team_name = meta[2]["name"]
        stats_raw = team_block[1]["team_stats"]["stats"]
        stats = {}
        for item in stats_raw:
            stat = item.get("stat")
            if stat is None:
                continue
            stat_id = str(stat.get("stat_id"))
            value_raw = stat.get("value")
            try:
                value = float(value_raw)
            except (TypeError, ValueError):
                value = value_raw
            stats[stat_id] = value
        league_stats[team_key] = {
            "team_name": team_name,
            "stats": stats
        }

# =========================
# Get my stats
# =========================
my_stats = league_stats[my_team_key]["stats"]

# =========================
# Compare against league
# =========================
strengths = []
weaknesses = []

for stat_id, my_value in my_stats.items():
    # Skip if my value is not numeric
    try:
        my_val_num = float(my_value)
    except (TypeError, ValueError):
        continue

    # Get all numeric values for this stat across league
    league_values = []
    for team_data in league_stats.values():
        val = team_data["stats"].get(stat_id)
        try:
            val_num = float(val)
            league_values.append(val_num)
        except (TypeError, ValueError):
            continue

    if not league_values:
        continue

    max_val = max(league_values)
    min_val = min(league_values)

    # For positive stats higher is better, negative stats (like GA, Shots Against) lower is better
    if stat_id in ["22", "23", "24"]:  # GA, GAA, Shots Against -> lower better
        if my_val_num == min_val:
            strengths.append({"stat_id": stat_id, "name": STAT_MAP.get(stat_id, stat_id), "value": my_val_num})
        if my_val_num == max_val:
            weaknesses.append({"stat_id": stat_id, "name": STAT_MAP.get(stat_id, stat_id), "value": my_val_num})
    else:
        if my_val_num == max_val:
            strengths.append({"stat_id": stat_id, "name": STAT_MAP.get(stat_id, stat_id), "value": my_val_num})
        if my_val_num == min_val:
            weaknesses.append({"stat_id": stat_id, "name": STAT_MAP.get(stat_id, stat_id), "value": my_val_num})

# Keep only top/bottom N
strengths = sorted(strengths, key=lambda x: float(x["value"]), reverse=True)[:TOP_N]
weaknesses = sorted(weaknesses, key=lambda x: float(x["value"]))[:BOTTOM_N]

# =========================
# Save everything to JSON
# =========================
payload = {
    "league": league.settings().get("name", "Unknown League"),
    "week": WEEK,
    "my_team_key": my_team_key,
    "team_name": league_stats[my_team_key]["team_name"],
    "team_points": my_stats.get("points", None),
    "all_team_stats": league_stats,
    "strengths": strengths,
    "weaknesses": weaknesses,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/team_analysis.json updated")
