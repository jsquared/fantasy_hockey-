import json
import os
from datetime import datetime

from yahoo_oauth import OAuth2
from yahoo_fantasy_api import League


OUTPUT_PATH = "docs/roster.json"


def normalize_player_stats(stats_block):
    """
    Yahoo stats are usually:
    [
      {'stat': {'stat_id': '5', 'value': '12'}},
      ...
    ]
    This converts them into {stat_id: value}
    """
    stats = {}

    if not isinstance(stats_block, list):
        return stats

    for item in stats_block:
        if not isinstance(item, dict):
            continue
        stat = item.get("stat")
        if isinstance(stat, dict):
            stats[stat.get("stat_id")] = stat.get("value")

    return stats


def main():
    oauth = OAuth2(None, None, from_file="oauth2.json")

    league = League(oauth, "465.l.33140")

    output = {
        "league": league.league_key,
        "teams": {},
        "lastUpdated": datetime.utcnow().isoformat() + "Z"
    }

    teams = league.teams()

    for team_key, team_name in teams.items():
        print(f"Pulling roster for {team_key}")

        output["teams"][team_key] = {
            "team_key": team_key,
            "team_name": team_name,
            "players": []
        }

        # Roster call (NO STATS HERE)
        roster = league.team_roster(team_key)

        if not isinstance(roster, list):
            continue

        for entry in roster:
            if not isinstance(entry, dict):
                continue

            player_block = entry.get("player")
            if not isinstance(player_block, list):
                continue

            player_meta = {}
            selected_position = None

            for item in player_block:
                if isinstance(item, dict):
                    if "player_key" in item:
                        player_meta = item
                    if "selected_position" in item:
                        selected_position = item["selected_position"]

            player_key = player_meta.get("player_key")
            player_id = player_meta.get("player_id")

            if not player_key:
                continue

            # ---- PLAYER STATS CALL (THIS IS THE IMPORTANT PART) ----
            try:
                raw_stats = league.player_stats(player_key)
            except Exception as e:
                raw_stats = []

            stats = {}
            if isinstance(raw_stats, list):
                for s in raw_stats:
                    if isinstance(s, dict) and "stats" in s:
                        stats = normalize_player_stats(s.get("stats"))
                        break

            output["teams"][team_key]["players"].append({
                "player_key": player_key,
                "player_id": player_id,
                "name": player_meta.get("name", {}).get("full"),
                "team": player_meta.get("editorial_team_full_name"),
                "team_abbr": player_meta.get("editorial_team_abbr"),
                "primary_position": player_meta.get("primary_position"),
                "selected_position": selected_position,
                "stats": stats
            })

    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote roster to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
