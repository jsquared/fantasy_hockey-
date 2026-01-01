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

    roster = raw["fantasy_content"]["team"][1]["roster"]["0"]["players"]
    for _, p in roster.items():
        if _ == "count":
            continue

        player = p["player"]
        players.append({
            "team_key": team_key,
            "player_id": int(player[0][1]["player_id"]),
            "name": player[0][2]["name"]["full"],
            "positions": [pos["position"] for pos in player[0][4]["eligible_positions"]],
            "status": player[0][5].get("status", "")
        })

    return players

def sum_categories(stats):
    totals = defaultdict(float)
    for p in stats:
        for c in CATEGORIES:
            v = p.get(c)
            if isinstance(v, (int, float)):
                totals[c] += v
    return dict(totals)

# =========================
# COLLECT ALL ROSTERS
# =========================
all_players = []
team_players = defaultdict(list)

for team_key in teams.keys():
    roster = get_team_roster(team_key)
    team_players[team_key] = roster
    all_players.extend(roster)

# =========================
# PLAYER SEASON STATS
# =========================
player_ids = [p["player_id"] for p in all_players]
player_stats = league.player_stats(player_ids, "season")

stats_by_id = {p["player_id"]: p for p in player_stats}

for p in all_players:
    p["season_stats"] = stats_by_id.get(p["player_id"], {})

# =========================
# TEAM TOTALS
# =========================
team_totals = {}

for team_key, roster in team_players.items():
    team_totals[team_key] = sum_categories(
        [p["season_stats"] for p in roster]
    )

# =========================
# LEAGUE AVERAGES
# =========================
league_averages = {}
for c in CATEGORIES:
    league_averages[c] = sum(
        team_totals[t][c] for t in team_totals
    ) / len(team_totals)

my_totals = team_totals[my_team_key]

# =========================
# WEAK / STRONG CATEGORIES
# =========================
weak = [c for c in CATEGORIES if my_totals[c] < league_averages[c]]
strong = [c for c in CATEGORIES if my_totals[c] > league_averages[c] * 1.1]

# =========================
# TRADE TARGET IDENTIFICATION
# =========================
targets = []

for team_key, roster in team_players.items():
    if team_key == my_team_key:
        continue

    if not any(team_totals[team_key][c] > league_averages[c] for c in weak):
        continue

    for p in roster:
        stats = p["season_stats"]
        boost = 0
        helps = []

        for c in weak:
            v = stats.get(c)
            if isinstance(v, (int, float)) and v > league_averages[c] / len(roster):
                boost += v
                helps.append(c)

        if boost > 0:
            targets.append({
                "team_key": team_key,
                "player_id": p["player_id"],
                "name": p["name"],
                "boost_score": round(boost, 2),
                "helps": helps
            })

targets = sorted(targets, key=lambda x: x["boost_score"], reverse=True)[:15]

# =========================
# SAFE TRADE BAIT (YOUR TEAM)
# =========================
safe_bait = []

for p in team_players[my_team_key]:
    stats = p["season_stats"]
    weak_help = any(stats.get(c, 0) > 0 for c in weak)

    if weak_help:
        continue

    hurts_strong = False
    for c in strong:
        if my_totals[c] - stats.get(c, 0) < league_averages[c]:
            hurts_strong = True
            break

    if not hurts_strong:
        value = sum(stats.get(c, 0) for c in strong)
        safe_bait.append({
            "player_id": p["player_id"],
            "name": p["name"],
            "value_in_strong_cats": round(value, 2)
        })

safe_bait = sorted(safe_bait, key=lambda x: x["value_in_strong_cats"])[:10]

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
        "league_averages": league_averages,
        "recommended_targets": targets,
        "safe_trade_bait": safe_bait
    }
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json updated with trade recommendations")
