import json
import os
from datetime import datetime

from yahoo_oauth import OAuth2
from yahoo_fantasy_api import League


# ---------------- CONFIG ----------------

GAME_CODE = "nhl"
LEAGUE_ID = "33140"
OUTPUT_FILE = "docs/roster.json"

# ---------------------------------------


def extract_player_stats(player_block):
    """
    Extract stats safely from Yahoo player XML/JSON blob
    """
    stats_out = {}

    player_stats = player_block.get("player_stats")
    if not player_stats:
        return stats_out

    stats = player_stats.get("stats", {}).get("stat", [])
    for stat in stats:
        stat_id = stat.get("stat_id")
        value = stat.get("value")
        stats_out[stat_id] = value

    return stats_out


def main():
    # OAuth
    oauth = OAuth2(None, None, from_file="oauth2.json")
    league = League(oauth, GAME_CODE, LEAGUE_ID)

    league_key = league.league_id
    teams = league.teams()

    output = {
        "league": league_key,
        "lastUpdated": datetime.utcnow().isoformat() + "Z",
        "teams": {}
    }

    for team_key, team_name in teams.items():
        print(f"Pulling roster for {team_key}")

        output["teams"][team_key] = {
            "team_key": team_key,
            "team_name": team_name,
            "players": []
        }

        # ---- Get roster player keys only ----
        roster = league.yhandler.get_team_roster_raw(team_key)

        players_block = (
            roster.get("fantasy_content", {})
            .get("team", {})
            .get("roster", {})
            .get("players", {})
            .get("player", [])
        )

        player_keys = []
        for p in players_block:
            if isinstance(p, dict):
                key = p.get("player_key")
                if key:
                    player_keys.append(key)

        if not player_keys:
            continue

        # ---- Fetch stats via Players API ----
        players_raw = league.yhandler.get_players_raw(
            league_key,
            player_keys,
            subresources=["stats"]
        )

        players_data = (
            players_raw.get("fantasy_content", {})
            .get("league", {})
            .get("players", {})
            .get("player", [])
        )

        for player in players_data:
            if not isinstance(player, dict):
                continue

            player_entry = {
                "player_key": player.get("player_key"),
                "player_id": player.get("player_id"),
                "name": player.get("name", {}).get("full"),
                "team": player.get("editorial_team_full_name"),
                "team_abbr": player.get("editorial_team_abbr"),
                "position": player.get("display_position"),
                "stats": extract_player_stats(player)
            }

            output["teams"][team_key]["players"].append(player_entry)

    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Roster written to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
