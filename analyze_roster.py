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

current_week = league.current_week()

# =========================
# Fetch raw league scoreboard
# =========================
raw = league.yhandler.get_scoreboard_raw(league.league_id, current_week)
matchups = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

# =========================
# Extract all team rosters
# =========================
all_teams = {}

for _, matchup_block in matchups.items():
    if _ == "count":
        continue

    teams_block = matchup_block["matchup"]["0"]["teams"]
    for tk, tv in teams_block.items():
        if tk == "count":
            continue
        team_block = tv["team"]
        team_key = team_block[0][0]["team_key"]
        all_teams[team_key] = team_block

# =========================
# Prepare payload
# =========================
payload = {
    "league": league.settings().get("name", "Unknown League"),
    "week": current_week,
    "teams": all_teams,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

# =========================
# Save to JSON
# =========================
os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json updated with all teams")
