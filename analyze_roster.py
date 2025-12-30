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
teams_meta = league.teams()

# =========================
# Helpers
# =========================
def safe_get(d, path, default=None):
    """Safely traverse nested Yahoo structures"""
    try:
        for p in path:
            d = d[p]
        return d
    except (KeyError, IndexError, TypeError):
        return default

def extract_player_stats(player_key):
    """Pull season stats for a player"""
    try:
        raw = league.yhandler.get_player_stats_raw(
            player_key,
            "season"
        )
        stats = {}

        stat_blocks = safe_get(
            raw,
            ["fantasy_content", "player", "1", "player_stats", "stats"],
            []
        )

        for s in stat_blocks:
            stat_id = str(s["stat"]["stat_id"])
            val = s["stat"].get("value")
            try:
                stats[stat_id] = float(val)
            except (TypeError, ValueError):
                stats[stat_id] = val

        return stats
    except Exception:
        return {}

# =========================
# DATA COLLECTION
# =========================
league_rosters = {}

for team_key, team_meta in teams_meta.items():
    print(f"Pulling roster for {team_key}")

    raw = league.yhandler.get_roster_raw(team_key, current_week)

    roster_block = safe_get(
        raw,
        ["fantasy_content", "team", "1", "roster"],
        {}
    )

    players_block = roster_block.get("0", {}).get("players", {})

    players = []

    for _, pwrap in players_block.items():
        if _ == "count":
            continue

        pdata = pwrap["player"][0]
        selected = pwrap["player"][1]["selected_position"][1]["position"]

        player_key = safe_get(pdata, [0, "player_key"])
        player_id = safe_get(pdata, [1, "player_id"])

        player = {
            "player_key": player_key,
            "player_id": player_id,
            "name": safe_get(pdata, [2, "name", "full"]),
            "editorial_team": safe_get(pdata, [6]),
            "team_abbr": safe_get(pdata, [7]),
            "uniform_number": safe_get(pdata, [10]),
            "display_position": safe_get(pdata, [11]),
            "primary_position": safe_get(pdata, [14]),
            "eligible_positions": safe_get(pdata, [15], []),
            "selected_position": selected,
            "stats": extract_player_stats(player_key)
        }

        players.append(player)

    league_rosters[team_key] = {
        "team_key": team_key,
        "team_name": team_meta["name"],
        "manager": team_meta.get("managers", [{}])[0].get("nickname"),
        "players": players
    }

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "week": current_week,
    "teams": league_rosters,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json updated with full rosters + player stats")
