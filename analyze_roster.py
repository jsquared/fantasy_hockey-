import json
import os
from datetime import datetime

from yahoo_oauth import OAuth2
from yahoo_fantasy_api.yhandler import YHandler


# ---------------- CONFIG ----------------
LEAGUE_KEY = "465.l.33140"
TEAM_KEY = "465.l.33140.t.14"
OUTPUT_FILE = "docs/roster.json"
# ---------------------------------------


def main():
    oauth = OAuth2(None, None, from_file="oauth.json")
    if not oauth.token_is_valid():
        oauth.refresh_access_token()

    yhandler = YHandler(oauth)

    print(f"Pulling roster for {TEAM_KEY}")

    # 1️⃣ Get roster players (RAW)
    roster_raw = yhandler.get_team_roster_raw(TEAM_KEY)

    players = []
    roster_players = []

    try:
        roster_players = (
            roster_raw["fantasy_content"]["team"][1]["roster"]["0"]["players"]
        )
    except Exception:
        roster_players = []

    # Normalize roster list
    if isinstance(roster_players, dict):
        roster_players = roster_players.values()

    player_keys = []

    for p in roster_players:
        if not isinstance(p, dict):
            continue
        player = p.get("player", [])
        if isinstance(player, list):
            for item in player:
                if isinstance(item, dict) and "player_key" in item:
                    player_keys.append(item["player_key"])

    # Deduplicate
    player_keys = list(set(player_keys))

    print(f"Found {len(player_keys)} players")

    # 2️⃣ Pull ALL stats for roster players
    stats_raw = {}
    if player_keys:
        stats_raw = yhandler.get_player_stats_raw(
            LEAGUE_KEY,
            ",".join(player_keys),
            req_type="season"
        )

    # 3️⃣ Write EVERYTHING (no parsing, no guessing)
    output = {
        "league": LEAGUE_KEY,
        "team": TEAM_KEY,
        "player_keys": player_keys,
        "raw_stats": stats_raw,
        "lastUpdated": datetime.utcnow().isoformat() + "Z",
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Wrote stats to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
