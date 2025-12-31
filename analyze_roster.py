import json
import os
from datetime import datetime

from yahoo_oauth import OAuth2
from yahoo_fantasy_api import League, Team, Player


# ===== CONFIG =====
LEAGUE_ID = "465.l.33140"
TEAM_KEY = "465.l.33140.t.14"
OUTPUT_FILE = "docs/roster.json"


def main():
    # ---- OAuth ----
    oauth = OAuth2(None, None, from_file="oauth.json")

    # ---- League ----
    league = League(oauth, LEAGUE_ID)

    # ---- Team ----
    team = Team(oauth, TEAM_KEY)

    # ---- Get roster player keys ----
    roster_player_keys = team.roster()

    players_out = []

    for player_key in roster_player_keys:
        player = Player(oauth, player_key)

        # ---- Metadata ----
        meta = player.player_info()

        # ---- Season stats (THIS IS THE KEY PART YOU WERE MISSING) ----
        stats = player.stats()

        players_out.append({
            "player_key": player_key,
            "name": meta.get("name", {}).get("full"),
            "team": meta.get("editorial_team_full_name"),
            "team_abbr": meta.get("editorial_team_abbr"),
            "display_position": meta.get("display_position"),
            "eligible_positions": meta.get("eligible_positions", []),
            "stats": stats
        })

    # ---- Final JSON ----
    output = {
        "league": LEAGUE_ID,
        "team_key": TEAM_KEY,
        "players": players_out,
        "lastUpdated": datetime.utcnow().isoformat() + "Z"
    }

    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Saved roster with stats → {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
