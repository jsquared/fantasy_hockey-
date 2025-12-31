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

CATEGORIES = ["G", "A", "PPP", "SOG", "FW", "HIT", "BLK"]

WEAK_THRESHOLD = 0.90     # < 90% of league avg = weak
STRONG_THRESHOLD = 1.15   # > 115% of league avg = strong

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

my_team_key = league.team_key()
current_week = league.current_week()
teams_meta = league.teams()

# =========================
# Helpers
# =========================
def safe_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0

def extract_roster(team_key):
    """Get roster players via raw API"""
    raw = league.yhandler.get_team_roster_raw(team_key)
    players = []

    roster = raw["fantasy_content"]["team"][1]["roster"]["0"]["players"]
    for _, p in roster.items():
        if _ == "count":
            continue

        pdata = p["player"][0]
        player_id = int(pdata[1]["player_id"])
        name = pdata[2]["name"]["full"]

        positions = []
        for pos in pdata:
            if isinstance(pos, dict) and "eligible_positions" in pos:
                positions = [x["position"] for x in pos["eligible_positions"]]

        players.append({
            "player_id": player_id,
            "name": name,
            "positions": positions
        })

    return players

# =========================
# COLLECT ALL ROSTERS
# =========================
team_rosters = {}
all_player_ids = set()

for team_key in teams_meta.keys():
    roster = extract_roster(team_key)
    team_rosters[team_key] = roster
    for p in roster:
        all_player_ids.add(p["player_id"])

# =========================
# PLAYER STATS (SEASON)
# =========================
player_stats = {}
stats_batch = league.player_stats(list(all_player_ids), "season")

for p in stats_batch:
    pid = int(p["player_id"])
    player_stats[pid] = p

# =========================
# TEAM TOTALS
# =========================
team_totals = defaultdict(lambda: defaultdict(float))

for team_key, roster in team_rosters.items():
    for p in roster:
        stats = player_stats.get(p["player_id"], {})
        for cat in CATEGORIES:
            team_totals[team_key][cat] += safe_float(stats.get(cat))

# =========================
# LEAGUE AVERAGES
# =========================
league_avgs = {}

for cat in CATEGORIES:
    league_avgs[cat] = (
        sum(team_totals[t][cat] for t in team_totals) / len(team_totals)
    )

# =========================
# MY WEAK CATEGORIES
# =========================
my_totals = team_totals[my_team_key]

weak_categories = [
    cat for cat in CATEGORIES
    if my_totals[cat] < league_avgs[cat] * WEAK_THRESHOLD
]

# =========================
# FIND STRONG TEAMS
# =========================
strong_teams = defaultdict(list)

for team_key in team_totals:
    if team_key == my_team_key:
        continue
    for cat in weak_categories:
        if team_totals[team_key][cat] > league_avgs[cat] * STRONG_THRESHOLD:
            strong_teams[team_key].append(cat)

# =========================
# TRADE ENGINE
# =========================
trade_recommendations = []

for team_key, cats in strong_teams.items():
    for p in team_rosters[team_key]:
        stats = player_stats.get(p["player_id"], {})
        helps = [c for c in cats if safe_float(stats.get(c)) > 0]

        if not helps:
            continue

        boost = sum(safe_float(stats.get(c)) for c in helps)

        # Find a give-back from my team that does NOT hurt weak cats
        for my_p in team_rosters[my_team_key]:
            my_stats = player_stats.get(my_p["player_id"], {})
            hurts = [
                c for c in weak_categories
                if safe_float(my_stats.get(c)) > 0
            ]
            if hurts:
                continue

            trade_recommendations.append({
                "partner_team": team_key,
                "receive": {
                    "player_id": p["player_id"],
                    "name": p["name"]
                },
                "send": {
                    "player_id": my_p["player_id"],
                    "name": my_p["name"]
                },
                "improves": helps,
                "boost_score": round(boost, 2)
            })

# Rank best trades
trade_recommendations.sort(
    key=lambda x: x["boost_score"], reverse=True
)

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "current_week": current_week,
    "my_team": my_team_key,
    "my_totals": dict(my_totals),
    "league_averages": league_avgs,
    "weak_categories": weak_categories,
    "trade_recommendations": trade_recommendations[:15],
    "generated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with league-aware trade recommendations")
