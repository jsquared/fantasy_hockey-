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

# =========================
# STATS WE CARE ABOUT
# =========================
STAT_CATEGORIES = [
    "G", "A", "+/-", "PIM", "PPP", "SHP", "GWG",
    "SOG", "FW", "HIT", "BLK"
]

LOWER_IS_BETTER = {"GA", "GAA", "Shots Against"}

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
current_week = league.current_week()
teams_meta = league.teams()

# =========================
# Helpers
# =========================
def safe_float(val):
    try:
        return float(val)
    except (TypeError, ValueError):
        return 0.0

# =========================
# COLLECT ALL ROSTERS + STATS
# =========================
all_players = []
team_totals = defaultdict(lambda: defaultdict(float))

for team_key, team_info in teams_meta.items():
    team_obj = league.to_team(team_key)
    roster = team_obj.roster(week=current_week)

    player_ids = [p["player_id"] for p in roster]
    stats = league.player_stats(player_ids, req_type="season")

    stats_by_id = {s["player_id"]: s for s in stats}

    for p in roster:
        pid = p["player_id"]
        stat_block = stats_by_id.get(pid, {})

        # accumulate team totals safely
        for stat in STAT_CATEGORIES:
            team_totals[team_key][stat] += safe_float(stat_block.get(stat))

        all_players.append({
            "team_key": team_key,
            "team_name": team_info.get("name", ""),
            "player_id": pid,
            "name": p["name"],
            "positions": p.get("eligible_positions", []),
            "status": p.get("status", ""),
            "season_stats": stat_block
        })

# =========================
# LEAGUE MEDIANS
# =========================
league_medians = {}

for stat in STAT_CATEGORIES:
    values = [team_totals[t][stat] for t in team_totals]
    values.sort()
    league_medians[stat] = values[len(values) // 2] if values else 0

# =========================
# FIND MY WEAK STATS
# =========================
weak_stats = []

for stat in STAT_CATEGORIES:
    my_val = team_totals[my_team_key][stat]
    median = league_medians[stat]

    if stat in LOWER_IS_BETTER:
        if my_val > median:
            weak_stats.append(stat)
    else:
        if my_val < median:
            weak_stats.append(stat)

# =========================
# TRADE TARGETS
# =========================
trade_targets = []

for p in all_players:
    if p["team_key"] == my_team_key:
        continue

    stats = p["season_stats"]

    for stat in weak_stats:
        player_val = safe_float(stats.get(stat))
        my_val = team_totals[my_team_key][stat]

        improves = (
            (stat in LOWER_IS_BETTER and player_val < my_val) or
            (stat not in LOWER_IS_BETTER and player_val > my_val)
        )

        if improves:
            trade_targets.append({
                "player_id": p["player_id"],
                "name": p["name"],
                "from_team": p["team_name"],
                "stat": stat,
                "player_value": player_val,
                "my_team_value": my_val
            })

# sort by biggest improvement
trade_targets.sort(
    key=lambda x: abs(x["player_value"] - x["my_team_value"]),
    reverse=True
)

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "current_week": current_week,
    "my_team_key": my_team_key,
    "lastUpdated": datetime.now(timezone.utc).isoformat(),
    "team_totals": team_totals,
    "league_medians": league_medians,
    "weak_stats": weak_stats,
    "trade_targets": trade_targets[:25],  # top 25
    "players": all_players
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json written successfully")
