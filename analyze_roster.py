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
WEAK_THRESHOLD = 0.90   # 10% below league average
STRONG_THRESHOLD = 1.10 # 10% above league average

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

def sum_stats(stats):
    return {k: safe_float(stats.get(k)) for k in CATEGORIES}

# =========================
# COLLECT ALL ROSTERS + STATS
# =========================
team_totals = defaultdict(lambda: defaultdict(float))
player_pool = []

for team_key in teams.keys():
    roster_raw = league.yhandler.get_roster_raw(team_key)

    players = roster_raw["fantasy_content"]["team"][1]["roster"]["0"]["players"]

    for _, p in players.items():
        if _ == "count":
            continue

        pdata = p["player"][0]
        player_id = int(pdata[1]["player_id"])
        name = pdata[2]["name"]["full"]

        positions = [pos["position"] for pos in pdata if isinstance(pos, dict) and "position" in pos]
        status = pdata[1].get("status", "")

        # Fetch season stats by PLAYER ID
        stats_resp = league.player_stats([player_id], "season")
        stats = stats_resp[0] if stats_resp else {}

        cleaned = sum_stats(stats)

        for cat, val in cleaned.items():
            team_totals[team_key][cat] += val

        player_pool.append({
            "team_key": team_key,
            "player_id": player_id,
            "name": name,
            "positions": positions,
            "status": status,
            "stats": cleaned
        })

# =========================
# LEAGUE AVERAGES
# =========================
league_avg = {}
for cat in CATEGORIES:
    league_avg[cat] = sum(team_totals[t][cat] for t in team_totals) / len(team_totals)

my_totals = team_totals[my_team_key]

# =========================
# WEAK / STRONG CATEGORIES
# =========================
weak_cats = [
    c for c in CATEGORIES
    if my_totals[c] < league_avg[c] * WEAK_THRESHOLD
]

strong_cats = [
    c for c in CATEGORIES
    if my_totals[c] > league_avg[c] * STRONG_THRESHOLD
]

# =========================
# FIND TRADE TARGETS (HELP YOU)
# =========================
targets = []

for p in player_pool:
    if p["team_key"] == my_team_key:
        continue

    helps = [c for c in weak_cats if p["stats"][c] > league_avg[c]]

    if not helps:
        continue

    boost = sum(p["stats"][c] for c in helps)

    targets.append({
        "team_key": p["team_key"],
        "player_id": p["player_id"],
        "name": p["name"],
        "boost_score": round(boost, 1),
        "helps": helps
    })

targets = sorted(targets, key=lambda x: x["boost_score"], reverse=True)[:15]

# =========================
# IDENTIFY SAFE TRADE BAIT (FROM YOUR TEAM)
# =========================
trade_bait = []

for p in player_pool:
    if p["team_key"] != my_team_key:
        continue

    contributes = [c for c in strong_cats if p["stats"][c] > league_avg[c]]
    hurts = [c for c in weak_cats if p["stats"][c] > 0]

    if contributes and not hurts:
        trade_bait.append({
            "player_id": p["player_id"],
            "name": p["name"],
            "surplus_categories": contributes,
            "stats": p["stats"]
        })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "generated": datetime.now(timezone.utc).isoformat(),
    "my_team": my_team_key,

    "trade_analysis": {
        "weak_categories": weak_cats,
        "strong_categories": strong_cats,
        "my_totals": my_totals,
        "league_averages": league_avg,
        "recommended_targets": targets,
        "safe_trade_bait": trade_bait
    }
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with trade recommendations")
