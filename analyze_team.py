import json
import os
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"

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

team_key = league.team_key()  # Your team key
week = 1  # Week to inspect

# =========================
# Fetch scoreboard
# =========================
raw_scoreboard = league.yhandler.get_scoreboard_raw(league.league_id, week)
league_data = raw_scoreboard["fantasy_content"]["league"][1]
matchups = league_data["scoreboard"]["0"]["matchups"]

# =========================
# Find only my team
# =========================
my_team_data = None

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
        if meta[0]["team_key"] == team_key:
            my_team_data = team_block[1]  # This contains stats, points, etc.
            break
    if my_team_data:
        break

if not my_team_data:
    raise RuntimeError("❌ Could not find your team data for week 1")

# =========================
# Dump to JSON
# =========================
os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(my_team_data, f, indent=2)

print("✅ My team data for week 1 dumped to docs/team_analysis.json")
