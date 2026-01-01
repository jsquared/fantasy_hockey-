import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
from collections import defaultdict

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"

CATS = ["G", "A", "PPP", "SOG", "FW", "HIT", "BLK"]

SOFT_STRONG_MARGIN = 0.95   # 95% of league average counts as usable strength
WEAK_MARGIN = 0.90          # below 90% of league avg = weak

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
    raw = league.yhandler.get_roster_raw(team_key)
    players = []

    for item in raw["fantasy_content"]["team"][1]["roster"]["0"]["players"].values():
        if item == "count":
            continue

        meta = item["player"][0]
        player_id = int(meta[1]["player_id"])
        name = meta[2]["name"]["full"]

        players.append({
            "player_id": player_id,
            "name": name,
            "team_key": team_key
        })

    return players


def sum_stats(stats_list):
    totals = defaultdict(float)
    for s in stats_list:
        for c in CATS:
            totals[c] += float(s.get(c, 0))
    return dict(totals)


# =========================
# COLLECT ALL ROSTERS + STATS
# =========================
team_players = defaultdict(list)
team_stats = defaultdict(list)

for team_key in teams:
    roster = get_team_roster(team_key)
    ids = [p["player_id"] for p in roster]

    if not ids:
        continue

    stats = league.player_stats(ids, "season")

    for p, s in zip(roster, stats):
        team_players[team_key].append({**p, **s})
        team_stats[team_key].append(s)

# =========================
# LEAGUE AVERAGES
# =========================
league_totals = [sum_stats(v) for v in team_stats.values()]
league_avg = {
    c: sum(t[c] for t in league_totals) / len(league_totals)
    for c in CATS
}

my_totals = sum_stats(team_stats[my_team_key])

# =========================
# CATEGORY CLASSIFICATION
# =========================
weak = []
soft_strong = []

for c in CATS:
    ratio = my_totals[c] / league_avg[c]
    if ratio < WEAK_MARGIN:
        weak.append(c)
    elif ratio >= SOFT_STRONG_MARGIN:
        soft_strong.append(c)

# =========================
# SAFE TRADE BAIT (LOW WEAK-CAT IMPACT)
# =========================
bait = []

for p in team_players[my_team_key]:
    weak_impact = sum(float(p.get(c, 0)) for c in weak)
    strong_impact = sum(float(p.get(c, 0)) for c in soft_strong)

    if weak_impact < strong_impact:
        bait.append({
            "player_id": p["player_id"],
            "name": p["name"],
            "value_score": round(strong_impact - weak_impact, 1)
        })

bait = sorted(bait, key=lambda x: x["value_score"], reverse=True)[:5]

# =========================
# TRADE TARGET SEARCH
# =========================
recommended = []

for team_key, players in team_players.items():
    if team_key == my_team_key:
        continue

    their_totals = sum_stats(team_stats[team_key])

    # Must be strong where I'm weak
    if not any(their_totals[c] > league_avg[c] for c in weak):
        continue

    for target in players:
        helps = [c for c in weak if float(target.get(c, 0)) > league_avg[c] * 0.2]
        if not helps:
            continue

        for offer in bait:
            recommended.append({
                "trade_partner": team_key,
                "they_receive": offer,
                "you_receive": {
                    "player_id": target["player_id"],
                    "name": target["name"],
                    "helps": helps
                }
            })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "generated": datetime.now(timezone.utc).isoformat(),
    "my_team": my_team_key,
    "trade_analysis": {
        "weak_categories": weak,
        "soft_strong_categories": soft_strong,
        "my_totals": my_totals,
        "league_averages": league_avg,
        "safe_trade_bait": bait,
        "recommended_trades": recommended[:10]
    }
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json updated with trade recommendations")
