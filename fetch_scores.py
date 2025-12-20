import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# --- LOAD OAUTH ---
raw_oauth = os.environ.get("YAHOO_OAUTH_JSON")
if not raw_oauth:
    raise RuntimeError("YAHOO_OAUTH_JSON secret is missing or empty")

with open("oauth2.json", "w") as f:
    json.dump(json.loads(raw_oauth), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

# --- YAHOO SETUP ---
game = yfa.Game(oauth, "nhl")
league = game.to_league("465.l.33140")

team_key = league.team_key()

# --- SCOREBOARD (SAFE API) ---
current_week = league.current_week()
scoreboard = league.scoreboard(week=current_week)

if not scoreboard:
    raise RuntimeError("No scoreboard data returned")

# Find the matchup that includes your team
matchup = None
for m in scoreboard:
    teams = m.get("teams", [])
    if any(t["team_key"] == team_key for t in teams):
        matchup = m
        break

if not matchup:
    raise RuntimeError("Could not find matchup for your team")

teams = matchup["teams"]

my_team = next(t for t in teams if t["team_key"] == team_key)
opp_team = next(t for t in teams if t["team_key"] != team_key)

my_score = float(my_team["team_points"]["total"])
opp_score = float(opp_team["team_points"]["total"])

status = matchup.get("status", "UNKNOWN").upper()

# --- OUTPUT ---
payload = {
    "league": league.settings()["name"],
    "week": current_week,
    "status": status,
    "myTeam": {
        "name": my_team["name"],
        "score": my_score
    },
    "opponent": {
        "name": opp_team["name"],
        "score": opp_score
    },
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/scores.json", "w") as f:
    json.dump(payload, f, indent=2)

print("scores.json updated successfully")
