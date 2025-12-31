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

# Stat mapping
STAT_MAP = {
    "1": "Goals",
    "2": "Assists",
    "4": "+/-",
    "5": "PIM",
    "8": "PPP",
    "11": "SHP",
    "12": "GWG",
    "14": "SOG",
    "16": "FW",
    "19": "Wins",
    "22": "GA",
    "23": "GAA",
    "24": "Shots Against",
    "25": "Saves",
    "26": "SV%",
    "27": "Shutouts",
    "31": "Hits",
    "32": "Blocks"
}

# =========================
# OAuth Setup
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

# =========================
# Pull All Player Stats
# =========================
all_teams = league.teams()
players_data = {}

for team_key in all_teams.keys():
    roster = league.roster(team_key, week=league.current_week())

    for player_key, player_info in roster.items():
        player_name = player_info["name"]["full"]

        try:
            stats_raw = league.yhandler.get_player_stats_raw(player_key, league.league_id)
            stats = {}
            for stat in stats_raw["fantasy_content"]["player"][1]["player_stats"]["stats"]:
                stat_id = str(stat["stat"]["stat_id"])
                stats[STAT_MAP.get(stat_id, stat_id)] = float(stat["stat"]["value"])
        except (KeyError, TypeError):
            stats = {}

        players_data[player_key] = {
            "name": player_name,
            "team": team_key,
            "stats": stats
        }

# =========================
# Output JSON
# =========================
os.makedirs("docs", exist_ok=True)
output_file = "docs/roster_stats.json"

with open(output_file, "w") as f:
    json.dump({
        "league": LEAGUE_ID,
        "lastUpdated": datetime.now(timezone.utc).isoformat(),
        "players": players_data
    }, f, indent=2)

print(f"{output_file} updated with all player stats")
