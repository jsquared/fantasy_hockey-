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
WEAK_THRESHOLD = 0.90   # < 90% of league avg
STRONG_THRESHOLD = 1.10 # > 110% of league avg

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
def get_team_roster(team_key):
    """Safely parse Yahoo roster raw structure"""
    raw = league.yhandler.get_roster_raw(team_key)
    players = []

    roster = raw["fantasy_content"]["team"][1]["roster"]["0"]["players"]

    for _, p in roster.items():
        if _ == "count":
            continue

        pdata = p["player"]
        meta = pdata[0]

        player_id = int(meta[1]["player_id"])
        name = meta[2]["name"]["full"]
        status = meta[1].get("status", "")

        players.append({
            "team_key": team_key,
            "player_id": player_id,
            "name": name,
            "status": status
        })

    return players


def sum_stats(stats):
    totals = defaultdict(float)
    for s in stats:
        for k in CATEGORIES:
            if k in s and isinstance(s[k], (int, float)):
                totals[k] += s[k]
    return dict(totals)


# =========================
# COLLECT ALL ROSTERS
# =========================
all_rosters = {}
for team_key in teams.keys():
    all_rosters[team_key] = get_team_roster(team_key)

# =========================
# PLAYER STATS (SEASON)
# =========================
team_player_stats = defaultdict(list)

for team_key, roster in all_rosters.items():
    ids = [p["player_id"] for p in roster]
    if not ids:
        continue

    stats = league.player_stats(ids, "season")

    for s in stats:
        team_player_stats[team_key].append(s)

# =========================
# TEAM TOTALS
# =========================
team_totals = {}
for team_key, stats in team_player_stats.items():
    team_totals[team_key] = sum_stats(stats)

my_totals = team_totals[my_team_key]

# =========================
# LEAGUE AVERAGES
# =========================
league_avg = {}
for cat in CATEGORIES:
    vals = [t.get(cat, 0) for t in team_totals.values()]
    league_avg[cat] = sum(vals) / len(vals)

# =========================
# WEAK / STRONG CATEGORIES
# =========================
weak = []
strong = []

for cat in CATEGORIES:
    ratio = my_totals.get(cat, 0) / league_avg[cat]
    if ratio < WEAK_THRESHOLD:
        weak.append(cat)
    elif ratio > STRONG_THRESHOLD:
        strong.append(cat)

# =========================
# SAFE TRADE BAIT
# =========================
safe_trade_bait = []

if strong:
    for s in team_player_stats[my_team_key]:
        contribution = sum(s.get(cat, 0) for cat in strong)
        if contribution > 0:
            safe_trade_bait.append({
                "player_id": s["player_id"],
                "name": s["name"],
                "strength_contribution": contribution
            })

safe_trade_bait = sorted(
    safe_trade_bait,
    key=lambda x: x["strength_contribution"]
)[:5]

# =========================
# MUTUAL TRADE TARGETS
# =========================
recommended_trades = []

for team_key, totals in team_totals.items():
    if team_key == my_team_key:
        continue

    helps_me = [c for c in weak if totals.get(c, 0) > league_avg[c]]
    i_help_them = [c for c in strong if totals.get(c, 0) < league_avg[c]]

    if not helps_me or not i_help_them:
        continue

    for s in team_player_stats[team_key]:
        boost = sum(s.get(c, 0) for c in helps_me)
        if boost > 0:
            recommended_trades.append({
                "team_key": team_key,
                "player_id": s["player_id"],
                "name": s["name"],
                "boost_score": boost,
                "helps_me": helps_me,
                "they_need": i_help_them
            })

recommended_trades = sorted(
    recommended_trades,
    key=lambda x: x["boost_score"],
    reverse=True
)[:10]

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "generated": datetime.now(timezone.utc).isoformat(),
    "my_team": my_team_key,
    "trade_analysis": {
        "weak_categories": weak,
        "strong_categories": strong,
        "my_totals": my_totals,
        "league_averages": league_avg,
        "safe_trade_bait": safe_trade_bait,
        "recommended_trades": recommended_trades
    }
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with trade recommendations")
