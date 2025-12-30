import json
import os
from datetime import datetime, timezone

from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa


OUTPUT_PATH = "docs/roster.json"


def safe_get(d, *keys):
    """Safely navigate nested dicts"""
    for k in keys:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


# ---------------------------
# Auth & League Setup
# ---------------------------
oauth = OAuth2(None, None, from_file="oauth2.json")
gm = yfa.Game(oauth, "nhl")

# Grab first league
league_id = gm.league_ids()[0]
league = gm.to_league(league_id)

current_week = league.current_week()

output = {
    "league": league.settings()["name"],
    "week": current_week,
    "teams": {},
    "lastUpdated": datetime.now(timezone.utc).isoformat(),
}

# ---------------------------
# Iterate Teams
# ---------------------------
for team_key, team_name in league.teams().items():
    print(f"Pulling roster for {team_key}")

    team_entry = {
        "team_key": team_key,
        "team_name": team_name,
        "manager": None,
        "players": [],
    }

    # ---------------------------
    # Get Roster (RAW)
    # ---------------------------
    roster_raw = league.yhandler.get_roster_raw(team_key, current_week)

    try:
        roster_block = roster_raw["team"][1]["roster"]
        players_block = roster_block["players"]
    except (KeyError, IndexError, TypeError):
        print(f"⚠️ No roster found for {team_key}")
        output["teams"][team_key] = team_entry
        continue

    # ---------------------------
    # Parse Players
    # ---------------------------
    for p in players_block:
        player = p.get("player", [])

        # Flatten player array into dict
        pdata = {}
        selected_position = None

        for item in player:
            if isinstance(item, dict):
                if "selected_position" in item:
                    selected_position = safe_get(item, "selected_position", "position")
                else:
                    pdata.update(item)

        player_key = pdata.get("player_key")
        player_id = pdata.get("player_id")

        player_entry = {
            "player_key": player_key,
            "player_id": player_id,
            "name": pdata.get("name", {}).get("full"),
            "editorial_team": pdata.get("editorial_team_full_name"),
            "team_abbr": pdata.get("editorial_team_abbr"),
            "primary_position": pdata.get("primary_position"),
            "eligible_positions": pdata.get("eligible_positions", []),
            "selected_position": selected_position,
            "stats": {},
        }

        # ---------------------------
        # Fetch SEASON stats
        # ---------------------------
        if player_key:
            try:
                stats_raw = league.yhandler.get_player_stats_raw(
                    player_key, "season"
                )

                stats_block = stats_raw["player"][1]["player_stats"]["stats"]
                for s in stats_block:
                    stat = s.get("stat", {})
                    stat_id = stat.get("stat_id")
                    value = stat.get("value")
                    player_entry["stats"][stat_id] = value

            except Exception as e:
                print(f"⚠️ Stats failed for {player_key}: {e}")

        team_entry["players"].append(player_entry)

    output["teams"][team_key] = team_entry

# ---------------------------
# Write Output
# ---------------------------
os.makedirs("docs", exist_ok=True)

with open(OUTPUT_PATH, "w") as f:
    json.dump(output, f, indent=2)

print(f"✅ Roster written to {OUTPUT_PATH}")
