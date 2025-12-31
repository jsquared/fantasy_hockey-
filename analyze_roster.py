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

TARGET_STATS = {
    "G", "A", "PPP", "SOG", "FW", "HIT", "BLK"
}

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
teams_meta = league.teams()

# =========================
# LOAD EXISTING ROSTER FILE
# =========================
with open(OUTPUT_FILE) as f:
    roster_data = json.load(f)

players = roster_data["players"]

# =========================
# MY TEAM TOTALS
# =========================
my_totals = defaultdict(float)

for p in players:
    stats = p.get("season_stats", {})
    for k, v in stats.items():
        if k in TARGET_STATS and isinstance(v, (int, float)):
            my_totals[k] += v

# =========================
# LEAGUE TOTALS
# =========================
league_totals = defaultdict(list)

for team_key in teams_meta.keys():
    team = league.to_team(team_key)
    roster = team.roster()

    ids = []
    meta = {}

    for p in roster:
        pid = int(p["player_id"])
        ids.append(pid)
        meta[pid] = p

    if not ids:
        continue

    stats = league.player_stats(ids, "season")

    for s in stats:
        for k in TARGET_STATS:
            v = s.get(k)
            if isinstance(v, (int, float)):
                league_totals[(team_key, k)].append(v)

# =========================
# LEAGUE AVERAGES
# =========================
league_avgs = defaultdict(float)

for stat in TARGET_STATS:
    values = []
    for (team_key, k), vals in league_totals.items():
        if k == stat:
            values.append(sum(vals))
    if values:
        league_avgs[stat] = sum(values) / len(values)

# =========================
# IDENTIFY WEAK CATEGORIES
# =========================
weak_stats = []

for stat in TARGET_STATS:
    my_val = my_totals.get(stat, 0)
    avg = league_avgs.get(stat, 0)
    if my_val < avg * 0.9:
        weak_stats.append(stat)

# =========================
# FIND TRADE TARGETS
# =========================
trade_targets = []

for team_key in teams_meta:
    if team_key == my_team_key:
        continue

    team = league.to_team(team_key)
    roster = team.roster()

    ids = [int(p["player_id"]) for p in roster]
    stats = league.player_stats(ids, "season")

    for s in stats:
        score = 0
        for stat in weak_stats:
            v = s.get(stat)
            if isinstance(v, (int, float)):
                score += v

        if score > 0:
            trade_targets.append({
                "team_key": team_key,
                "player_id": s["player_id"],
                "name": s["name"],
                "boost_score": round(score, 2),
                "helps": weak_stats
            })

trade_targets.sort(key=lambda x: x["boost_score"], reverse=True)

# =========================
# OUTPUT
# =========================
roster_data["trade_analysis"] = {
    "weak_categories": weak_stats,
    "my_totals": dict(my_totals),
    "league_averages": dict(league_avgs),
    "recommended_targets": trade_targets[:10],
    "generated": datetime.now(timezone.utc).isoformat()
}

with open(OUTPUT_FILE, "w") as f:
    json.dump(roster_data, f, indent=2)

print("docs/roster.json updated with trade recommendations")
