import os
import json
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
from collections import defaultdict

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"
SWING_THRESHOLD = 0.10  # 10%

os.makedirs("docs", exist_ok=True)

# =========================
# STAT MAP
# =========================
STAT_KEYS = ["G", "A", "PPP", "SOG", "FW", "HIT", "BLK"]

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
teams_meta = league.teams()
current_week = league.current_week()

# =========================
# Helper Functions
# =========================
def get_team_roster(team_key):
    roster_raw = league.yhandler.get_roster_raw(team_key)
    roster = []

    # Ensure player list exists
    players_list = roster_raw.get("player") if isinstance(roster_raw, dict) else roster_raw
    if not isinstance(players_list, list):
        return roster

    for item in players_list:
        # Handle structure variations
        player_data = item.get("player") if isinstance(item, dict) and "player" in item else item
        if isinstance(player_data, list):
            player_meta = player_data[0] if player_data else {}
        elif isinstance(player_data, dict):
            player_meta = player_data
        else:
            continue

        if "player_id" not in player_meta:
            continue

        roster.append({
            "team_key": team_key,
            "player_id": int(player_meta["player_id"]),
            "player_key": player_meta.get("player_key", ""),
            "name": player_meta.get("name", {}).get("full", "Unknown") if isinstance(player_meta.get("name"), dict) else player_meta.get("name", "Unknown"),
            "positions": [p["position"] for p in player_meta.get("eligible_positions", [])] if player_meta.get("eligible_positions") else [],
            "status": player_meta.get("status", ""),
            "season_stats": player_meta.get("player_stats", {})
        })

    return roster

def compute_team_totals(roster):
    totals = defaultdict(float)
    for player in roster:
        stats = player.get("season_stats", {})
        for k in STAT_KEYS:
            try:
                totals[k] += float(stats.get(k, 0))
            except (ValueError, TypeError):
                totals[k] += 0
    return totals

def analyze_trades(my_totals, league_totals, all_rosters):
    weak_cats = []
    strong_cats = []
    recommended_targets = []
    safe_trade_bait = []

    # Identify weak and strong categories
    for k in STAT_KEYS:
        my_val = my_totals.get(k, 0)
        league_avg = league_totals.get(k, 0) / len(all_rosters)
        if my_val < league_avg:
            weak_cats.append(k)
        else:
            strong_cats.append(k)

    # Identify safe trade bait (players contributing minimally to strong categories)
    my_roster = all_rosters[my_team_key]
    for player in my_roster:
        contribution = sum(player.get("season_stats", {}).get(cat, 0) for cat in strong_cats)
        if contribution < 0.05 * sum(my_totals.get(cat, 1) for cat in strong_cats):
            safe_trade_bait.append(player)

    # Recommend trades from other teams who are strong in our weak categories
    for tk, roster in all_rosters.items():
        if tk == my_team_key:
            continue
        for player in roster:
            helps = []
            for cat in weak_cats:
                val = player.get("season_stats", {}).get(cat, 0)
                league_avg = league_totals.get(cat, 0) / len(all_rosters)
                if val > league_avg:
                    helps.append(cat)
            if helps:
                boost_score = sum(player.get("season_stats", {}).get(c, 0) for c in helps)
                recommended_targets.append({
                    "team_key": tk,
                    "player_id": player["player_id"],
                    "name": player["name"],
                    "boost_score": boost_score,
                    "helps": helps
                })

    return weak_cats, strong_cats, recommended_targets, safe_trade_bait

# =========================
# Collect rosters
# =========================
all_rosters = {}
league_totals = defaultdict(float)

for tk in teams_meta.keys():
    roster = get_team_roster(tk)
    all_rosters[tk] = roster
    team_totals = compute_team_totals(roster)
    for k in STAT_KEYS:
        league_totals[k] += team_totals.get(k, 0)

# =========================
# My Team Analysis
# =========================
my_totals = compute_team_totals(all_rosters[my_team_key])
weak_cats, strong_cats, recommended_targets, safe_trade_bait = analyze_trades(my_totals, league_totals, all_rosters)

# =========================
# Output
# =========================
payload = {
    "league": league.settings()["name"],
    "generated": datetime.now(timezone.utc).isoformat(),
    "my_team": my_team_key,
    "trade_analysis": {
        "weak_categories": weak_cats,
        "strong_categories": strong_cats,
        "my_totals": my_totals,
        "league_averages": {k: league_totals[k] / len(all_rosters) for k in STAT_KEYS},
        "recommended_targets": recommended_targets,
        "safe_trade_bait": safe_trade_bait
    }
}

with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json updated with roster, stats, and trade recommendations")
