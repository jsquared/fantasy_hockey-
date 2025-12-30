import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
GAME_CODE = "nhl"
PLAYER_KEY = "465.p.8642"  # Quinton Byfield
LEAGUE_ID = "465.l.33140"

# =========================
# OAuth
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

# =========================
# Pull Quinton Byfield stats
# =========================
stats_dict = {}
try:
    raw_stats = league.yhandler.get_player_stats_raw(PLAYER_KEY, week=current_week)
    stats_list = raw_stats["fantasy_content"]["player"][1]["player_stats"]["stats"]
    for s in stats_list:
        stat_id = s["stat"]["stat_id"]
        value = s["stat"]["value"]
        stats_dict[stat_id] = value
except Exception as e:
    print(f"Failed to get stats for {PLAYER_KEY}: {e}")

# =========================
# Prepare player info
# =========================
player_info = {
    "player_key": PLAYER_KEY,
    "name": "Quinton Byfield",
    "team": "Los Angeles Kings",
    "team_abbr": "LA",
    "primary_position": "C",
    "selected_position": "C",
    "stats": stats_dict
}

# =========================
# Write output
# =========================
payload = {
    "league": league.settings().get("name", "Unknown League"),
    "week": current_week,
    "player": player_info,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json updated with Quinton Byfield stats")
