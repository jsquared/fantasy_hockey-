import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
from itertools import combinations
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

LOWER_IS_BETTER = {"GA", "GAA", "Shots Against"}
GOALIE_STATS = {"Wins", "GA", "GAA", "Saves", "SV%", "Shutouts"}

# =========================
# OAUTH
# =========================
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

# =========================
# LEAGUE
# =========================
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)
my_team_key = league.team_key()

# =========================
# HELPERS
# =========================
def normalize(val, min_v, max_v, invert=False):
    if val is None or min_v == max_v:
        return 0.5
    n = (val - min_v) / (max_v - min_v)
    return 1 - n if invert else n

def get_player_stats(player):
    stats = {}
    pdata = player.stats()
    for item in pdata:
        sid = str(item["stat_id"])
        if sid in STAT_MAP:
            try:
                stats[STAT_MAP[sid]] = float(item["value"])
            except (TypeError, ValueError):
                stats[STAT_MAP[sid]] = None
    return stats

# =========================
# COLLECT ALL PLAYERS
# =========================
teams = {}
players_by_team = defaultdict(dict)
league_stat_pool = defaultdict(list)

for team in league.teams():
    team_key = team.team_key
    teams[team_key] = team.name

    roster = team.roster()
    for p in roster:
        player_key = p["player_key"]
        player = yfa.Player(oauth, player_key)

        stats = get_player_stats(player)
        players_by_team[team_key][player_key] = {
            "name": p["name"]["full"],
            "stats": stats
        }

        for stat, val in stats.items():
            if val is not None:
                league_stat_pool[stat].append(val)

# =========================
# NORMALIZATION BOUNDS
# =========================
stat_bounds = {}
for stat, vals in league_stat_pool.items():
    stat_bounds[stat] = (min(vals), max(vals))

# =========================
# TRADE ENGINE
# =========================
trade_recs = []
my_players = players_by_team[my_team_key]

for opp_key, opp_players in players_by_team.items():
    if opp_key == my_team_key:
        continue

    # -------- 1-for-1 --------
    for my_p in my_players.values():
        for opp_p in opp_players.values():
            net = 0
            for stat in STAT_MAP.values():
                min_v, max_v = stat_bounds.get(stat, (0, 1))
                invert = stat in LOWER_IS_BETTER

                my_v = my_p["stats"].get(stat)
                opp_v = opp_p["stats"].get(stat)

                net += normalize(opp_v, min_v, max_v, invert) - normalize(my_v, min_v, max_v, invert)

            if net > 0:
                trade_recs.append({
                    "partner": teams[opp_key],
                    "type": "1-for-1",
                    "i_give": my_p["name"],
                    "i_get": opp_p["name"],
                    "net_gain": round(net, 3)
                })

    # -------- 2-for-1 --------
    for my_pair in combinations(my_players.values(), 2):
        for opp_p in opp_players.values():
            net = 0
            for stat in STAT_MAP.values():
                min_v, max_v = stat_bounds.get(stat, (0, 1))
                invert = stat in LOWER_IS_BETTER

                my_sum = sum(p["stats"].get(stat, 0) or 0 for p in my_pair)
                opp_v = opp_p["stats"].get(stat)

                net += normalize(opp_v, min_v, max_v, invert) - normalize(my_sum, min_v, max_v, invert)

            if net > 0:
                trade_recs.append({
                    "partner": teams[opp_key],
                    "type": "2-for-1",
                    "i_give": [p["name"] for p in my_pair],
                    "i_get": opp_p["name"],
                    "net_gain": round(net, 3)
                })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "my_team": my_team_key,
    "trade_recommendations": sorted(trade_recs, key=lambda x: -x["net_gain"]),
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with player-level trade recommendations")
