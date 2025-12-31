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
OUTPUT_FILE = "docs/roster.json"

STAT_KEYS = [
    "G", "A", "+/-", "PIM", "PPP", "SHP", "GWG",
    "SOG", "FW", "HIT", "BLK",
    "W", "GA", "GAA", "SV%", "SHO"
]

LOWER_IS_BETTER = {"GA", "GAA"}

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
teams = league.teams()

# =========================
# Helpers
# =========================
def safe_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0

# =========================
# LEAGUE AVERAGES (TEAM LEVEL)
# =========================
league_totals = defaultdict(float)
league_counts = defaultdict(int)

for team_key in teams.keys():
    stats = league.team_stats(team_key)
    for k in STAT_KEYS:
        if k in stats:
            league_totals[k] += safe_float(stats[k])
            league_counts[k] += 1

league_averages = {
    k: league_totals[k] / league_counts[k]
    for k in league_totals
    if league_counts[k] > 0
}

# =========================
# MY ROSTER
# =========================
team = league.to_team(my_team_key)
roster = team.roster()

player_ids = []
player_meta = {}

for p in roster:
    pid = int(p["player_id"])
    player_ids.append(pid)
    player_meta[pid] = {
        "name": p["name"],
        "positions": p.get("eligible_positions", []),
        "status": p.get("status", "")
    }

stats = league.player_stats(player_ids, "season")

# =========================
# ROSTER AGGREGATES
# =========================
roster_totals = defaultdict(float)
player_contributions = {}

for p in stats:
    pid = int(p["player_id"])
    player_contributions[pid] = {}

    for k in STAT_KEYS:
        val = safe_float(p.get(k))
        roster_totals[k] += val
        player_contributions[pid][k] = val

# =========================
# CATEGORY EVALUATION
# =========================
category_analysis = {}

for k in STAT_KEYS:
    my_val = roster_totals.get(k, 0)
    league_avg = league_averages.get(k, 0)

    if league_avg == 0:
        continue

    diff = my_val - league_avg
    score = diff / league_avg

    if k in LOWER_IS_BETTER:
        score *= -1

    category_analysis[k] = {
        "my_total": round(my_val, 2),
        "league_avg": round(league_avg, 2),
        "relative_strength": round(score, 3)
    }

# =========================
# TRADE RECOMMENDATION LOGIC
# =========================
weak_cats = sorted(
    category_analysis.items(),
    key=lambda x: x[1]["relative_strength"]
)[:4]

strong_cats = sorted(
    category_analysis.items(),
    key=lambda x: x[1]["relative_strength"],
    reverse=True
)[:4]

trade_away = []
trade_for = []

for pid, stats in player_contributions.items():
    strength = sum(stats.get(k[0], 0) for k in strong_cats)
    weakness = sum(stats.get(k[0], 0) for k in weak_cats)

    if strength > weakness * 2:
        trade_away.append(player_meta[pid]["name"])

    if weakness > strength * 2:
        trade_for.append(player_meta[pid]["name"])

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "team_key": my_team_key,
    "lastUpdated": datetime.now(timezone.utc).isoformat(),
    "league_averages": league_averages,
    "roster_totals": roster_totals,
    "category_analysis": category_analysis,
    "trade_recommendations": {
        "weak_categories": [k for k, _ in weak_cats],
        "strong_categories": [k for k, _ in strong_cats],
        "suggest_trade_away": sorted(set(trade_away)),
        "suggest_trade_for": sorted(set(trade_for))
    }
}

os.makedirs("docs", exist_ok=True)
with open(OUTPUT_FILE, "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with trade recommendations")
