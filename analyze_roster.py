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
teams = league.teams()  # dict keyed by team_key

# =========================
# Pull rosters for all teams
# =========================
league_rosters = {}

for team_key in teams.keys():
    raw_roster = league.yhandler.get_roster_raw(team_key, current_week)
    league_rosters[team_key] = raw_roster

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings().get("name", "Unknown League"),
    "week": current_week,
    "teams": league_rosters,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json updated with FULL league rosters")
