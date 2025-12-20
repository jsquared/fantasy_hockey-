import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# --- LOAD OAUTH FROM GITHUB SECRET ---
raw_oauth = os.environ.get("YAHOO_OAUTH_JSON")
if not raw_oauth:
    raise RuntimeError("YAHOO_OAUTH_JSON secret is missing or empty")

oauth_data = json.loads(raw_oauth)

with open("oauth2.json", "w") as f:
    json.dump(oauth_data, f)

oauth = OAuth2(None, None, from_file="oauth2.json")

# --- YAHOO SETUP ---
game = yfa.Game(oauth, "nhl")
league_id = "465.l.33140"
league = game.to_league(league_id)

team_key = league.team_key()
team = league.to_team(team_key)

# --- FETCH MATCHUP ---
current_week = league.current_week()
matchups = team.matchup(week=current_week)

if not isinstance(matchups, dict):
    raise RuntimeError(f"Unexpected matchup type: {type(matchups)}")

matchup = None
for key, value in matchups.items():
    if key == "count":
        continue
    matchup = value.get("matchup")
    break

if not matchup:
    raise RuntimeError("No matchup data found")

teams = matchup.get("teams", [])
if len(teams) != 2:
    raise RuntimeError(f"Expected 2 teams, got {len(teams)}")

my_team = next(t for t in teams if t["team_key"] == team_key)
opp_team = next(t for t in teams if t["team_key"] != team_key)

# --- SCORES ---
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
