import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"   # your league
GAME_CODE = "nhl"

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
teams = league.teams()  # dict keyed by team_key

# =========================
# Pull rosters and stats
# =========================
league_rosters = {}

for team_key, team_obj in teams.items():
    raw_roster = league.yhandler.get_roster_raw(team_key, current_week)
    roster_block = raw_roster.get("fantasy_content", {}).get("team", [])
    if len(roster_block) < 2:
        continue

    roster_data = roster_block[1].get("roster", {})

    players_list = []

    for slot_key in roster_data:
        slot_value = roster_data[slot_key]

        # Skip if not dict or missing 'players'
        if not isinstance(slot_value, dict) or "players" not in slot_value:
            continue

        players = slot_value["players"]
        # players can be a dict keyed by integers
        for player_index in players:
            player_block = players[player_index]
            if not isinstance(player_block, dict):
                continue

            player_main = player_block.get("player", [])
            if not player_main or not isinstance(player_main, list):
                continue

            main_info = player_main[0]
            player_dict = {
                "player_key": main_info[0].get("player_key"),
                "player_id": main_info[1].get("player_id"),
                "name": main_info[2]["name"]["full"],
                "team": main_info[6].get("editorial_team_full_name"),
                "team_abbr": main_info[7].get("editorial_team_abbr"),
                "primary_position": main_info[12] if len(main_info) > 12 else None,
                "selected_position": None,
                "stats": {}
            }

            # Selected position
            if len(player_main) > 1 and isinstance(player_main[1], list) and len(player_main[1]) > 1:
                sel_block = player_main[1]
                player_dict["selected_position"] = sel_block[1].get("position")

            # Player stats
            stats_block = {}
            if len(main_info) >= 22 and isinstance(main_info[21], dict):
                stats_block = main_info[21].get("player_stats", {})
                for stat_entry in stats_block.get("stats", []):
                    stat_info = stat_entry.get("stat", {})
                    player_dict["stats"][stat_info.get("stat_id")] = stat_info.get("value")

            players_list.append(player_dict)

    league_rosters[team_key] = {
        "team_key": team_key,
        "team_name": team_obj.get("name"),
        "manager": team_obj.get("managers")[0].get("nickname") if team_obj.get("managers") else None,
        "players": players_list
    }

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings().get("name", "Unknown League"),
    "week": current_week,
    "teams": league_rosters,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json updated with all players and stats")
