import json
import os
from datetime import datetime, timezone
from collections import defaultdict
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"
GOALIE_STATS = ["Wins", "GA", "GAA", "Shots Against", "Saves", "SV%", "Shutouts"]

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

# =========================
# HELPERS
# =========================
def normalize(value, min_v, max_v):
    if max_v == min_v:
        return 0.5
    return (value - min_v) / (max_v - min_v)

# =========================
# OAUTH
# =========================
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

my_team_key = league.team_key()
team_obj = league.to_team(my_team_key)

# =========================
# PLAYER DATA COLLECTION
# =========================
team_roster = {}
goalie_values = defaultdict(list)

for p in team_obj.roster():
    # p can be either player_id string or dict, handle both
    pid = p if isinstance(p, str) else p["player_id"]
    player_info = league.player(pid)

    name = player_info["name"]["full"]
    pos = player_info.get("selected_position", {}).get("position", "NA")

    # Pull stats for current season (weeks 1-current_week)
    raw_stats = league.player_stats(pid, 1, league.current_week())
    stats = {}
    for sid, sname in STAT_MAP.items():
        try:
            stats[sname] = float(raw_stats.get(sid, 0))
        except (TypeError, ValueError):
            stats[sname] = 0

    team_roster[pid] = {
        "name": name,
        "position": pos,
        "stats": stats
    }

    # Track goalies separately for normalization
    if pos == "G":
        for gs in GOALIE_STATS:
            if stats.get(gs) is not None:
                goalie_values[gs].append(stats[gs])

# =========================
# GOALIE NORMALIZATION
# =========================
goalie_minmax = {stat: (min(vals), max(vals)) for stat, vals in goalie_values.items()}

for pdata in team_roster.values():
    if pdata["position"] == "G":
        normalized = {}
        for stat in GOALIE_STATS:
            min_v, max_v = goalie_minmax.get(stat, (0, 1))
            normalized[stat] = normalize(pdata["stats"].get(stat, 0), min_v, max_v)
        pdata["normalized_stats"] = normalized

# =========================
# WRITE OUTPUT
# =========================
payload = {
    "team_key": my_team_key,
    "team_name": team_obj.name,
    "players": team_roster,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with player stats and normalized goalies")
