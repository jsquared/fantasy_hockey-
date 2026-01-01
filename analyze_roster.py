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

TRACK_STATS = ["G", "A", "PPP", "SOG", "FW", "HIT", "BLK"]

# =========================
# OAuth (GitHub safe)
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
def safe_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def get_team_roster(team_key):
    """
    Uses YHandler.get_roster_raw (DOCUMENTED)
    Returns list of player dicts with guaranteed player_id
    """
    raw = league.yhandler.get_roster_raw(team_key)
    players = []

    for _, entry in raw["fantasy_content"]["team"][1]["roster"]["0"]["players"].items():
        if _ == "count":
            continue

        pdata = entry["player"]
        meta = pdata[0]

        player_id = int(meta["player_id"])
        name = meta["name"]["full"]

        positions = []
        if "eligible_positions" in meta:
            positions = [p["position"] for p in meta["eligible_positions"]]

        players.append({
            "player_id": player_id,
            "name": name,
            "positions": positions
        })

    return players


def sum_stats(stat_rows):
    totals = defaultdict(float)
    for row in stat_rows:
        for s in TRACK_STATS:
            if s in row:
                totals[s] += safe_float(row[s])
    return dict(totals)


# =========================
# COLLECT ALL ROSTERS + STATS
# =========================
team_rosters = {}
team_totals = {}
team_players = {}

for team_key in teams_meta.keys():
    roster = get_team_roster(team_key)
    team_players[team_key] = roster

    ids = [p["player_id"] for p in roster]
    if not ids:
        continue

    stats = league.player_stats(ids, "season")
    team_totals[team_key] = sum_stats(stats)

# =========================
# LEAGUE AVERAGES
# =========================
league_avg = {}
for stat in TRACK_STATS:
    league_avg[stat] = sum(
        team_totals[t].get(stat, 0)
        for t in team_totals
    ) / len(team_totals)

my_totals = team_totals[my_team_key]

# =========================
# STRENGTH / WEAKNESS
# =========================
weak = [s for s in TRACK_STATS if my_totals.get(s, 0) < league_avg[s]]
strong = [s for s in TRACK_STATS if my_totals.get(s, 0) > league_avg[s]]

# =========================
# FIND TRADE PARTNERS
# =========================
trade_targets = []

for team_key, totals in team_totals.items():
    if team_key == my_team_key:
        continue

    helps = [s for s in weak if totals.get(s, 0) > league_avg[s]]
    wants = [s for s in strong if totals.get(s, 0) < league_avg[s]]

    if not helps or not wants:
        continue

    for p in team_players[team_key]:
        pstats = league.player_stats([p["player_id"]], "season")[0]
        boost = sum(safe_float(pstats.get(s, 0)) for s in helps)

        if boost <= 0:
            continue

        trade_targets.append({
            "team_key": team_key,
            "player_id": p["player_id"],
            "name": p["name"],
            "helps": helps,
            "their_needs": wants,
            "boost_score": round(boost, 1)
        })

trade_targets.sort(key=lambda x: x["boost_score"], reverse=True)

# =========================
# SAFE TRADE BAIT (YOU)
# =========================
safe_trade_bait = []

for p in team_players[my_team_key]:
    pstats = league.player_stats([p["player_id"]], "season")[0]
    contribution = sum(safe_float(pstats.get(s, 0)) for s in strong)

    if contribution > 0:
        safe_trade_bait.append({
            "player_id": p["player_id"],
            "name": p["name"],
            "supports": strong,
            "value_score": round(contribution, 1)
        })

safe_trade_bait.sort(key=lambda x: x["value_score"])

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
        "recommended_targets": trade_targets[:15],
        "safe_trade_bait": safe_trade_bait[:10]
    }
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with league-aware trade recommendations")
