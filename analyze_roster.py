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

# Categories to analyze (skater only)
CATEGORIES = ["G", "A", "PPP", "SOG", "FW", "HIT", "BLK"]

# Categories where lower is better (excluded from skater logic)
LOWER_IS_BETTER = set()

# Thresholds
WEAK_THRESHOLD = 0.90   # < 90% of league avg = weak
SURPLUS_THRESHOLD = 1.10  # > 110% of league avg = surplus
SAFE_OFFER_PCT = 0.05  # player contributes <5% of team total = safe to trade

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
# STEP 1: Pull all rosters
# =========================
team_rosters = defaultdict(list)
all_player_ids = set()

for team_key in teams.keys():
    raw = league.yhandler.get_team_roster_raw(team_key)
    players = raw["fantasy_content"]["team"][1]["roster"]["0"]["players"]

    for _, p in players.items():
        if _ == "count":
            continue
        pdata = p["player"][0]
        pid = int(pdata[0]["player_id"])

        team_rosters[team_key].append({
            "player_id": pid,
            "name": pdata[2]["name"]["full"],
            "positions": pdata[4]["eligible_positions"],
            "status": pdata[1].get("status", "")
        })
        all_player_ids.add(pid)

# =========================
# STEP 2: Pull season stats
# =========================
player_stats = {}
BATCH = 25
ids = list(all_player_ids)

for i in range(0, len(ids), BATCH):
    batch = ids[i:i+BATCH]
    stats = league.player_stats(batch, "season")
    for p in stats:
        player_stats[p["player_id"]] = p

# =========================
# STEP 3: Team totals
# =========================
team_totals = defaultdict(lambda: defaultdict(float))

for team_key, roster in team_rosters.items():
    for p in roster:
        stats = player_stats.get(p["player_id"])
        if not stats:
            continue
        for cat in CATEGORIES:
            team_totals[team_key][cat] += safe_float(stats.get(cat))

# =========================
# STEP 4: League averages
# =========================
league_averages = {}
for cat in CATEGORIES:
    league_averages[cat] = sum(
        team_totals[t][cat] for t in team_totals
    ) / len(team_totals)

# =========================
# STEP 5: Weak & surplus cats
# =========================
my_totals = team_totals[my_team_key]

weak_cats = [
    c for c in CATEGORIES
    if my_totals[c] < league_averages[c] * WEAK_THRESHOLD
]

surplus_cats = [
    c for c in CATEGORIES
    if my_totals[c] > league_averages[c] * SURPLUS_THRESHOLD
]

# =========================
# STEP 6: Identify safe-to-offer players
# =========================
safe_offers = []

for p in team_rosters[my_team_key]:
    stats = player_stats.get(p["player_id"])
    if not stats:
        continue

    contribution = 0
    for cat in surplus_cats:
        contribution += safe_float(stats.get(cat))

    total_surplus = sum(my_totals[c] for c in surplus_cats) or 1

    if contribution / total_surplus < SAFE_OFFER_PCT:
        safe_offers.append({
            "player_id": p["player_id"],
            "name": p["name"],
            "contribution": round(contribution, 1)
        })

# =========================
# STEP 7: Find trade partners
# =========================
trade_targets = []

for team_key, totals in team_totals.items():
    if team_key == my_team_key:
        continue

    # They are strong where I'm weak
    helps = [
        c for c in weak_cats
        if totals[c] > league_averages[c]
    ]

    # They are weak where I'm strong
    needs = [
        c for c in surplus_cats
        if totals[c] < league_averages[c]
    ]

    if not helps or not needs:
        continue

    # Rank players on their team by impact
    for p in team_rosters[team_key]:
        stats = player_stats.get(p["player_id"])
        if not stats:
            continue

        boost = sum(
            safe_float(stats.get(c)) for c in helps
        )

        if boost <= 0:
            continue

        trade_targets.append({
            "team_key": team_key,
            "player_id": p["player_id"],
            "name": p["name"],
            "boost_score": round(boost, 1),
            "helps": helps,
            "they_need": needs
        })

trade_targets.sort(key=lambda x: x["boost_score"], reverse=True)

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "generated": datetime.now(timezone.utc).isoformat(),
    "my_team": my_team_key,
    "my_totals": dict(my_totals),
    "league_averages": league_averages,
    "weak_categories": weak_cats,
    "surplus_categories": surplus_cats,
    "safe_trade_offers": safe_offers,
    "recommended_trades": trade_targets[:15]
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with trade recommendations")
