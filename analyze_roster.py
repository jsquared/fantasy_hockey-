import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# ------------------ CONFIG ------------------
GAME_CODE = "nhl"
LEAGUE_ID = "465.l.33140"
ROSTER_FILE = "docs/roster.json"

# ------------------ OAUTH ------------------
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

# ------------------ FETCH ALL TEAMS ------------------
teams = league.teams()
all_team_rosters = []

for t in teams:
    t_key = t["team_key"]
    raw_roster = league.roster(t_key)
    roster_output = []
    for player in raw_roster:
        pid = int(player["player_id"])
        name = player.get("name")
        pos = player.get("selected_position")
        stats = player.get("stats", {})
        roster_output.append({
            "player_id": pid,
            "name": name,
            "selected_position": pos,
            "stats": stats
        })
    all_team_rosters.append({"team_key": t_key, "roster": roster_output})

# ------------------ TRADE RECOMMENDATION ------------------
def recommend_trades(my_team_key, all_teams):
    my_team = next(team for team in all_teams if team["team_key"] == my_team_key)
    trades = []

    # Flatten other teams
    other_players = [
        p for team in all_teams if team["team_key"] != my_team_key
        for p in team["roster"]
    ]

    for my_player in my_team["roster"]:
        momentum = my_player["stats"].get("momentum_score", 0)
        if momentum <= 0:  # cold player
            pos = my_player["selected_position"]
            # Candidate hot players in same position
            candidates = [
                p for p in other_players
                if p["selected_position"] == pos and p["stats"].get("momentum_score", 0) > 0
            ]
            # Sort by closest improvement
            candidates.sort(key=lambda x: abs(x["stats"].get("momentum_score", 0) - abs(momentum)))
            if candidates:
                trades.append({
                    "give": my_player["name"],
                    "get": candidates[0]["name"],
                    "pos": pos,
                    "momentum_diff": round(candidates[0]["stats"].get("momentum_score", 0) - momentum, 3)
                })
    return trades

my_team_key = league.team_key()
trade_suggestions = recommend_trades(my_team_key, all_team_rosters)

# ------------------ UPDATE ROSTER.JSON ------------------
if os.path.exists(ROSTER_FILE):
    with open(ROSTER_FILE, "r") as f:
        roster_data = json.load(f)
else:
    roster_data = {}

roster_data["trade_recommendations"] = {
    "generated": datetime.now(timezone.utc).isoformat(),
    "team_key": my_team_key,
    "recommendations": trade_suggestions
}

# Overwrite roster.json with added trade recommendations
with open(ROSTER_FILE, "w") as f:
    json.dump(roster_data, f, indent=2)

print(f"✅ {ROSTER_FILE} updated with {len(trade_suggestions)} trade recommendations")
