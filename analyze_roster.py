import json
import os
import itertools
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
from collections import defaultdict

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"
WEEKS = 12  # number of weeks to average over
MAX_TRADE_PLAYERS = 2  # 1-for-1 and 2-for-1 only

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
# Setup OAuth
# =========================
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

# =========================
# Yahoo fantasy objects
# =========================
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

my_team_key = league.team_key()
all_team_keys = league.teams()

# =========================
# ROSTERS
# =========================
rosters = {}
players_info = {}

for team_key in all_team_keys:
    team_obj = league.to_team(team_key)
    roster = team_obj.roster()
    rosters[team_key] = []

    for p in roster:
        pid = p["player_id"]
        rosters[team_key].append(pid)
        players_info[pid] = {
            "name": p["name"],
            "positions": p.get("eligible_positions", [])
        }

# =========================
# WEEKLY STATS (per player NOT team)
# =========================
player_weekly = defaultdict(lambda: defaultdict(list))

for week in range(1, WEEKS + 1):
    raw = league.yhandler.get_scoreboard_raw(league.league_id, week)
    matchups = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

    for _, matchup_data in matchups.items():
        if _ == "count":
            continue
        teams_block = matchup_data["matchup"]["0"]["teams"]
        for tk, team_data in teams_block.items():
            if tk == "count":
                continue
            for pstat in team_data["team"][1]["player_stats"]["stats"]:
                pid = pstat["player_id"]
                for stat_item in pstat["stats"]:
                    stat_id = stat_item["stat_id"]
                    if stat_id in STAT_MAP:
                        try:
                            player_weekly[pid][STAT_MAP[stat_id]].append(float(stat_item["value"]))
                        except:
                            pass

# =========================
# PLAYER AVERAGES (per stat)
# =========================
player_avg = {}

for pid, stats in player_weekly.items():
    player_avg[pid] = {}
    for stat, vals in stats.items():
        if vals:
            player_avg[pid][stat] = sum(vals) / len(vals)

# =========================
# TEAM CATEGORY AVERAGES
# =========================
team_category_avg = defaultdict(lambda: defaultdict(float))

for team_key, pids in rosters.items():
    for pid in pids:
        for stat, avg in player_avg.get(pid, {}).items():
            team_category_avg[team_key][stat] += avg

# =========================
# CATEGORY SURPLUS / WEAKNESS
# =========================
league_category_avg = defaultdict(list)

for team_key in team_category_avg:
    for stat, val in team_category_avg[team_key].items():
        league_category_avg[stat].append(val)

league_category_avg = {stat: sum(vals)/len(vals) for stat, vals in league_category_avg.items()}

my_cat = team_category_avg[my_team_key]
strengths = [s for s,v in my_cat.items() if v > league_category_avg.get(s, 0)]
weaknesses = [s for s,v in my_cat.items() if v < league_category_avg.get(s, 0)]

# =========================
# PLAYER MARGINAL VALUE
# =========================
player_marginal = {}

for team_key, pids in rosters.items():
    player_marginal[team_key] = {}
    for pid in pids:
        base = team_category_avg[team_key]
        without = base.copy()
        for stat, avg in player_avg.get(pid, {}).items():
            without[stat] = without.get(stat,0) - avg
        marginal = {stat: base.get(stat,0) - without.get(stat,0) for stat in STAT_MAP.values()}
        player_marginal[team_key][pid] = marginal

# =========================
# TRADE SIMULATION
# =========================
trade_results = []

def score_trade(my_give, other_give):
    delta_me = 0
    delta_them = 0
    for stat in weaknesses:
        delta_me += player_marginal[other_team][other_give].get(stat, 0) - player_marginal[my_team_key][my_give].get(stat, 0)
    for stat in strengths:
        delta_them += player_marginal[my_team_key][my_give].get(stat, 0) - player_marginal[other_team][other_give].get(stat, 0)
    return round(delta_me + delta_them,3)

for other_team in all_team_keys:
    if other_team == my_team_key:
        continue

    # 1-for-1
    for my_pid, their_pid in itertools.product(rosters[my_team_key], rosters[other_team]):
        score = score_trade(my_pid, their_pid)
        if score > 0:
            trade_results.append({
                "partner": other_team,
                "type": "1-for-1",
                "give": players_info[my_pid]["name"],
                "get": players_info[their_pid]["name"],
                "score": score
            })

    # 2-for-1
    for my_combo in itertools.combinations(rosters[my_team_key],2):
        for their_pid in rosters[other_team]:
            my_loss = sum(player_avg.get(pid,{}).get(stat,0) for pid in my_combo for stat in weaknesses)
            their_gain = player_avg.get(their_pid,{}).get(stat,0)
            if their_gain > my_loss:
                trade_results.append({
                    "partner": other_team,
                    "type": "2-for-1",
                    "give": [players_info[pid]["name"] for pid in my_combo],
                    "get": players_info[their_pid]["name"],
                    "score": round(their_gain - my_loss,3)
                })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "my_team": my_team_key,
    "strengths": strengths,
    "weaknesses": weaknesses,
    "trade_suggestions": sorted(trade_results, key=lambda x: x["score"], reverse=True),
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with player-level trade ideas")
