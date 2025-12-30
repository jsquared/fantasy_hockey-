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
# Pull rosters and player stats
# =========================
league_rosters = {}

for team_key, team_data in teams.items():
    print(f"Pulling roster for {team_key}")
    try:
        raw_roster = league.yhandler.get_roster_raw(team_key, current_week)
    except Exception as e:
        print(f"  Failed to get roster for {team_key}: {e}")
        continue

    players_info = []
    team_blocks = raw_roster.get("fantasy_content", {}).get("team", [])
    if not team_blocks:
        continue

    # Team block usually at index 1
    roster_block = None
    for block in team_blocks[1:]:
        if "roster" in block:
            roster_block = block["roster"]
            break
    if not roster_block:
        continue

    for key, players_group in roster_block.items():
        if not key.isdigit():
            continue
        players = players_group.get("players", {})
        for pkey, pdata in players.items():
            player_main = pdata.get("player", [])
            if not player_main:
                continue

            player_metadata = player_main[0][0]  # core metadata
            selected_pos_block = player_main[1][0].get("selected_position", [{}])
            selected_position = selected_pos_block[1].get("position") if len(selected_pos_block) > 1 else None

            # Pull player stats (week)
            player_key = player_metadata.get("player_key")
            stats_dict = {}
            if player_key:
                try:
                    raw_stats = league.yhandler.get_player_stats_raw(player_key, week=current_week)
                    stats_list = raw_stats["fantasy_content"]["player"][1]["player_stats"]["stats"]
                    for s in stats_list:
                        stat_id = s["stat"]["stat_id"]
                        value = s["stat"]["value"]
                        stats_dict[stat_id] = value
                except Exception as e:
                    print(f"    Could not get stats for {player_key}: {e}")

            players_info.append({
                "player_key": player_metadata.get("player_key"),
                "player_id": player_metadata.get("player_id"),
                "name": player_metadata.get("name", {}).get("full"),
                "team": player_metadata.get("editorial_team_full_name"),
                "team_abbr": player_metadata.get("editorial_team_abbr"),
                "display_position": player_metadata.get("display_position"),
                "primary_position": player_metadata.get("primary_position"),
                "eligible_positions": [pos.get("position") for pos in player_metadata.get("eligible_positions", [])],
                "selected_position": selected_position,
                "stats": stats_dict
            })

    manager_name = None
    managers = team_data.get("managers")
    if managers:
        manager_name = managers[0].get("manager", {}).get("nickname")

    league_rosters[team_key] = {
        "team_key": team_key,
        "team_name": team_data.get("name"),
        "manager": manager_name,
        "players": players_info
    }

# =========================
# Write output
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

print("docs/roster.json updated with FULL league rosters and player stats")
