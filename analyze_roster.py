import json
import os
from datetime import datetime, timezone

from yahoo_oauth import OAuth2
from yahoo_fantasy_api import League


def unwrap(items):
    """
    Yahoo returns lists of {key: value} dicts.
    This converts them into a single dict.
    """
    out = {}
    for item in items:
        if isinstance(item, dict):
            out.update(item)
    return out


# --- OAuth ---
oauth = OAuth2(None, None, from_file="oauth2.json")

# --- League ---
GAME_KEY = "465"          # NHL
LEAGUE_ID = "33140"       # Your league
league = League(oauth, f"{GAME_KEY}.l.{LEAGUE_ID}")

current_week = league.current_week()

output = {
    "league": league.settings()["name"],
    "week": current_week,
    "teams": {},
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

teams = league.teams()

for team_key, team_name in teams.items():
    print(f"Pulling roster for {team_key}")

    team_data = {
        "team_key": team_key,
        "team_name": team_name,
        "manager": None,
        "players": []
    }

    # --- ROSTER ---
    roster_raw = league.yhandler.get_roster_raw(team_key, current_week)

    # Path: team -> roster -> players -> player
    team_block = roster_raw["fantasy_content"]["team"][1]
    roster_block = team_block["roster"]
    players_block = roster_block["players"]

    for p in players_block:
        if "player" not in p:
            continue

        player = unwrap(p["player"])

        # --- Selected position ---
        selected_position = None
        if "selected_position" in player:
            selected_position = player["selected_position"].get("position")

        player_key = player.get("player_key")

        # --- SEASON STATS ---
        stats = {}
        try:
            stats_raw = league.yhandler.get_player_stats_raw(
                player_key,
                req_type="season"
            )

            stat_list = (
                stats_raw["fantasy_content"]["player"][1]
                ["player_stats"]["stats"]
            )

            for s in stat_list:
                stat = s["stat"]
                stats[stat["stat_id"]] = stat.get("value")

        except Exception as e:
            stats = {}

        team_data["players"].append({
            "player_key": player_key,
            "player_id": player.get("player_id"),
            "name": player.get("name", {}).get("full"),
            "editorial_team": player.get("editorial_team_full_name"),
            "team_abbr": player.get("editorial_team_abbr"),
            "primary_position": player.get("primary_position"),
            "eligible_positions": [
                pos["position"]
                for pos in player.get("eligible_positions", [])
            ],
            "selected_position": selected_position,
            "status": player.get("status"),
            "stats": stats
        })

    output["teams"][team_key] = team_data


# --- Write file ---
os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(output, f, indent=2)

print("Roster written to docs/roster.json")
