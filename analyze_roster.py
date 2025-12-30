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
teams_meta = league.teams()  # dict keyed by team_key

# =========================
# HELPERS
# =========================
def extract_player(player_block):
    meta = player_block[0]
    selected = player_block[1] if len(player_block) > 1 else {}

    player = {
        "player_key": meta[0].get("player_key"),
        "player_id": meta[1].get("player_id"),
        "name": meta[2]["name"]["full"],
        "team": meta[6],
        "team_abbr": meta[7],
        "display_position": meta[10],
        "primary_position": meta[14],
        "eligible_positions": [
            p["position"] for p in meta[15].get("eligible_positions", [])
        ],
        "selected_position": selected.get("selected_position", [{}])[1].get("position"),
    }

    # Season stats if present
    for item in meta:
        if isinstance(item, dict) and "player_stats" in item:
            stats = {}
            for s in item["player_stats"]["stats"]:
                sid = s["stat"]["stat_id"]
                val = s["stat"].get("value")
                try:
                    stats[sid] = float(val)
                except (TypeError, ValueError):
                    stats[sid] = val
            player["season_stats"] = stats

    return player

# =========================
# ROSTER COLLECTION
# =========================
league_rosters = {}

for team_key, team_meta in teams_meta.items():
    print(f"Pulling roster for {team_key}")

    raw = league.yhandler.get_roster_raw(team_key, current_week)
    team_data = raw["fantasy_content"]["team"]

    team_info = team_data[0]
    roster_block = team_data[1]["roster"]

    team_payload = {
        "team_key": team_key,
        "team_name": team_info[2]["name"],
        "manager": team_info[-1]["managers"][0]["manager"]["nickname"],
        "players": []
    }

    players = roster_block["0"]["players"]

    for _, player_entry in players.items():
        if _ == "count":
            continue
        player_block = player_entry["player"]
        team_payload["players"].append(extract_player(player_block))

    league_rosters[team_key] = team_payload

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

print("docs/roster.json updated with full league rosters")
