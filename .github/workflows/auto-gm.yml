import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# --- LOAD OAUTH FROM GITHUB SECRET ---
oauth_data = json.loads(os.environ["YAHOO_OAUTH_JSON"])
with open("oauth2.json", "w") as f:
    json.dump(oauth_data, f)

oauth = OAuth2(None, None, from_file="oauth2.json")

# --- YAHOO SETUP ---
game = yfa.Game(oauth, "nhl")
league_id = "465.l.33140"
league = game.to_league(league_id)

team_key = league.team_key()
team = league.to_team(team_key)

current_week = league.current_week()
matchup = team.matchup(week=current_week)

teams = matchup["teams"]
my_team = next(t for t in teams if t["team_key"] == team_key)
opp_team = next(t for t in teams if t["team_key"] != team_key)

my_score = float(my_team["team_points"]["total"])
opp_score = float(opp_team["team_points"]["total"])

status = matchup.get("status", "UNKNOWN").upper()

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

print("scores.json updated")
