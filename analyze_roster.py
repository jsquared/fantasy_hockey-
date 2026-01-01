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

CATS = ["G", "A", "PPP", "SOG", "FW", "HIT", "BLK"]

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
    """Return list of {player_id, name, team_key}"""
    raw = league.yhandler.get_roster_raw(team_key)

    players = []
    for _, entry in raw["fantasy_content"]["team"][1]["roster"]["0"]["players"].items():
        if _ == "count":
            continue

        pdata = entry["player"]
        meta = pdata[0]

        # player_id is ALWAYS inside meta as string
        player_id = int(meta["player_id"])
        name = meta["name"]["full"]

        players.append({
            "player_id": player_id,
            "name": name,
            "team_key": team_key
        })

    return players


def sum_stats(players):
    totals = defaultdict(float)
    ids = [p["player_id"] for p in players]

    stats = league.player_stats(ids, "season")

    for s in stats:
        for c in CATS:
            if c in s and isinstance(s[c], (int, float)):
                totals[c] += float(s[c])

    return dict(totals)


# =========================
# COLLECT ROSTERS
# =========================
team_rosters = {}
team_totals = {}

for team_key in teams.keys():
    roster = get_team_roster(team_key)
    team_rosters[team_key] = roster
    team_totals[team_key] = sum_stats(roster)

# =========================
# LEAGUE AVERAGES
# =========================
league_avgs = {}
for c in CATS:
    league_avgs[c] = sum(
        team_totals[t].get(c, 0) for t in team_totals
    ) / len(team_totals)

# =========================
# MY TEAM ANALYSIS
# =========================
my_totals = team_totals[my_team_key]

weak_cats = [
    c for c in CATS
    if my_totals.get(c, 0) < league_avgs[c]
]

strong_cats = [
    c for c in CATS
    if my_totals.get(c, 0) > league_avgs[c] * 1.10
]

# =========================
# FIND TRADE TARGETS
# =========================
targets = []

for team_key, totals in team_totals.items():
    if team_key == my_team_key:
        continue

    helps = [c for c in weak_cats if totals.get(c, 0) > league_avgs[c]]
    needs = [c for c in strong_cats if totals.get(c, 0) < league_avgs[c]]

    if not helps or not needs:
        continue

    for player in team_rosters[team_key]:
        stats = league.player_stats([player["player_id"]], "season")[0]

        boost = sum(stats.get(c, 0) for c in helps if c in stats)
        if boost <= 0:
            continue

        targets.append({
            "from_team": team_key,
            "player_id": player["player_id"],
            "name": player["name"],
            "helps": helps,
            "boost_score": round(boost, 1)
        })

targets = sorted(targets, key=lambda x: x["boost_score"], reverse=True)[:10]

# =========================
# SAFE TRADE BAIT (YOUR TEAM)
# =========================
safe_bait = []

for player in team_rosters[my_team_key]:
    stats = league.player_stats([player["player_id"]], "season")[0]

    contrib = sum(stats.get(c, 0) for c in weak_cats if c in stats)
    surplus = sum(stats.get(c, 0) for c in strong_cats if c in stats)

    if surplus > contrib:
        safe_bait.append({
            "player_id": player["player_id"],
            "name": player["name"],
            "surplus_score": round(surplus - contrib, 1)
        })

safe_bait = sorted(safe_bait, key=lambda x: x["surplus_score"], reverse=True)[:8]

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "my_team": my_team_key,
    "generated": datetime.now(timezone.utc).isoformat(),
    "trade_analysis": {
        "weak_categories": weak_cats,
        "strong_categories": strong_cats,
        "my_totals": my_totals,
        "league_averages": league_avgs,
        "recommended_targets": targets,
        "safe_trade_bait": safe_bait
    }
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json written successfully")
