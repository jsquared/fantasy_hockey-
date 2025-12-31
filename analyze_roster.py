import json
import os
from datetime import datetime, timezone

from yahoo_oauth import OAuth2
from yahoo_fantasy_api import League, Team


OUTPUT_FILE = "docs/roster.json"


def normalize_player(player_block):
    """
    Yahoo player blocks are inconsistent.
    This safely extracts metadata, positions, and stats without assuming structure.
    """
    player_data = {
        "player_key": None,
        "player_id": None,
        "name": None,
        "team": None,
        "team_abbr": None,
        "primary_position": None,
        "selected_position": None,
        "stats": {}
    }

    if not isinstance(player_block, dict):
        return player_data

    player_items = player_block.get("player", [])
    if not isinstance(player_items, list):
        return player_data

    for item in player_items:
        if not isinstance(item, dict):
            continue

        # --- Player metadata ---
        if "player_key" in item:
            player_data["player_key"] = item.get("player_key")
            player_data["player_id"] = item.get("player_id")
            player_data["name"] = item.get("name", {}).get("full")
            player_data["team"] = item.get("editorial_team_full_name")
            player_data["team_abbr"] = item.get("editorial_team_abbr")

            # Primary position
            positions = item.get("display_position")
            if positions:
                player_data["primary_position"] = positions

        # --- Selected position ---
        if "selected_position" in item:
            pos = item.get("selected_position")
            if isinstance(pos, dict):
                player_data["selected_position"] = pos.get("position")

        # --- Stats ---
        if "stats" in item:
            stats_block = item.get("stats", {})
            if isinstance(stats_block, dict):
                stats_list = stats_block.get("stats", [])
                if isinstance(stats_list, list):
                    for stat_entry in stats_list:
                        if not isinstance(stat_entry, dict):
                            continue
                        stat = stat_entry.get("stat", {})
                        if isinstance(stat, dict):
                            stat_id = stat.get("stat_id")
                            value = stat.get("value")
                            if stat_id is not None:
                                player_data["stats"][stat_id] = value

    return player_data


def main():
    # OAuth
    oauth = OAuth2(None, None, from_file="oauth2.json")

    # League setup (NO game_code, NO league_key)
    league = League(
        oauth,
        league_id="465.l.33140"
    )

    output = {
        "league": "465.l.33140",
        "teams": {},
        "lastUpdated": datetime.now(timezone.utc).isoformat()
    }

    teams = league.teams()
    if not isinstance(teams, list):
        teams = []

    for team_meta in teams:
        if not isinstance(team_meta, dict):
            continue

        team_key = team_meta.get("team_key")
        team_name = team_meta.get("name")

        if not team_key:
            continue

        print(f"Pulling roster for {team_key}")

        team = Team(oauth, team_key)

        output["teams"][team_key] = {
            "team_key": team_key,
            "team_name": team_name,
            "players": []
        }

        try:
            roster = team.roster()
        except Exception as e:
            print(f"Roster fetch failed for {team_key}: {e}")
            continue

        if not isinstance(roster, list):
            continue

        for player_block in roster:
            player_data = normalize_player(player_block)
            if player_data["player_key"]:
                output["teams"][team_key]["players"].append(player_data)

    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Roster written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
