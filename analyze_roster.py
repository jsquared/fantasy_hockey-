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
WEEKS = 12
SWING_THRESHOLD = 0.10  # 10% for category swing

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

# =========================
# LEAGUE OBJECTS
# =========================
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

# Fix for team objects vs strings
teams = {}
for t in league.teams():
    if hasattr(t, "team_key"):
        teams[t.team_key] = t
    else:
        team_obj = league.team(t)
        teams[team_obj.team_key] = team_obj

my_team_key = league.team_key()
current_week = int(league.current_week())

# =========================
# HELPERS
# =========================
def extract_team_stats(team_block):
    stats = {}
    for item in team_block[1]["team_stats"]["stats"]:
        stat_id = str(item["stat"]["stat_id"])
        try:
            stats[stat_id] = float(item["stat"]["value"])
        except (TypeError, ValueError):
            stats[stat_id] = None
    return stats

def extract_player_stats(team_obj):
    """Returns player_id -> {stat_name: value}"""
    player_stats = {}
    for player in team_obj.roster(week=None)["players"]:
        pid = player["player_id"]
        stats_block = player.get("player_stats", {}).get("stats", [])
        stats = {}
        for s in stats_block:
            sid = str(s["stat"]["stat_id"])
            if sid in STAT_MAP:
                try:
                    stats[STAT_MAP[sid]] = float(s["stat"]["value"])
                except (TypeError, ValueError):
                    stats[STAT_MAP[sid]] = None
        player_stats[pid] = {"name": player["name"], "stats": stats}
    return player_stats

def normalize(value, min_v, max_v):
    if max_v == min_v:
        return 0.5
    return (value - min_v) / (max_v - min_v)

# =========================
# DATA COLLECTION
# =========================
weekly_stats = defaultdict(dict)
weekly_ranks = defaultdict(dict)
player_stats_all = {}

for week in range(1, WEEKS + 1):
    raw = league.yhandler.get_scoreboard_raw(league.league_id, week)
    matchups = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

    for _, matchup_block in matchups.items():
        if _ == "count":
            continue
        teams_block = matchup_block["matchup"]["0"]["teams"]
        for _, team_entry in teams_block.items():
            if _ == "count":
                continue
            team_block = team_entry["team"]
            team_key = team_block[0][0]["team_key"]
            weekly_stats[week][team_key] = extract_team_stats(team_block)

# Weekly ranking
for week, team_vals in weekly_stats.items():
    for stat_id, stat_name in STAT_MAP.items():
        values = {t: v.get(stat_id) for t, v in team_vals.items() if v.get(stat_id) is not None}
        reverse = stat_name not in LOWER_IS_BETTER
        ranked = sorted(values.items(), key=lambda x: x[1], reverse=reverse)
        for rank, (team_key, _) in enumerate(ranked, start=1):
            weekly_ranks[week].setdefault(team_key, {})[stat_name] = rank

# =========================
# PLAYER STATS
# =========================
for t_key, t_obj in teams.items():
    player_stats_all[t_key] = extract_player_stats(t_obj)

# =========================
# AVG STATS + RANKS
# =========================
avg_stats = defaultdict(dict)
avg_ranks = defaultdict(dict)

for t_key in teams:
    for stat_id, stat_name in STAT_MAP.items():
        values = []
        ranks = []
        for week in range(1, WEEKS + 1):
            v = weekly_stats[week].get(t_key, {}).get(stat_id)
            r = weekly_ranks[week].get(t_key, {}).get(stat_name)
            if v is not None:
                values.append(v)
            if r is not None:
                ranks.append(r)
        avg_stats[t_key][stat_name] = sum(values)/len(values) if values else None
        avg_ranks[t_key][stat_name] = sum(ranks)/len(ranks) if ranks else None

# =========================
# 1-for-1 AND 2-for-1 PLAYER TRADE RECOMMENDATIONS
# =========================
trade_recs = []

my_players = player_stats_all[my_team_key]

for t_key, opp_players in player_stats_all.items():
    if t_key == my_team_key:
        continue
    # 1-for-1 trades
    for my_pid, my_p in my_players.items():
        for opp_pid, opp_p in opp_players.items():
            net_gain = 0
            for stat in STAT_MAP.values():
                my_val = my_p["stats"].get(stat, 0) or 0
                opp_val = opp_p["stats"].get(stat, 0) or 0
                league_vals = [avg_stats[t][stat] for t in avg_stats if avg_stats[t][stat] is not None]
                min_v, max_v = min(league_vals), max(league_vals)
                my_score = normalize(my_val, min_v, max_v)
                opp_score = normalize(opp_val, min_v, max_v)
                net_gain += opp_score - my_score
            if net_gain > 0:
                trade_recs.append({
                    "partner": teams[t_key].name,
                    "type": "1-for-1",
                    "i_give": my_p["name"],
                    "i_get": opp_p["name"],
                    "net_gain": round(net_gain, 3)
                })
    # 2-for-1 trades (combinations of my players)
    for my_pair in combinations(my_players.values(), 2):
        for opp_pid, opp_p in opp_players.items():
            net_gain = 0
            for stat in STAT_MAP.values():
                my_val = sum(p["stats"].get(stat,0) or 0 for p in my_pair)
                opp_val = opp_p["stats"].get(stat,0) or 0
                league_vals = [avg_stats[t][stat] for t in avg_stats if avg_stats[t][stat] is not None]
                min_v, max_v = min(league_vals), max(league_vals)
                my_score = normalize(my_val, min_v, max_v)
                opp_score = normalize(opp_val, min_v, max_v)
                net_gain += opp_score - my_score
            if net_gain > 0:
                trade_recs.append({
                    "partner": teams[t_key].name,
                    "type": "2-for-1",
                    "i_give": [p["name"] for p in my_pair],
                    "i_get": opp_p["name"],
                    "net_gain": round(net_gain, 3)
                })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "my_team": my_team_key,
    "strengths": sorted([s for s in STAT_MAP.values() if avg_ranks[my_team_key][s] <= 5]),
    "weaknesses": sorted([s for s in STAT_MAP.values() if avg_ranks[my_team_key][s] >= 10]),
    "trade_recommendations": sorted(trade_recs, key=lambda x: -x["net_gain"]),
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with player-level trade suggestions")
