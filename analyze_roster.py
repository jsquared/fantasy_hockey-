import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

GAME_CODE = "nhl"
LEAGUE_ID = "465.l.33140"

# OAuth bootstrap
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)
team_key = league.team_key()

# Fetch raw roster + season stats
raw = league.yhandler.get(f"team/{team_key}/roster/players/stats;type=season")

roster_output = []

# Navigate to the roster block
players_block = raw["fantasy_content"]["team"][1]["roster"]["0"]["players"]

for pid_str, pdata in players_block.items():
    player_data = pdata.get("player")
    if not player_data or not isinstance(player_data, list):
        continue  # skip malformed or placeholder entries

    player_list = player_data[0]  # The actual player data list
    player_stats_block = None

    # Extract stats if present
    for item in player_list:
        if isinstance(item, dict) and "player_stats" in item:
            player_stats_block = item["player_stats"]
            break

    stats = {}
    if player_stats_block:
        for stat_entry in player_stats_block.get("stats", []):
            stat = stat_entry.get("stat", {})
            sid = stat.get("stat_id")
            val = stat.get("value")
            if sid:
                try:
                    stats[str(sid)] = float(val)
                except (TypeError, ValueError):
                    stats[str(sid)] = val

    # Extract basic info
    player_id = None
    player_name = None
    selected_position = None
    editorial_team_abbr = None

    for item in player_list:
        if isinstance(item, dict):
            if "player_id" in item:
                player_id = int(item["player_id"])
            if "name" in item:
                player_name = item["name"].get("full")
            if "editorial_team_abbr" in item:
                editorial_team_abbr = item["editorial_team_abbr"]
            if "display_position" in item:
                selected_position = item["display_position"]

    roster_output.append({
        "player_id": player_id,
        "name": player_name,
        "selected_position": selected_position,
        "editorial_team": editorial_team_abbr,
        "stats": stats
    })

# Write output to JSON
os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump({
        "league": league.settings().get("name"),
        "team_key": team_key,
        "generated": datetime.now(timezone.utc).isoformat(),
        "roster": roster_output
    }, f, indent=2)

print("✅ docs/roster.json written successfully with season stats")
