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

# =========================
# TEAMS (IMPORTANT FIX)
# league.teams() RETURNS A DICT
# =========================
teams_raw = league.teams()

teams = {}
for t in teams_raw.values():
    teams[t["team_key"]] = {
        "team_id": t["team_id"],
        "name": t["name"]
    }

# =========================
# ROSTERS
# =========================
rosters = {}

for team_key in teams.keys():
    team = yfa.Team(oauth, team_key)
    roster = team.roster()

    players = []

    for p in roster:
        players.append({
            "player_id": p.get("player_id"),
            "name": p.get("name"),
            "position": p.get("display_position"),
            "eligible_positions": p.get("eligible_positions"),
            "editorial_team": p.get("editorial_team_abbr"),
            "status": p.get("status")
        })

    rosters[team_key] = players

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings().get("name"),
    "league_id": LEAGUE_ID,
    "generated": datetime.now(timezone.utc).isoformat(),
    "teams": teams,
    "rosters": rosters
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated")
