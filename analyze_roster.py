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
SWING_THRESHOLD = 0.10  # 10% difference to flag as swing

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

# =========================
# OAUTH
# =========================
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

# =========================
# TEAMS
# =========================
teams = {t.team_key: t.name for t in league.teams()}
my_team_key = league.team_key()

# =========================
# DATA COLLECTION
# =========================
team_players = {}
player_averages = {}
team_avg_stats = defaultdict(dict)

for team_key in teams.keys():
    team_obj = league.team(team_key)
    roster = team_obj.roster()  # returns list of player dicts
    team_players[team_key] = roster

    for player in roster:
        pid = player["player_id"]
        player_stats = player.stats("season")
        player_averages[pid] = {}

        for stat_id, stat_name in STAT_MAP.items():
            val = player_stats.get(stat_id)
            if val is not None:
                # normalize goalie stats vs skaters
                if stat_name in ["GA", "GAA", "Shots Against", "SV%", "Saves", "Wins", "Shutouts"]:
                    # simple normalization: SV%, Wins, Shutouts positive, GA/GAA/Sa negative
                    norm_val = val
                    if stat_name in ["GA", "GAA", "Shots Against"]:
                        norm_val *= -1
                    player_averages[pid][stat_name] = norm_val
                else:
                    player_averages[pid][stat_name] = val

# Compute team averages
for team_key, roster in team_players.items():
    for stat_name in STAT_MAP.values():
        vals = []
        for player in roster:
            pid = player["player_id"]
            if stat_name in player_averages[pid]:
                vals.append(player_averages[pid][stat_name])
        if vals:
            team_avg_stats[team_key][stat_name] = sum(vals) / len(vals)
        else:
            team_avg_stats[team_key][stat_name] = 0

# =========================
# TEAM STRENGTHS / WEAKNESSES
# =========================
my_team_avg = team_avg_stats[my_team_key]
strengths = sorted(my_team_avg, key=lambda x: my_team_avg[x], reverse=True)[:5]
weaknesses = sorted(my_team_avg, key=lambda x: my_team_avg[x])[:5]

# =========================
# TRADE ANALYSIS
# =========================
trade_recommendations = []

# Evaluate 1-for-1 trades
for partner_key, roster in team_players.items():
    if partner_key == my_team_key:
        continue
    for my_player in team_players[my_team_key]:
        for their_player in roster:
            my_pid = my_player["player_id"]
            their_pid = their_player["player_id"]
            net_gain = 0
            for stat in STAT_MAP.values():
                my_val = player_averages[my_pid].get(stat, 0)
                their_val = player_averages[their_pid].get(stat, 0)
                diff = their_val - my_val
                net_gain += diff
            trade_recommendations.append({
                "partner": teams[partner_key],
                "type": "1-for-1",
                "i_give": my_player["name"],
                "i_get": their_player["name"],
                "net_gain": round(net_gain, 3)
            })

# Evaluate 2-for-1 trades (all pairs of my players)
for partner_key, roster in team_players.items():
    if partner_key == my_team_key:
        continue
    for my_pair in combinations(team_players[my_team_key], 2):
        for their_player in roster:
            my_pids = [p["player_id"] for p in my_pair]
            their_pid = their_player["player_id"]
            net_gain = 0
            for stat in STAT_MAP.values():
                my_val = sum(player_averages[p]["stat"] if stat in player_averages[p] else 0 for p in my_pids)
                their_val = player_averages[their_pid].get(stat, 0)
                diff = their_val - my_val
                net_gain += diff
            trade_recommendations.append({
                "partner": teams[partner_key],
                "type": "2-for-1",
                "i_give": [p["name"] for p in my_pair],
                "i_get": their_player["name"],
                "net_gain": round(net_gain, 3)
            })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "my_team": my_team_key,
    "strengths": strengths,
    "weaknesses": weaknesses,
    "trade_recommendations": sorted(trade_recommendations, key=lambda x: -x["net_gain"]),
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with player-level trade suggestions")
