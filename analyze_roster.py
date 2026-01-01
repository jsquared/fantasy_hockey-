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

# Skater categories only (simplified + stable)
CATEGORIES = ["G", "A", "PPP", "SOG", "FW", "HIT", "BLK"]

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
# COLLECT ROSTERS + STATS
# =========================
team_totals = defaultdict(lambda: defaultdict(float))
player_pool = []

for team_key in teams.keys():
    team = league.to_team(team_key)

    roster = team.roster()
    player_ids = [p["player_id"] for p in roster]

    stats = league.player_stats(player_ids, "season")

    stats_map = {p["player_id"]: p for p in stats}

    for p in roster:
        pid = p["player_id"]
        pdata = stats_map.get(pid, {})

        player_entry = {
            "team_key": team_key,
            "player_id": pid,
            "name": p["name"],
            "positions": p.get("eligible_positions", []),
            "stats": {}
        }

        for cat in CATEGORIES:
            val = safe_float(pdata.get(cat))
            player_entry["stats"][cat] = val
            team_totals[team_key][cat] += val

        player_pool.append(player_entry)

# =========================
# LEAGUE AVERAGES
# =========================
league_avg = {}
for cat in CATEGORIES:
    league_avg[cat] = sum(team_totals[t][cat] for t in team_totals) / len(team_totals)

# =========================
# MY STRENGTHS & WEAKNESSES
# =========================
my_totals = team_totals[my_team_key]

weak_cats = [c for c in CATEGORIES if my_totals[c] < league_avg[c]]
strong_cats = [c for c in CATEGORIES if my_totals[c] > league_avg[c]]

# =========================
# TEAM PROFILES
# =========================
team_strengths = {}
team_weaknesses = {}

for t in team_totals:
    team_strengths[t] = [c for c in CATEGORIES if team_totals[t][c] > league_avg[c]]
    team_weaknesses[t] = [c for c in CATEGORIES if team_totals[t][c] < league_avg[c]]

# =========================
# TRADE RECOMMENDATION ENGINE
# =========================
trade_targets = []

for p in player_pool:
    if p["team_key"] == my_team_key:
        continue

    helps = [c for c in weak_cats if p["stats"][c] > 0]

    if not helps:
        continue

    other_team = p["team_key"]

    # Must help their weakness AND not hurt our strength
    if not any(c in team_weaknesses[other_team] for c in strong_cats):
        continue

    boost = sum(p["stats"][c] for c in helps)

    trade_targets.append({
        "team_key": other_team,
        "player_id": p["player_id"],
        "name": p["name"],
        "boost_score": round(boost, 2),
        "helps": helps
    })

trade_targets.sort(key=lambda x: x["boost_score"], reverse=True)

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "generated": datetime.now(timezone.utc).isoformat(),
    "trade_analysis": {
        "weak_categories": weak_cats,
        "strong_categories": strong_cats,
        "my_totals": my_totals,
        "league_averages": league_avg,
        "recommended_targets": trade_targets[:15]
    }
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with trade recommendations")
