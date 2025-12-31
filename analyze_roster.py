import json
import os
from datetime import datetime
from yahoo_oauth import OAuth2
from yahoo_fantasy_api import League

# ---------- CONFIG ----------
GAME_CODE = "nhl"
LEAGUE_ID = "33140"   # numeric only
OUTPUT_PATH = "docs/roster.json"
# ----------------------------


def safe_get(d, key, default=None):
    return d.get(key) if isinstance(d, dict) else default


def extract_player_meta(player_block):
    """
    Yahoo player blocks are LISTS of dicts and garbage.
    This pulls out the dict that actually contains player data.
    """
    if not isinstance(player_block, list):
        return None

    for item in player_block:
        if isinstance(item, dict) and "player_key" in item:
            return item
    return None


def extract_stats(stats_block):
    """
    Converts Yahoo stat list into {stat_id: value}
    """
    stats = {}

    if not isinstance(stats_block, dict):
        return stats

    stat_list = stats_block.get("stats", [])
    if not isinstance(stat_list, list):
        return stats

    for s in stat_list:
        if isinstance(s, dict):
            stat_id = s.get("stat_id")
            value = s.get("value")
            if stat_id is not None:
                stats[str(stat_id)] = value

    return stats


def main():
    # ---- OAuth ----
    oauth = OAuth2(None, None, from_file="oauth.json")
    if not oauth.token_is_valid():
        oauth.refresh_access_token()

    # ---- League ----
    league = League(oauth, GAME_CODE, LEAGUE_ID)

    output = {
        "league": league.league_id,
        "teams": {},
        "lastUpdated": datetime.utcnow().isoformat() + "Z",
    }

    teams = league.teams()

    for team_key, team_name in teams.items():
        print(f"Pulling roster for {team_key}")

        output["teams"][team_key] = {
            "team_key": team_key,
            "team_name": team_name,
            "players": []
        }

        roster = league.team_roster(team_key)

        if not isinstance(roster, list):
            continue

        for player_block in roster:
            player_meta = extract_player_meta(player_block)
            if not player_meta:
                continue

            player_key = player_meta.get("player_key")
            player_id = player_meta.get("player_id")

            name_block = safe_get(player_meta, "name", {})
            name = safe_get(name_block, "full")

            team_abbr = player_meta.get("editorial_team_abbr")
            position = player_meta.get("display_position")
            image_url = player_meta.get("image_url")

            # ---- STATS (SEASON) ----
            stats = {}
            try:
                raw_stats = league.player_stats(player_key)
                if isinstance(raw_stats, dict):
                    stats = extract_stats(raw_stats)
            except Exception:
                stats = {}

            output["teams"][team_key]["players"].append({
                "player_key": player_key,
                "player_id": player_id,
                "name": name,
                "team_abbr": team_abbr,
                "position": position,
                "image_url": image_url,
                "stats": stats
            })

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Roster written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
