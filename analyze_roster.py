import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
from collections import defaultdict

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"

# =========================
# STAT MAP
# =========================
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
    "31": "Hits",
    "32": "Blocks",
    "19": "Wins",
    "22": "GA",
    "23": "GAA",
    "24": "Shots Against",
    "25": "Saves",
    "26": "SV%",
    "27": "Shutouts"
}

GOALIE_STATS = {"Wins", "GA", "GAA", "Shots Against", "Saves", "SV%", "Shutouts"}

# =========================
# OAuth
# =========================
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

# =========================
# Yahoo League Object
# =========================
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

my_team_key = league.team_key()
current_week = int(league.current_week())

# =========================
# Helpers
# =========================
def normalize(value, min_v, max_v):
    if value is None:
        return 0.0
    if max_v == min_v:
        return 0.5
    return (value - min_v) / (max_v - min_v)

def extract_player_stats(player_id):
    raw = league.player_stats(player_id, 1, current_week)
    stats = {}
    for sid, sname in STAT_MAP.items():
        if sid in raw:
            try:
                stats[sname] = float(raw[sid])
            except (TypeError, ValueError):
                stats[sname] = None
        else:
            stats[sname] = None
    return stats

# =========================
# FETCH ROSTER AND STATS
# =========================
team_obj = league.to_team(my_team_key)
roster = team_obj.roster()

team_data = {"team_key": my_team_key, "team_name": team_obj.name, "players": {}}

for player in roster:
    pid = player if isinstance(player, str) else player["player_id"]
    player_info = league.player(pid)
    name = player_info["name"]["full"]
    pos = player_info.get("selected_position", {}).get("position", "NA")
    stats = extract_player_stats(pid)

    team_data["players"][pid] = {
        "name": name,
        "position": pos,
        "stats": stats
    }

# =========================
# NORMALIZE GOALIES
# =========================
goalie_values = defaultdict(list)
for pdata in team_data["players"].values():
    if pdata["position"] == "G":
        for stat in GOALIE_STATS:
            if pdata["stats"].get(stat) is not None:
                goalie_values[stat].append(pdata["stats"][stat])

goalie_minmax = {stat: (min(vals), max(vals)) for stat, vals in goalie_values.items() if vals}

for pdata in team_data["players"].values():
    if pdata["position"] == "G":
        normalized = {}
        for stat in GOALIE_STATS:
            if stat in pdata["stats"]:
                min_v, max_v = goalie_minmax.get(stat, (0, 1))
                normalized[stat] = normalize(pdata["stats"][stat], min_v, max_v)
        pdata["normalized_stats"] = normalized

# =========================
# OUTPUT
# =========================
output = {
    "team_key": my_team_key,
    "team_name": team_obj.name,
    "current_week": current_week,
    "players": team_data["players"],
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(output, f, indent=2)

print("✅ docs/roster.json updated with player stats")
