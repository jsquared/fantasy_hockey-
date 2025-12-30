import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
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

current_week = league.current_week()
teams = league.teams()  # dict keyed by team_key

# =========================
# Pull rosters and stats for all teams
# =========================
league_rosters = {}

for team_key, team_info in teams.items():
    print(f"Pulling roster for {team_key}")
    raw_roster = league.yhandler.get_roster_raw(team_key, current_week)
    roster_dict = {}
    roster_block = raw_roster.get("fantasy_content", {}).get("team", [])

    # extract manager name
    manager_name = None
    for section in roster_block:
        if isinstance(section, dict) and "managers" in section:
            managers_list = section.get("managers", [])
            if managers_list:
                manager_name = managers_list[0].get("manager", {}).get("nickname")
    roster_dict["team_key"] = team_key
    roster_dict["team_name"] = team_info.get("name")
    roster_dict["manager"] = manager_name
    roster_dict["players"] = []

    # iterate roster slots
    for slot_block in roster_block:
        if not isinstance(slot_block, dict):
            continue
        roster_slots = slot_block.get("roster", {}).get("0", {}).get("players", {})
        for player_block in roster_slots.values():
            player_main = player_block.get("player", [])
            if not player_main or not isinstance(player_main, list):
                continue
            main_info = player_main[0]

            # selected position
            selected_position = None
            if len(player_main) > 1:
                try:
                    selected_position = player_main[1][1].get("position")
                except (IndexError, AttributeError):
                    selected_position = None

            # headshot/image
            primary_position_block = main_info[12] if len(main_info) > 12 else {}
            if isinstance(primary_position_block, dict):
                headshot = primary_position_block.get("headshot", {})
                image_url = primary_position_block.get("image_url")
            else:
                headshot = {}
                image_url = None

            # stats
            stats_dict = {}
            if len(main_info) > 21 and isinstance(main_info[21], dict):
                stats_block = main_info[21].get("player_stats", {})
                for stat_entry in stats_block.get("stats", []):
                    stat_info = stat_entry.get("stat", {})
                    stats_dict[stat_info.get("stat_id")] = stat_info.get("value")

            # build player dict
            player_info = {
                "player_key": main_info[0].get("player_key"),
                "player_id": main_info[1].get("player_id"),
                "name": main_info[2]["name"]["full"] if "name" in main_info[2] else None,
                "team": main_info[6].get("editorial_team_full_name"),
                "team_abbr": main_info[7].get("editorial_team_abbr"),
                "primary_position": main_info[12] if len(main_info) > 12 else None,
                "selected_position": selected_position,
                "stats": stats_dict,
                "headshot": headshot,
                "image_url": image_url
            }

            roster_dict["players"].append(player_info)

    league_rosters[team_key] = roster_dict

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

print("docs/roster.json updated with FULL league rosters + stats")
