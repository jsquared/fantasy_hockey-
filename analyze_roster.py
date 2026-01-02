import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
from collections import defaultdict
import itertools

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"
FAIR_VALUE_TOLERANCE = 0.10  # ±10% player value difference
MIN_CATEGORY_GAIN = 2       # minimum categories improved for both teams

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

teams_meta = league.teams()
my_team_key = league.team_key()

# =========================
# Helpers
# =========================
def normalize(value, min_v, max_v):
    if max_v == min_v:
        return 0.5
    return (value - min_v) / (max_v - min_v)

# =========================
# ROSTERS + PLAYER STATS
# =========================
team_rosters = defaultdict(list)
player_stats = {}
stat_pool = defaultdict(list)

for team_key in teams_meta:
    team = yfa.Team(oauth, team_key)
    roster = team.roster()

    for p in roster:
        pid = p["player_id"]
        team_rosters[team_key].append(pid)

        if pid in player_stats:
            continue

        stats = {}
        for s in p["player_stats"]["stats"]:
            stat_id = str(s["stat"]["stat_id"])
            try:
                val = float(s["stat"]["value"])
                stats[stat_id] = val
                stat_pool[stat_id].append(val)
            except (TypeError, ValueError):
                continue

        player_stats[pid] = {
            "name": p["name"]["full"],
            "team": team_key,
            "stats": stats
        }

# =========================
# PLAYER VALUE MODEL
# =========================
player_values = {}

for pid, pdata in player_stats.items():
    total = 0
    contributing = 0

    for stat_id, stat_name in STAT_MAP.items():
        if stat_id not in pdata["stats"]:
            continue

        vals = stat_pool.get(stat_id)
        if not vals:
            continue

        v = pdata["stats"][stat_id]
        min_v, max_v = min(vals), max(vals)
        norm = normalize(v, min_v, max_v)

        if stat_name in LOWER_IS_BETTER:
            norm = 1 - norm

        total += norm
        contributing += 1

    if contributing:
        player_values[pid] = round(total / contributing, 4)

# =========================
# TEAM CATEGORY TOTALS
# =========================
team_category_totals = defaultdict(lambda: defaultdict(float))

for team_key, pids in team_rosters.items():
    for pid in pids:
        for stat_id, stat_name in STAT_MAP.items():
            team_category_totals[team_key][stat_name] += \
                player_stats[pid]["stats"].get(stat_id, 0)

# =========================
# TRADE SIMULATION
# =========================
trade_recommendations = []

my_players = team_rosters[my_team_key]

for opp_key in teams_meta:
    if opp_key == my_team_key:
        continue

    opp_players = team_rosters[opp_key]

    for my_pid, opp_pid in itertools.product(my_players, opp_players):
        my_val = player_values.get(my_pid)
        opp_val = player_values.get(opp_pid)

        if not my_val or not opp_val:
            continue

        # Fair value check
        if abs(my_val - opp_val) / max(my_val, opp_val) > FAIR_VALUE_TOLERANCE:
            continue

        my_gain = 0
        opp_gain = 0

        for stat_id, stat_name in STAT_MAP.items():
            my_before = team_category_totals[my_team_key][stat_name]
            opp_before = team_category_totals[opp_key][stat_name]

            my_after = (
                my_before
                - player_stats[my_pid]["stats"].get(stat_id, 0)
                + player_stats[opp_pid]["stats"].get(stat_id, 0)
            )

            opp_after = (
                opp_before
                - player_stats[opp_pid]["stats"].get(stat_id, 0)
                + player_stats[my_pid]["stats"].get(stat_id, 0)
            )

            if my_after > my_before:
                my_gain += 1
            if opp_after > opp_before:
                opp_gain += 1

        if my_gain >= MIN_CATEGORY_GAIN and opp_gain >= MIN_CATEGORY_GAIN:
            trade_recommendations.append({
                "give": player_stats[my_pid]["name"],
                "receive": player_stats[opp_pid]["name"],
                "opponent_team": opp_key,
                "my_value": my_val,
                "opp_value": opp_val,
                "my_category_gains": my_gain,
                "opp_category_gains": opp_gain
            })

# =========================
# OUTPUT (docs/roster.json)
# =========================
os.makedirs("docs", exist_ok=True)

payload = {
    "league": league.settings()["name"],
    "generated": datetime.now(timezone.utc).isoformat(),
    "my_team": my_team_key,
    "trade_recommendations": trade_recommendations
}

with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print(f"docs/roster.json updated with {len(trade_recommendations)} fair 1-for-1 trade recommendations")
