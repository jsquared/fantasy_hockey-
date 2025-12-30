import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
GAME_CODE = "nhl"
LEAGUE_ID = "465.l.33140"
PLAYER_KEY = "465.p.8642"  # Quinton Byfield

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
current_week = league.current_week()

# =========================
# Get full roster
# =========================
team_key = "465.l.33140.t.14"  # Grambling
roster_raw = league.yhandler.get_roster_raw(team_key, current_week)
players_block = roster_raw["fantasy_content"]["team"][1]["roster"]

# =========================
# Find Quinton Byfield
# =========================
byfield_stats = {}
byfield_info = None

for slot_key, slot in players_block.items():
    for player_entry in slot["players"].values():
        player_data = player_entry["player"][0]
        selected_pos_block = player_entry["player"][1]
        if player_data[0]["player_key"] == PLAYER_KEY:
            byfield_info = {
                "player_key": PLAYER_KEY,
                "name": player_data[2]["name"]["full"],
                "team": player_data[6]["editorial_team_full_name"],
                "team_abbr": player_data[7]["editorial_team_abbr"],
                "primary_position": player_data[12]["display_position"],
                "selected_position": selected_pos_block[1]["position"]
            }
            # Extract stats if present
            stats_block = player_data[-1].get("player_stats", {})
            if stats_block:
                for stat in stats_block.get("stats", []):
                    byfield_stats[stat["stat"]["stat_id"]] = stat["stat"]["value"]
            byfield_info["stats"] = byfield_stats
            break
    if byfield_info:
        break

# =========================
# Write output
# =========================
payload = {
    "league": league.settings().get("name", "Unknown League"),
    "week": current_week,
    "player": byfield_info,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json updated with Quinton Byfield stats")
