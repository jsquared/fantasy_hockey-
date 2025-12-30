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
teams = league.teams()
current_week = league.current_week()

# =========================
# Helpers
# =========================
def safe_get(d, *keys):
    for k in keys:
        if isinstance(d, dict) and k in d:
            d = d[k]
        else:
            return None
    return d

def extract_player_stats(player_key):
    """Pull SEASON stats for a player (raw)"""
    try:
        raw = league.yhandler.get_player_stats_raw(player_key, "season")
        stats = raw["fantasy_content"]["player"][1]["player_stats"]["stats"]
        out = {}
        for s in stats:
            stat = s["stat"]
            out[str(stat["stat_id"])] = stat.get("value")
        return out
    except Exception:
        return {}

# =========================
# DATA COLLECTION
# =========================
league_rosters = {}

for team_key, team_meta in teams.items():
    print(f"Pulling roster for {team_key}")

    raw = league.yhandler.get_team_roster_raw(team_key, current_week)
    team_block = raw["fantasy_content"]["team"]
    roster_block = team_block[1]["roster"]

    team_info = {
        "team_key": team_key,
        "team_name": safe_get(team_block[0][2], "name"),
        "manager": safe_get(team_block[0][-1]["managers"][0]["manager"], "nickname"),
        "players": []
    }

    players = roster_block["0"]["players"]

    for _, p in players.items():
        if _ == "count":
            continue

        player_meta = p["player"][0]
        selected_pos = p["player"][1]["selected_position"][1]["position"]

        player_key = safe_get(player_meta[0], "player_key")

        player_data = {
            "player_key": player_key,
            "player_id": safe_get(player_meta[1], "player_id"),
            "name": safe_get(player_meta[2], "name", "full"),
            "team": safe_get(player_meta[6], "editorial_team_full_name"),
            "team_abbr": safe_get(player_meta[7], "editorial_team_abbr"),
            "display_position": safe_get(player_meta[11], "display_position"),
            "primary_position": safe_get(player_meta[13], "primary_position"),
            "eligible_positions": [
                pos["position"]
                for pos in safe_get(player_meta[14],) or []
            ],
            "selected_position": selected_pos,
            "season_stats": extract_player_stats(player_key)
        }

        team_info["players"].append(player_data)

    league_rosters[team_key] = team_info

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

print("docs/roster.json updated with full league rosters + season stats")
