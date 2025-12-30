import json
import os
from datetime import datetime, timezone

from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa


OUTPUT_PATH = "docs/roster.json"


def normalize_list(obj):
    """Yahoo loves returning dict OR list depending on count"""
    if obj is None:
        return []
    if isinstance(obj, list):
        return obj
    return [obj]


# ---- AUTH ----
oauth = OAuth2(None, None, from_file="oauth2.json")
gm = yfa.Game(oauth, "nhl")

# Use first available league (safe for single-league accounts)
league_id = gm.league_ids()[0]
league = gm.to_league(league_id)

league_name = league.settings()["name"]
current_week = int(league.current_week())

# ---- GET ALL TEAMS ----
teams_raw = league.yhandler.get_teams_raw(league_id)

teams_out = {}

for team_entry in teams_raw["teams"]["team"]:
    team_key = team_entry["team_key"]
    team_name = team_entry["name"]

    manager_name = None
    managers = team_entry.get("managers", {})
    if managers:
        mgr = normalize_list(managers.get("manager"))
        if mgr:
            manager_name = mgr[0].get("nickname")

    print(f"Pulling roster + stats for {team_key}")

    # 🔑 THIS IS THE CRITICAL CALL
    roster_raw = league.yhandler.get_roster_raw(
        team_key,
        current_week,
        players=True,
        stats=True
    )

    players_out = []

    roster = roster_raw.get("roster", {})
    players_block = roster.get("players", {})
    players = normalize_list(players_block.get("player"))

    for player in players:
        player_data = {}

        # --- Basic metadata ---
        player_data["player_key"] = player.get("player_key")
        player_data["player_id"] = player.get("player_id")
        player_data["name"] = player.get("name", {}).get("full")

        # Team info
        editorial_team = player.get("editorial_team_full_name")
        team_abbr = player.get("editorial_team_abbr")

        player_data["nhl_team"] = editorial_team
        player_data["nhl_team_abbr"] = team_abbr

        # Positions
        player_data["primary_position"] = player.get("primary_position")
        player_data["eligible_positions"] = player.get("eligible_positions", {}).get("position", [])

        # Selected roster position
        selected_pos = None
        selected = player.get("selected_position")
        if selected:
            selected_pos = selected.get("position")

        player_data["selected_position"] = selected_pos

        # --- STATS ---
        stats_out = {}
        stats_block = player.get("player_stats", {}).get("stats", {}).get("stat")

        for stat in normalize_list(stats_block):
            stat_id = stat.get("stat_id")
            value = stat.get("value")
            stats_out[stat_id] = value

        player_data["season_stats"] = stats_out

        players_out.append(player_data)

    teams_out[team_key] = {
        "team_key": team_key,
        "team_name": team_name,
        "manager": manager_name,
        "players": players_out,
    }

# ---- WRITE FILE ----
os.makedirs("docs", exist_ok=True)

output = {
    "league": league_name,
    "week": current_week,
    "teams": teams_out,
    "lastUpdated": datetime.now(timezone.utc).isoformat(),
}

with open(OUTPUT_PATH, "w") as f:
    json.dump(output, f, indent=2)

print(f"Roster written to {OUTPUT_PATH}")
