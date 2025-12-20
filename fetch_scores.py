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
team = league.to_team(team_key)

# --- FETCH MATCHUP ---
current_week = league.current_week()
raw_matchups = team.matchup(week=current_week)

# yahoo_fantasy_api sometimes returns raw JSON text
if isinstance(raw_matchups, str):
    raw_matchups = json.loads(raw_matchups)

# Navigate Yahoo fantasy_content structure
fantasy_content = raw_matchups["fantasy_content"]
team_data = fantasy_content["team"][1]
matchups_data = team_data["matchups"]

matchup = None
for key, value in matchups_data.items():
    if key == "count":
        continue
    matchup = value["matchup"]
    break

if not matchup:
    raise RuntimeError("No matchup found")

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
