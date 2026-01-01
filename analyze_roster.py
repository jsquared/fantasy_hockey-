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

TRACKED_STATS = ["G", "A", "PPP", "SOG", "FW", "HIT", "BLK"]

WEAK_THRESHOLD = 0.90     # < 90% of league avg
STRONG_THRESHOLD = 1.10   # > 110% of league avg

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
# Helpers
# =========================
def get_team_roster(team_key):
    """Safely parse Yahoo raw roster response"""
    raw = league.yhandler.get_roster_raw(team_key)
    players = []

    roster_players = raw["fantasy_content"]["team"][1]["roster"]["0"]["players"]

    for _, p in roster_players.items():
        if _ == "count":
            continue

        pdata = p["player"]
        meta = pdata[0]

        player_key = meta["player_key"]
        player_id = int(player_key.split(".")[-1])

        name = meta["name"]["full"]
        status = meta.get("status", "")
        positions = [pos["position"] for pos in meta.get("eligible_positions", [])]

        players.append({
            "player_id": player_id,
            "name": name,
            "status": status,
            "positions": positions
        })

    return players


def get_season_stats(player_ids):
    if not player_ids:
        return {}

    stats = league.player_stats(player_ids, "season")
    return {p["player_id"]: p for p in stats}


def sum_stats(players):
    totals = defaultdict(float)
    for p in players:
        for stat in TRACKED_STATS:
            val = p["season_stats"].get(stat)
            if isinstance(val, (int, float)):
                totals[stat] += val
    return dict(totals)


# =========================
# COLLECT ROSTERS + STATS
# =========================
team_rosters = {}
team_totals = {}

for team_key in teams_meta:
    roster = get_team_roster(team_key)
    stats_map = get_season_stats([p["player_id"] for p in roster])

    enriched = []
    for p in roster:
        season = stats_map.get(p["player_id"], {})
        enriched.append({**p, "season_stats": season})

    team_rosters[team_key] = enriched
    team_totals[team_key] = sum_stats(enriched)

# =========================
# LEAGUE AVERAGES
# =========================
league_averages = {}
for stat in TRACKED_STATS:
    vals = [team_totals[t].get(stat, 0) for t in team_totals]
    league_averages[stat] = sum(vals) / len(vals)

# =========================
# MY TEAM ANALYSIS
# =========================
my_totals = team_totals[my_team_key]

weak_categories = [
    stat for stat in TRACKED_STATS
    if my_totals.get(stat, 0) < league_averages[stat] * WEAK_THRESHOLD
]

strong_categories = [
    stat for stat in TRACKED_STATS
    if my_totals.get(stat, 0) > league_averages[stat] * STRONG_THRESHOLD
]

# =========================
# SAFE TRADE BAIT (from strengths)
# =========================
safe_trade_bait = []

for p in team_rosters[my_team_key]:
    helps = [s for s in strong_categories if p["season_stats"].get(s, 0) > 0]
    if helps:
        safe_trade_bait.append({
            "player_id": p["player_id"],
            "name": p["name"],
            "contributes_to": helps
        })

# =========================
# FIND MUTUAL TRADE TARGETS
# =========================
recommended_trades = []

for team_key, roster in team_rosters.items():
    if team_key == my_team_key:
        continue

    their_totals = team_totals[team_key]

    # They must be strong where I'm weak
    if not any(
        their_totals.get(stat, 0) > league_averages[stat] * STRONG_THRESHOLD
        for stat in weak_categories
    ):
        continue

    # They must be weak where I'm strong
    if not any(
        their_totals.get(stat, 0) < league_averages[stat] * WEAK_THRESHOLD
        for stat in strong_categories
    ):
        continue

    for p in roster:
        helps_me = [s for s in weak_categories if p["season_stats"].get(s, 0) > 0]
        if helps_me:
            recommended_trades.append({
                "trade_partner": team_key,
                "target_player": {
                    "player_id": p["player_id"],
                    "name": p["name"],
                    "improves": helps_me
                }
            })

# =========================
# OUTPUT
# =========================
output = {
    "league": league.settings()["name"],
    "generated": datetime.now(timezone.utc).isoformat(),
    "my_team": my_team_key,
    "trade_analysis": {
        "weak_categories": weak_categories,
        "strong_categories": strong_categories,
        "my_totals": my_totals,
        "league_averages": league_averages,
        "safe_trade_bait": safe_trade_bait,
        "recommended_trades": recommended_trades
    }
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(output, f, indent=2)

print("✅ docs/roster.json updated with trade recommendations")
