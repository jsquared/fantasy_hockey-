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
TOP_N = 8        # how many strengths to show
BOTTOM_N = 5     # how many weaknesses to show

# =========================
# OAuth (GitHub Actions safe)
# =========================
if "YAHOO_OAUTH_JSON" in os.environ:
    oauth_data = json.loads(os.environ["YAHOO_OAUTH_JSON"])
    with open("oauth2.json", "w") as f:
        json.dump(oauth_data, f)

oauth = OAuth2(None, None, from_file="oauth2.json")

# =========================
# Yahoo Objects
# =========================
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

team_key = league.team_key()
current_week = league.current_week()

# =========================
# GLOBAL STAT MAP (bulletproof)
# =========================
stat_map = {}

raw_game = game.yhandler.get_game_raw(GAME_CODE)
stats = raw_game["fantasy_content"]["game"][1]["stat_categories"]["stats"]

for s in stats:
    stat_map[str(s["stat_id"])] = s["name"]

# =========================
# FETCH TEAM STATS (weekly)
# =========================
raw_scoreboard = league.yhandler.get_scoreboard_raw(league.league_id, current_week)
matchups = raw_scoreboard["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

my_stats = None

for _, m in matchups.items():
    if not isinstance(m, dict):
        continue

    teams = m["matchup"]["0"]["teams"]

    for _, t in teams.items():
        if not isinstance(t, dict):
            continue

        team = t["team"]
        meta = team[0]
        stats_block = team[1]["team_stats"]["stats"]

        if meta[0]["team_key"] == team_key:
            my_stats = stats_block
            break

    if my_stats:
        break

if not my_stats:
    raise RuntimeError("Could not find your team stats")

# =========================
# PROCESS STATS
# =========================
processed = []

for item in my_stats:
    stat_id = str(item["stat"]["stat_id"])
    raw_value = item["stat"].get("value")

    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        continue

    processed.append({
        "stat_id": stat_id,
        "name": stat_map.get(stat_id, f"Stat {stat_id}"),
        "value": value
    })

# Sort by value
processed.sort(key=lambda x: x["value"], reverse=True)

strengths = processed[:TOP_N]
weaknesses = list(reversed(processed[-BOTTOM_N:]))

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "team_key": team_key,
    "week": current_week,
    "strengths": strengths,
    "weaknesses": weaknesses,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(payload, f, indent=2)

print("team_analysis.json updated successfully")
