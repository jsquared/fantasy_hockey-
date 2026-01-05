import json
import os
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

GAME_CODE = "nhl"
LEAGUE_ID = "465.l.33140"

# OAuth bootstrap (CI-safe)
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

team_key = league.team_key()

# Fetch raw roster + stats from Yahoo NHL API
raw = league.yhandler.get(
    f"team/{team_key}/roster/players/stats;type=season"
)

# Make sure docs folder exists
os.makedirs("docs", exist_ok=True)

# Dump the raw API output to JSON for inspection
with open("docs/roster.json", "w") as f:
    json.dump(raw, f, indent=2)

print("✅ docs/roster.json written successfully")
