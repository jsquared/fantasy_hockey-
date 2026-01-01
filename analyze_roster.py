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

STAT_KEYS = ["G", "A", "PPP", "SOG", "FW", "HIT", "BLK"]

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
# HELPERS
# =========================
def safe_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def get_team_roster(team_key):
    """
    Uses yahoo_fantasy_api Team object (stable path)
    """
    team = yfa.Team(oauth, team_key)
    roster = []

    for p in team.roster():
        stats = p.stats() or {}

        season_stats = {}
        for k in STAT_KEYS:
            season_stats[k] = safe_float(stats.get(k))

        roster.append({
            "team_key": team_key,
            "player_id": p.player_id,
            "name": p.name,
            "positions": p.position,
            "season_stats": season_stats
        })

    return roster


def compute_team_totals(roster):
    totals = {k: 0.0 for k in STAT_KEYS}
    for player in roster:
        for k in STAT_KEYS:
            totals[k] += safe_float(player["season_stats"].get(k))
    return totals


# =========================
# COLLECT ALL ROSTERS
# =========================
all_rosters = {}
for tk in teams_meta.keys():
    all_rosters[tk] = get_team_roster(tk)

my_roster = all_rosters[my_team_key]

# =========================
# TEAM TOTALS
# =========================
my_totals = compute_team_totals(my_roster)

league_totals = {k: 0.0 for k in STAT_KEYS}
for roster in all_rosters.values():
    team_totals = compute_team_totals(roster)
    for k in STAT_KEYS:
        league_totals[k] += team_totals[k]

num_teams = len(all_rosters)
league_averages = {
    k: league_totals[k] / num_teams for k in STAT_KEYS
}

# =========================
# CATEGORY STRENGTH
# =========================
weak_categories = []
strong_categories = []

for k in STAT_KEYS:
    if my_totals[k] < league_averages[k]:
        weak_categories.append(k)
    elif my_totals[k] > league_averages[k]:
        strong_categories.append(k)

# =========================
# SAFE TRADE BAIT
# =========================
safe_trade_bait = []

for p in my_roster:
    contribution = 0
    helps = []

    for k in strong_categories:
        v = p["season_stats"].get(k, 0)
        if v > 0:
            contribution += v
            helps.append(k)

    if contribution > 0:
        safe_trade_bait.append({
            "player_id": p["player_id"],
            "name": p["name"],
            "contribution_score": round(contribution, 2),
            "helps": helps
        })

safe_trade_bait = sorted(
    safe_trade_bait,
    key=lambda x: x["contribution_score"],
    reverse=True
)[:10]

# =========================
# FIND TRADE TARGETS
# =========================
recommended_targets = []

for team_key, roster in all_rosters.items():
    if team_key == my_team_key:
        continue

    team_totals = compute_team_totals(roster)

    team_strong = [
        k for k in weak_categories
        if team_totals[k] > league_averages[k]
    ]

    if not team_strong:
        continue

    for p in roster:
        boost = 0
        helps = []

        for k in team_strong:
            v = p["season_stats"].get(k, 0)
            if v > 0:
                boost += v
                helps.append(k)

        if boost > 0:
            recommended_targets.append({
                "team_key": team_key,
                "player_id": p["player_id"],
                "name": p["name"],
                "boost_score": round(boost, 2),
                "helps": helps
            })

recommended_targets = sorted(
    recommended_targets,
    key=lambda x: x["boost_score"],
    reverse=True
)[:15]

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
        "safe_trade_bait": safe_trade_bait,
        "recommended_targets": recommended_targets
    }
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json updated with league-aware trade recommendations")
