import json
import os
from datetime import datetime

from yahoo_oauth import OAuth2
from yahoo_fantasy_api import League, Team

GAME_CODE = "nhl"
LEAGUE_ID = "33140"   # numeric league id
DOCS_PATH = "docs/roster.json"


def main():
    # OAuth via environment (NO oauth.json)
    oauth = OAuth2(
        consumer_key=os.environ["YAHOO_CONSUMER_KEY"],
        consumer_secret=os.environ["YAHOO_CONSUMER_SECRET"],
        refresh_token=os.environ["YAHOO_REFRESH_TOKEN"],
    )

    league = League(oauth, GAME_CODE, LEAGUE_ID)

    output = {
        "league": league.league_id,
        "teams": {},
        "lastUpdated": datetime.utcnow().isoformat() + "Z",
    }

    # Iterate teams
    for team_key in league.teams():
        team = Team(oauth, team_key)

        team_data = {
            "team_key": team_key,
            "team_name": team.team_info().get("name"),
            "players": [],
        }

        # Roster returns player keys
        for player_key in team.roster():
            player = league.player_details(player_key)

            player_entry = {
                "player_key": player_key,
                "player_id": player.get("player_id"),
                "name": player.get("name", {}).get("full"),
                "editorial_team": player.get("editorial_team_full_name"),
                "editorial_team_abbr": player.get("editorial_team_abbr"),
                "display_position": player.get("display_position"),
                "eligible_positions": player.get("eligible_positions", {}),
                "stats": {},
            }

            # Get stats (season by default)
            try:
                stats = league.player_stats(player_key)
                player_entry["stats"] = stats
            except Exception as e:
                player_entry["stats_error"] = str(e)

            team_data["players"].append(player_entry)

        output["teams"][team_key] = team_data

    os.makedirs("docs", exist_ok=True)
    with open(DOCS_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Roster written to {DOCS_PATH}")


if __name__ == "__main__":
    main()
