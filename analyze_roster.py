import json
import os
from datetime import datetime, timezone

from yahoo_oauth import OAuth2
from yahoo_fantasy_api import League


OUTPUT_PATH = "docs/roster.json"

LEAGUE_KEY = "465.l.33140"
WEEK = 13


def normalize_list(obj):
    """
    Yahoo returns:
    - dict
    - list
    - list with ints mixed in
    This makes sure we always get iterable dicts
    """
    if isinstance(obj, dict):
        return [obj]
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    return []


def extract_player_meta(player_blob):
    """
    Extracts basic player metadata from Yahoo player structure
    """
    data = {}

    if not isinstance(player_blob, dict):
        return data

    for k, v in player_blob.items():
        if k == "player_key":
            data["player_key"] = v
        elif k == "player_id":
            data["player_id"] = v
        elif k == "name":
            data["name"] = v.get("full")
        elif k == "editorial_team_full_name":
            data["team"] = v
        elif k == "editorial_team_abbr":
            data["team_abbr"] = v
        elif k == "primary_position":
            data["primary_position"] = v
        elif k == "headshot":
            data["headshot"] = v

    return data


def extract_selected_position(player_blob):
    """
    Selected position lives in a totally separate list element.
    """
    if not isinstance(player_blob, list):
        return None

    for item in player_blob:
        if isinstance(item, dict) and "selected_position" in item:
            return item["selected_position"].get("position")

    return None


def extract_stats(stats_blob):
    """
    Converts Yahoo stat list to a dict
    """
    stats = {}

    if not isinstance(stats_blob, dict):
        return stats

    stat_items = stats_blob.get("stats", [])
    for entry in normalize_list(stat_items):
        stat = entry.get("stat")
        if not isinstance(stat, dict):
            continue

        stat_id = stat.get("stat_id")
        value = stat.get("value")

        if stat_id is not None:
            stats[str(stat_id)] = value

    return stats


def main():
    oauth = OAuth2(None, None, from_file="oauth2.json")
    league = League(oauth, LEAGUE_KEY)

    result = {
        "league": league.league_settings().get("name"),
        "week": WEEK,
        "teams": {},
        "lastUpdated": datetime.now(timezone.utc).isoformat()
    }

    teams = league.teams()

    for team in teams:
        team_key = team["team_key"]
        print(f"Pulling roster for {team_key}")

        result["teams"][team_key] = {
            "team_key": team_key,
            "team_name": team["name"],
            "manager": None,
            "players": []
        }

        roster = league.yhandler.get_team_roster(team_key, week=WEEK)

        team_block = normalize_list(roster.get("team"))[0]
        roster_block = normalize_list(team_block.get("roster"))[0]
        players_block = normalize_list(roster_block.get("players"))[0]

        for player_entry in normalize_list(players_block.get("player")):
            # Player entry is a LIST of dicts
            if not isinstance(player_entry, list):
                continue

            meta = {}
            for item in player_entry:
                if isinstance(item, dict) and "player_key" in item:
                    meta = extract_player_meta(item)

            if not meta:
                continue

            selected_position = extract_selected_position(player_entry)

            # Pull stats safely
            stats = {}
            try:
                raw_stats = league.yhandler.get_player_stats_raw(
                    meta["player_key"],
                    week=WEEK
                )
                stats = extract_stats(raw_stats)
            except Exception:
                stats = {}

            result["teams"][team_key]["players"].append({
                **meta,
                "selected_position": selected_position,
                "stats": stats
            })

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(result, f, indent=2)

    print(f"Roster written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
