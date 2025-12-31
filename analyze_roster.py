import json
import os
from datetime import datetime

from yahoo_oauth import OAuth2
from yahoo_fantasy_api import League


OUTPUT_PATH = "docs/roster.json"


def safe_dict(val):
    return val if isinstance(val, dict) else {}


def safe_list(val):
    return val if isinstance(val, list) else []


def extract_player(player_obj):
    """
    player_obj is the value of "player" from Yahoo.
    It is usually a LIST of dicts + ints.
    """
    data = {}
    stats = {}

    for item in safe_list(player_obj):
        if not isinstance(item, dict):
            continue

        # player metadata
        if "player_key" in item:
            data["player_key"] = item.get("player_key")
            data["player_id"] = item.get("player_id")
            data["name"] = item.get("name", {}).get("full")
            data["team"] = item.get("editorial_team_full_name")
            data["team_abbr"] = item.get("editorial_team_abbr")
            data["primary_position"] = item.get("primary_position")

        # selected position
        if "selected_position" in item:
            data["selected_position"] = item["selected_position"].get("position")

        # stats block (DO NOT PARSE — JUST DUMP)
        if "stats" in item:
            for stat_block in safe_list(item["stats"]):
                if not isinstance(stat_block, dict):
                    continue
                for s in safe_list(stat_block.get("stats", [])):
                    stat = safe_dict(s.get("stat"))
                    stat_id = stat.get("stat_id")
                    value = stat.get("value")
                    if stat_id is not None:
                        stats[str(stat_id)] = value

    data["stats"] = stats
    return data


def main():
    oauth = OAuth2(None, None, from_file="oauth2.json")

    league = League(
        oauth,
        game_code="nhl",
        league_id="33140"
    )

    result = {
        "league": league.league_id,
        "teams": {},
        "lastUpdated": datetime.utcnow().isoformat() + "Z",
    }

    teams = league.teams()

    for team_key, team_name in teams.items():
        print(f"Pulling roster for {team_key}")

        team_block = {
            "team_key": team_key,
            "team_name": team_name,
            "players": []
        }

        roster = league.roster(team_key)

        for entry in safe_list(roster):
            if not isinstance(entry, dict):
                continue

            player_obj = entry.get("player")
            if not player_obj:
                continue

            player_data = extract_player(player_obj)
            if player_data:
                team_block["players"].append(player_data)

        result["teams"][team_key] = team_block

    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Wrote roster to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
