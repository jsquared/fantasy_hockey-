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
    # Skater stats
    "1": "Goals", "2": "Assists", "4": "+/-", "5": "PIM", "8": "PPP",
    "11": "SHP", "12": "GWG", "14": "SOG", "16": "FW", "31": "Hit", "32": "Blk",
    # Goalie stats
    "19": "Wins", "22": "GA", "23": "GAA", "24": "Shots Against", 
    "25": "Saves", "26": "SV%", "27": "Shutouts"
}

SKATER_STATS = {"1","2","4","5","8","11","12","14","16","31","32"}
GOALIE_STATS = {"19","22","23","24","25","26","27"}

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
# Rank each stat vs league
# =========================
ranked_stats = []

for stat_id, my_value in my_stats.items():
    try:
        my_val_num = float(my_value)
    except (TypeError, ValueError):
        continue

    # All numeric values for this stat across league
    league_values = []
    for team_data in league_stats.values():
        val = team_data["stats"].get(stat_id)
        try:
            league_values.append(float(val))
        except (TypeError, ValueError):
            continue
    if not league_values:
        continue

    # Determine rank
    if stat_id in ["22","23","24"]:  # negative stats → lower is better
        league_values_sorted = sorted(league_values)
    else:
        league_values_sorted = sorted(league_values, reverse=True)

    try:
        rank = league_values_sorted.index(my_val_num) + 1
    except ValueError:
        rank = None  # in case of missing data

    ranked_stats.append({
        "stat_id": stat_id,
        "name": STAT_MAP.get(stat_id, f"Stat {stat_id}"),
        "value": my_val_num,
        "rank": rank,
        "total_teams": len(league_values)
    })

# =========================
# Save everything to JSON
# =========================
payload = {
    "league": league.settings().get("name", "Unknown League"),
    "week": WEEK,
    "my_team_key": my_team_key,
    "team_name": league_stats[my_team_key]["team_name"],
    "all_team_stats": league_stats,
    "ranked_stats": ranked_stats,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/team_analysis.json updated")
