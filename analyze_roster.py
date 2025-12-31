import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"  # replace with your league ID
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

my_team_key = league.team_key()
current_week = league.current_week()
teams_meta = league.teams()

# =========================
# Pull rosters and player stats
# =========================
all_players = []

for team_key in teams_meta:
    team_obj = league.to_team(team_key)
    roster = team_obj.roster(week=current_week)  # list of dicts with player_id

    # Extract player IDs
    player_ids = [p["player_id"] for p in roster]

    # Get season stats for all players on this team
    if player_ids:
        stats_list = league.player_stats(player_ids, req_type="season")
    else:
        stats_list = []

    # Merge player info and stats
    for player in roster:
        pid = player["player_id"]
        # Find stats for this player
        player_stats = next((s for s in stats_list if int(s["player_id"]) == int(pid)), {})

        all_players.append({
            "team_key": team_key,
            "player_id": pid,
            "name": player.get("name") if isinstance(player.get("name"), str) else player.get("name", {}).get("full", "Unknown"),
            "positions": player.get("eligible_positions", []),
            "status": player.get("status", ""),
            "team": player.get("editorial_team_full_name", ""),
            "season_stats": player_stats
        })

# =========================
# Save output
# =========================
os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump({
        "league": league.settings().get("name"),
        "current_week": current_week,
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "players": all_players
    }, f, indent=2)

print("docs/roster.json updated with player season stats.")
