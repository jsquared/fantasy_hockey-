import os
import json
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
GAME_CODE = "nhl"
LEAGUE_ID = "465.l.33140"  # replace with your league ID
OUTPUT_FILE = "docs/roster_stats.json"

# =========================
# OAUTH
# =========================
oauth = OAuth2(None, None, from_file="oauth2.json")

# =========================
# YAHOO OBJECTS
# =========================
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

# Get all teams in the league
teams = league.teams()

# =========================
# DATA COLLECTION
# =========================
roster_stats = {}

for team_key, team_info in teams.items():
    team_name = team_info['name']
    roster_stats[team_name] = []

    team_obj = league.to_team(team_key)
    roster = team_obj.roster()  # This gives list of players

    player_ids = [p['player_id'] for p in roster]
    if not player_ids:
        continue

    # Pull season stats for all players on the team
    stats_list = league.player_stats(player_ids, req_type='season')

    # Combine player info with stats
    for player, stats in zip(roster, stats_list):
        player_data = {
            "player_id": player["player_id"],
            "name": player["name"]["full"],
            "positions": player.get("eligible_positions", []),
            "status": player.get("status", ""),
            "team": player.get("editorial_team_full_name", ""),
            "season_stats": stats
        }
        roster_stats[team_name].append(player_data)

# =========================
# SAVE OUTPUT
# =========================
os.makedirs("docs", exist_ok=True)
with open(OUTPUT_FILE, "w") as f:
    json.dump(roster_stats, f, indent=2)

print(f"{OUTPUT_FILE} updated with roster and season stats for all teams.")
