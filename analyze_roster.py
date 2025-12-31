import json
import os
from datetime import datetime, timezone

from yahoo_oauth import OAuth2
from yahoo_fantasy_api import League


LEAGUE_KEY = "465.l.33140"
OUTPUT_FILE = "docs/roster.json"


def normalize_stats(stats_block):
    """
    Yahoo returns stats as a list of dicts like:
    [{ 'stat_id': '5', 'value': '12' }, ...]
    Convert to { stat_id: value }
    """
    stats = {}

    if not isinstance(stats_block, list):
        return stats

    for item in stats_block:
        if not isinstance(item, dict):
            continue
        stat_id = item.get("stat_id")
        value = item.get("value")
        if stat_id is not None:
            stats[str(stat_id)] = value

    return stats


def main():
    oauth = OAuth2(None, None, from_file="oauth2.json")
    league = League(oauth, LEAGUE_KEY)

    output = {
        "league": LEAGUE_KEY,
        "teams": {},
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
    }

    teams = league.teams()  # SAFE call

    for team_key, team_name in teams.items():
        print(f"Pulling roster for {team_key}")

        output["teams"][team_key] = {
            "team_key": team_key,
            "team_name": team_name,
            "players": [],
        }

        try:
            roster = league.team_roster(team_key)
        except Exception as e:
            print(f"  Failed to get roster: {e}")
            continue

        if not isinstance(roster, list):
            continue

        for player in roster:
            if not isinstance(player, dict):
                continue

            player_key = player.get("player_key")
            name = player.get("name")
            team = player.get("editorial_team_full_name")
            team_abbr = player.get("editorial_team_abbr")
            primary_position = player.get("primary_position")

            stats = {}
            try:
                raw_stats = league.player_stats(player_key, "season")
                stats = normalize_stats(raw_stats)
            except Exception:
                stats = {}

            output["teams"][team_key]["players"].append({
                "player_key": player_key,
                "name": name,
                "team": team,
                "team_abbr": team_abbr,
                "primary_position": primary_position,
                "stats": stats,
            })

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n✅ Wrote roster data to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
