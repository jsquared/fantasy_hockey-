import os
import json
from datetime import datetime
from yahoo_oauth import OAuth2
from yahoo_fantasy_api import League


GAME_CODE = "nhl"
LEAGUE_ID = "33140"
OUTPUT_FILE = "docs/roster.json"


def main():
    # ---------- AUTH ----------
    oauth = OAuth2(
        consumer_key=os.environ["YAHOO_CONSUMER_KEY"],
        consumer_secret=os.environ["YAHOO_CONSUMER_SECRET"],
    )

    league = League(oauth, GAME_CODE, LEAGUE_ID)

    output = {
        "league": f"{GAME_CODE}.l.{LEAGUE_ID}",
        "teams": {},
        "lastUpdated": datetime.utcnow().isoformat() + "Z",
    }

    # ---------- TEAMS ----------
    for team_key in league.teams().keys():
        print(f"Pulling roster for {team_key}")

        team = league.to_team(team_key)
        roster = team.roster()

        players_out = []

        for player in roster:
            # player is a dict wrapped in Yahoo nonsense
            if not isinstance(player, dict):
                continue

            player_key = player.get("player_key")
            if not player_key:
                continue

            # ---------- RAW STATS ----------
            stats_raw = league.yhandler.get_player_stats_raw(
                league_id=league.league_id,
                player_keys=player_key,
            )

            players_out.append({
                "player_key": player_key,
                "name": player.get("name"),
                "team": player.get("editorial_team_full_name"),
                "team_abbr": player.get("editorial_team_abbr"),
                "display_position": player.get("display_position"),
                "stats_raw": stats_raw,  # <-- NOTHING FILTERED
            })

        output["teams"][team_key] = {
            "team_key": team_key,
            "team_name": team.team_name(),
            "players": players_out,
        }

    # ---------- WRITE FILE ----------
    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"✅ Wrote roster data to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
