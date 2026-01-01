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
def safe_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0


def get_team_roster(team_key):
    """
    Uses supported raw handler call and defensively parses players.
    """
    raw = league.yhandler.get_roster_raw(team_key)
    players = []

    team_block = raw["fantasy_content"]["team"][1]["roster"]["0"]["players"]

    for _, p in team_block.items():
        if _ == "count":
            continue

        pdata = p["player"]
        meta = pdata[0]
        stats_block = pdata[1].get("player_stats", {}).get("stats", [])

        player_id = int(meta[0]["player_id"])
        name = meta[2]["name"]["full"]

        positions = []
        for pos in meta:
            if isinstance(pos, dict) and "eligible_positions" in pos:
                positions = [x["position"] for x in pos["eligible_positions"]]

        stats = {}
        for s in stats_block:
            stat = s["stat"]
            stat_name = stat.get("display_name")
            if stat_name in TRACKED_STATS:
                stats[stat_name] = safe_float(stat.get("value"))

        players.append({
            "team_key": team_key,
            "player_id": player_id,
            "name": name,
            "positions": positions,
            "season_stats": stats
        })

    return players


# =========================
# COLLECT ALL ROSTERS
# =========================
all_players = []
team_totals = defaultdict(lambda: defaultdict(float))

for team_key in teams_meta.keys():
    roster = get_team_roster(team_key)
    all_players.extend(roster)

    for p in roster:
        for stat, val in p["season_stats"].items():
            team_totals[team_key][stat] += val

# =========================
# LEAGUE AVERAGES
# =========================
league_averages = {}
for stat in TRACKED_STATS:
    league_averages[stat] = (
        sum(team_totals[t][stat] for t in team_totals) / len(team_totals)
    )

my_totals = dict(team_totals[my_team_key])

# =========================
# WEAK / STRONG CATEGORIES
# =========================
weak_categories = []
strong_categories = []

for stat in TRACKED_STATS:
    if my_totals[stat] < league_averages[stat] * WEAK_THRESHOLD:
        weak_categories.append(stat)
    elif my_totals[stat] > league_averages[stat] * STRONG_THRESHOLD:
        strong_categories.append(stat)

# =========================
# TRADE TARGETS
# =========================
targets = []

for p in all_players:
    if p["team_key"] == my_team_key:
        continue

    helps = []
    boost = 0.0

    for stat in weak_categories:
        val = p["season_stats"].get(stat, 0)
        if val > 0:
            helps.append(stat)
            boost += val

    if helps and boost > 0:
        targets.append({
            "team_key": p["team_key"],
            "player_id": p["player_id"],
            "name": p["name"],
            "boost_score": round(boost, 1),
            "helps": helps
        })

targets = sorted(targets, key=lambda x: x["boost_score"], reverse=True)[:15]

# =========================
# SAFE TRADE BAIT
# =========================
safe_bait = []

my_players = [p for p in all_players if p["team_key"] == my_team_key]

for p in my_players:
    contributes = False
    for stat in strong_categories:
        if p["season_stats"].get(stat, 0) > league_averages[stat] * 0.05:
            contributes = True

    if contributes:
        safe_bait.append({
            "player_id": p["player_id"],
            "name": p["name"],
            "positions": p["positions"]
        })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "generated": datetime.now(timezone.utc).isoformat(),
    "my_team": my_team_key,
    "trade_analysis": {
        "weak_categories": weak_categories,
        "strong_categories": strong_categories,
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
