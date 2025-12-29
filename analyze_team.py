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

current_week = league.current_week()

# =========================
# Fetch raw scoreboard
# =========================
raw_scoreboard = league.yhandler.get_scoreboard_raw(league.league_id, current_week)

# =========================
# Dump full data to team_analysis.json
# =========================
os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(raw_scoreboard, f, indent=2)

print(f"✅ Full raw scoreboard for week {current_week} dumped to docs/team_analysis.json")
