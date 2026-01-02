import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
from collections import defaultdict
from itertools import combinations

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"
SWING_THRESHOLD = 0.10  # 10% swing for confidence
MAX_PLAYERS_FOR_2_FOR_1 = 2

STAT_MAP = {
    "1": "G",
    "2": "A",
    "4": "+/-",
    "5": "PIM",
    "8": "PPP",
    "11": "SHP",
    "12": "GWG",
    "14": "SOG",
    "16": "FW",
    "31": "HIT",
    "32": "BLK",
    "19": "W",
    "22": "GA",
    "23": "GAA",
    "24": "SA",
    "25": "SV",
    "26": "SV%",
    "27": "SHO",
}

LOWER_IS_BETTER = {"GA", "GAA", "SA"}

# =========================
# OAUTH
# =========================
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

# =========================
# SETUP LEAGUE
# =========================
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)
my_team_key = league.team_key()
teams = {t["team_key"]: t["name"] for t in league.teams()}

# =========================
# FETCH ROSTERS & PLAYER STATS
# =========================
team_players = {}
player_averages = {}

for team_key in teams.keys():
    roster = league.team(team_key).roster()
    team_players[team_key] = roster
    for player in roster:
        pid = player["player_id"]
        player_averages[pid] = {}
        stats = player.stats("season")  # season averages
        for stat_id, stat_name in STAT_MAP.items():
            value = stats.get(stat_id)
            if value is not None:
                player_averages[pid][stat_name] = value

# =========================
# COMPUTE TEAM TOTALS
# =========================
team_totals = {}
for team_key, players in team_players.items():
    totals = defaultdict(float)
    for player in players:
        pid = player["player_id"]
        for stat_name, val in player_averages.get(pid, {}).items():
            totals[stat_name] += val
    team_totals[team_key] = totals

# =========================
# NORMALIZATION FUNCTION
# =========================
def normalize(value, min_v, max_v):
    if max_v == min_v:
        return 0.5
    return (value - min_v) / (max_v - min_v)

# =========================
# CALCULATE TRADE VALUE
# =========================
def trade_value(i_give, i_get, team_totals_dict):
    """Compute net gain of a trade in normalized category points."""
    values = []
    for stat in STAT_MAP.values():
        stat_vals = [team_totals_dict[t][stat] for t in team_totals_dict if stat in team_totals_dict[t]]
        values.append((stat, min(stat_vals), max(stat_vals)))

    def score(team, stats_to_consider):
        s = 0
        for stat, min_v, max_v in values:
            val = team.get(stat, 0)
            n = normalize(val, min_v, max_v)
            if stat in LOWER_IS_BETTER:
                n = 1 - n
            if stat in stats_to_consider:
                s += n
        return s

    my_score = score(team_totals_dict[my_team_key], i_get)
    opp_score = score(team_totals_dict[my_team_key], i_give)
    return my_score - opp_score

# =========================
# GENERATE TRADE RECOMMENDATIONS
# =========================
trade_recommendations = []

for partner_key, partner_name in teams.items():
    if partner_key == my_team_key:
        continue

    my_players = team_players[my_team_key]
    partner_players = team_players[partner_key]

    # 1-for-1 trades
    for mine in my_players:
        for theirs in partner_players:
            net_gain = trade_value([mine["player_id"]], [theirs["player_id"]], player_averages)
            trade_recommendations.append({
                "partner": partner_name,
                "type": "1-for-1",
                "i_give": mine["name"],
                "i_get": theirs["name"],
                "net_gain": round(net_gain, 3)
            })

    # 2-for-1 trades
    for combo in combinations(my_players, 2):
        for theirs in partner_players:
            net_gain = trade_value([p["player_id"] for p in combo], [theirs["player_id"]], player_averages)
            trade_recommendations.append({
                "partner": partner_name,
                "type": "2-for-1",
                "i_give": [p["name"] for p in combo],
                "i_get": theirs["name"],
                "net_gain": round(net_gain, 3)
            })

# =========================
# OUTPUT TO JSON
# =========================
payload = {
    "league": league.settings()["name"],
    "my_team": my_team_key,
    "teams": teams,
    "team_totals": team_totals,
    "trade_recommendations": sorted(trade_recommendations, key=lambda x: -x["net_gain"]),
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with player-level trade recommendations")
