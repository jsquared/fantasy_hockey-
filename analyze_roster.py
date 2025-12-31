import json
import os
from datetime import datetime, timezone

from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa


OUTPUT_PATH = "docs/roster.json"


def safe_get(d, key, default=None):
    return d.get(key, default) if isinstance(d, dict) else default


def normalize_player(player_obj):
    """
    Yahoo returns players as:
    [
      { "player_key": "...", "name": {...}, ... },
      { "selected_position": {...} },
      { "player_stats": {...} }
    ]
    OR sometimes missing parts.
    This function safely flattens everything.
    """

    if not isinstance(player_obj, list):
        return {}

    meta = {}
    selected_position = None
    stats = {}

    for item in player_obj:
        if not isinstance(item, dict):
            continue

        if "player_key" in item:
            meta = item

        if "selected_position" in item:
            pos_block = item.get("selected_position")
            if isinstance(pos_block, dict):
                selected_position = pos_block.get("position")

        if "player_stats" in item:
            stats_block = item.get("player_stats", {})
            if isinstance(stats_block, dict):
                stat_list = stats_block.get("stats", [])
                if isinstance(stat_list, list):
                    for stat in stat_list:
                        if isinstance(stat, dict):
                            stat_id = stat.get("stat_id")
                            value = stat.get("value")
                            if stat_id is not None:
                                stats[str(stat_id)] = value

    name_block = safe_get(meta, "name", {})
    editorial_team = safe_get(meta, "editorial_team_abbr")

    return {
        "player_key": meta.get("player_key"),
        "player_id": meta.get("player_id"),
        "name": name_block.get("full"),
        "team": meta.get("editorial_team_full_name"),
        "team_abbr": editorial_team,
        "primary_position": meta.get("primary_position"),
        "selected_position": selected_position,
        "stats": stats
    }


def main():
    oauth = OAuth2(None, None, from_file="oauth2.json")
    game = yfa.Game(oauth, "nhl")

    league_id = game.league_ids()[0]
    league = game.to_league(league_id)

    week = league.current_week()

    output = {
        "league": league.settings().get("name"),
        "week": week,
        "teams": {},
        "lastUpdated": datetime.now(timezone.utc).isoformat()
    }

    teams = league.teams()

    for team in teams:
        team_key = team.get("team_key")
        team_name = team.get("name")

        print(f"Pulling roster for {team_key}")

        output["teams"][team_key] = {
            "team_key": team_key,
            "team_name": team_name,
            "manager": None,
            "players": []
        }

        try:
            roster = league.team_roster(team_key, week)
        except Exception as e:
            print(f"Roster fetch failed for {team_key}: {e}")
            continue

        if not isinstance(roster, dict):
            continue

        players = roster.get("players", {})
        if not isinstance(players, dict):
            continue

        for _, player_block in players.items():
            player_data = normalize_player(player_block)
            if player_data:
                output["teams"][team_key]["players"].append(player_data)

    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Roster written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
