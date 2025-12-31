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
WEEKS = 12
SWING_THRESHOLD = 0.10  # 10%

# =========================
# STAT MAP
# =========================
STAT_MAP = {
    "G": "Goals",
    "A": "Assists",
    "+/-": "+/-",
    "PIM": "PIM",
    "PPP": "PPP",
    "SHP": "SHP",
    "GWG": "GWG",
    "SOG": "SOG",
    "FW": "FW",
    "HIT": "Hits",
    "BLK": "Blocks",
    "W": "Wins",
    "GA": "GA",
    "GAA": "GAA",
    "Shots Against": "Shots Against",
    "Saves": "Saves",
    "SV%": "SV%",
    "Shutouts": "Shutouts"
}

LOWER_IS_BETTER = {"GA", "GAA", "Shots Against"}

# =========================
# OAuth
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
# Get roster and player stats
# =========================
roster_data = []

for team_key, team_info in teams_meta.items():
    team_obj = league.to_team(team_key)
    player_entries = team_obj.roster(week=current_week)

    player_ids = [p["player_id"] for p in player_entries]
    stats = league.player_stats(player_ids, req_type="season")

    for p, s in zip(player_entries, stats):
        roster_data.append({
            "team_key": team_key,
            "player_id": p["player_id"],
            "name": p["name"],
            "positions": p.get("eligible_positions", []),
            "status": p.get("status", ""),
            "team": team_info.get("name", ""),
            "season_stats": s
        })

# =========================
# Compute league averages and trends
# =========================
avg_stats = defaultdict(dict)
trends = defaultdict(dict)

for stat_name in STAT_MAP.values():
    values_by_team = {}
    for team_key, team_info in teams_meta.items():
        team_obj = league.to_team(team_key)
        player_entries = team_obj.roster(week=current_week)
        player_ids = [p["player_id"] for p in player_entries]
        stats = league.player_stats(player_ids, req_type="season")

        # sum stats across players for team total
        team_total = 0
        count = 0
        for s in stats:
            v = s.get(stat_name)
            if v is not None:
                team_total += v
                count += 1
        if count > 0:
            values_by_team[team_key] = team_total

    # compute average across all teams
    for team_key in values_by_team:
        avg_stats[team_key][stat_name] = values_by_team[team_key]
    # league trend: compare your team vs league median
    team_values = list(values_by_team.values())
    median = sorted(team_values)[len(team_values)//2] if team_values else 0
    for team_key, total in values_by_team.items():
        trends[team_key][stat_name] = total - median

# =========================
# Identify weak stats in your team
# =========================
weak_stats = []
for stat_name in STAT_MAP.values():
    if my_team_key not in avg_stats:
        continue
    my_val = avg_stats[my_team_key].get(stat_name, 0)
    team_vals = [v.get(stat_name, 0) for k, v in avg_stats.items() if k != my_team_key]
    if not team_vals:
        continue
    median = sorted(team_vals)[len(team_vals)//2]
    if (stat_name in LOWER_IS_BETTER and my_val > median) or \
       (stat_name not in LOWER_IS_BETTER and my_val < median):
        weak_stats.append(stat_name)

# =========================
# Recommend trade targets
# =========================
trade_targets = []
for team_key, team_info in teams_meta.items():
    if team_key == my_team_key:
        continue
    team_obj = league.to_team(team_key)
    player_entries = team_obj.roster(week=current_week)
    player_ids = [p["player_id"] for p in player_entries]
    stats = league.player_stats(player_ids, req_type="season")

    for p, s in zip(player_entries, stats):
        for stat_name in weak_stats:
            player_val = s.get(stat_name)
            if player_val is None:
                continue
            my_val = avg_stats[my_team_key].get(stat_name, 0)
            if (stat_name in LOWER_IS_BETTER and player_val < my_val) or \
               (stat_name not in LOWER_IS_BETTER and player_val > my_val):
                trade_targets.append({
                    "player_id": p["player_id"],
                    "name": p["name"],
                    "current_team": team_info.get("name", ""),
                    "stat_to_improve": stat_name,
                    "value": player_val
                })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "current_week": current_week,
    "lastUpdated": datetime.now(timezone.utc).isoformat(),
    "players": roster_data,
    "weak_stats": weak_stats,
    "trade_targets": trade_targets
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json updated with player stats, weak stats, and trade recommendations")
