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
TOP_N = 8
BOTTOM_N = 5

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

team_key = league.team_key()
current_week = league.current_week()

# =========================
# STAT ID → NAME MAP (SAFE)
# =========================
stat_map = {}

try:
    settings = league.settings()
    for s in settings.get("stat_categories", []):
        stat_map[str(s["stat_id"])] = s["name"]
except Exception:
    pass  # Yahoo sometimes omits this

# =========================
# FETCH SCOREBOARD (KNOWN-GOOD PATH)
# =========================
raw = league.yhandler.get_scoreboard_raw(
    league.league_id, current_week
)

league_data = raw["fantasy_content"]["league"][1]
scoreboard = league_data["scoreboard"]["0"]
matchups = scoreboard["matchups"]

# =========================
# FIND MY TEAM STATS
# =========================
my_stats = None

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

        if meta[0]["team_key"] != team_key:
            continue

        my_stats = team_block[1]["team_stats"]["stats"]
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
    stat = item.get("stat")
    if not stat:
        continue

    stat_id = str(stat.get("stat_id"))
    raw_value = stat.get("value")

    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        continue

    processed.append({
        "stat_id": stat_id,
        "name": stat_map.get(stat_id, f"Stat {stat_id}"),
        "value": value
    })

processed.sort(key=lambda x: x["value"], reverse=True)

strengths = processed[:TOP_N]
weaknesses = list(reversed(processed[-BOTTOM_N:]))

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings().get("name", "Unknown League"),
    "team_key": team_key,
    "week": current_week,
    "strengths": strengths,
    "weaknesses": weaknesses,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(payload, f, indent=2)

print("team_analysis.json updated")
