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
# OAuth
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
roster = league.roster(week=league.current_week())[my_team_key]  # Current week roster

# =========================
# PROCESS ROSTER
# =========================
processed_roster = []
for player in roster:
    processed_roster.append({
        "player_name": player["name"],
        "position": player["position"],
        "team": player["editorial_team_abbr"],
        "status": player.get("status", "Active")
    })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings().get("name", "Unknown League"),
    "team_key": my_team_key,
    "week": league.current_week(),
    "roster": processed_roster,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json updated")
