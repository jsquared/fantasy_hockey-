import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"

# =========================
# OAuth (GitHub-safe)
# =========================
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

# =========================
# Yahoo Objects
# =========================
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

current_week = league.current_week()
teams = league.teams()  # dict keyed by team_key

# =========================
# Output container
# =========================
output = {
    "league": league.settings().get("name", "Unknown League"),
    "week": current_week,
    "teams": {},
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

# =========================
# Iterate teams
# =========================
for team_key, team_meta in teams.items():
    print(f"Pulling roster for {team_key}")

    team_entry = {
        "team_key": team_key,
        "team_name": team_meta.get("name"),
        "manager": None,
        "players": []
    }

    # Manager name
    managers = team_meta.get("managers", [])
    if managers:
        team_entry["manager"] = managers[0]["manager"].get("nickname")

    # =========================
    # Pull roster (players only)
    # =========================
    roster_raw = league.yhandler.get_roster_raw(team_key, current_week)

    roster_block = (
        roster_raw
        .get("fantasy_content", {})
        .get("team", [])[1]
        .get("roster", {})
    )

    # Iterate roster slots
    for slot in roster_block.values():
        if not isinstance(slot, dict):
            continue

        players = slot.get("players", {})
        if not isinstance(players, dict):
            continue

        for player_obj in players.values():
            player_data = player_obj.get("player", [])
            if not player_data or not isinstance(player_data, list):
                continue

            player_meta = player_data[0]

            player_key = player_meta.get("player_key")
            player_name = player_meta.get("name", {}).get("full")

            # =========================
            # Pull REAL stats (this is the missing piece)
            # =========================
            stats = {}
            try:
                player_api = yfa.Player(oauth, player_key)
                raw_stats = player_api.stats()  # season stats
                if isinstance(raw_stats, dict):
                    stats = raw_stats
            except Exception as e:
                print(f"Stats failed for {player_name}: {e}")

            team_entry["players"].append({
                "player_key": player_key,
                "player_id": player_meta.get("player_id"),
                "name": player_name,
                "team": player_meta.get("editorial_team_full_name"),
                "team_abbr": player_meta.get("editorial_team_abbr"),
                "primary_position": player_meta.get("primary_position"),
                "display_position": player_meta.get("display_position"),
                "stats": stats
            })

    output["teams"][team_key] = team_entry

# =========================
# WRITE OUTPUT
# =========================
os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(output, f, indent=2)

print("docs/roster.json updated with player stats")
