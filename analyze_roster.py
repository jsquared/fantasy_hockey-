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
SWING_THRESHOLD = 0.10  # 10%

# =========================
# STAT MAP
# =========================
STAT_MAP = {
    "G": "G",
    "A": "A",
    "PPP": "PPP",
    "SOG": "SOG",
    "FW": "FW",
    "HIT": "HIT",
    "BLK": "BLK"
}

LOWER_IS_BETTER = set()  # All higher is better for counting stats

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

# =========================
# Helpers
# =========================
def get_team_roster(team_key):
    roster_raw = league.yhandler.get_roster_raw(team_key)
    roster = []
    for item in roster_raw:
        player_data = item["player"]
        if isinstance(player_data, list):
            player_meta = player_data[0]
        elif isinstance(player_data, dict):
            player_meta = player_data
        else:
            continue

        roster.append({
            "team_key": team_key,
            "player_id": int(player_meta["player_id"]),
            "player_key": player_meta.get("player_key", ""),
            "name": player_meta["name"]["full"],
            "positions": [p["position"] for p in player_meta.get("eligible_positions", [])],
            "status": player_meta.get("status", ""),
            "season_stats": item.get("player_stats", {})
        })
    return roster

def compute_team_totals(roster):
    totals = defaultdict(float)
    for p in roster:
        stats = p.get("season_stats", {})
        for k in STAT_MAP.keys():
            try:
                totals[k] += float(stats.get(k, 0))
            except (TypeError, ValueError):
                totals[k] += 0
    return totals

def identify_weak_categories(my_totals, league_averages):
    weak = []
    for stat in STAT_MAP.keys():
        if my_totals.get(stat, 0) < league_averages.get(stat, 0):
            weak.append(stat)
    return weak

def identify_safe_trade_bait(roster, my_totals, league_averages):
    bait = []
    for p in roster:
        contributes = 0
        for stat in STAT_MAP.keys():
            player_stat = p.get("season_stats", {}).get(stat, 0)
            if player_stat < league_averages.get(stat, 0) * 0.5:  # low contribution
                contributes += 1
        if contributes >= 2:
            bait.append({"player_id": p["player_id"], "name": p["name"]})
    return bait

def find_trade_targets(rosters, weak_categories, my_totals):
    recommended = []
    for team_key, roster in rosters.items():
        if team_key == my_team_key:
            continue
        for p in roster:
            helps = []
            boost_score = 0
            for stat in weak_categories:
                player_stat = p.get("season_stats", {}).get(stat, 0)
                league_avg = my_totals.get(stat, 0)
                if player_stat > league_avg:
                    helps.append(stat)
                    boost_score += player_stat - league_avg
            if helps:
                recommended.append({
                    "team_key": team_key,
                    "player_id": p["player_id"],
                    "name": p["name"],
                    "boost_score": boost_score,
                    "helps": helps
                })
    recommended.sort(key=lambda x: x["boost_score"], reverse=True)
    return recommended[:10]  # top 10 trade targets

# =========================
# MAIN
# =========================
all_rosters = {}
for tk in teams_meta.keys():
    all_rosters[tk] = get_team_roster(tk)

my_roster = all_rosters[my_team_key]
my_totals = compute_team_totals(my_roster)

# League averages
league_totals = defaultdict(float)
num_teams = len(all_rosters)
for tk, roster in all_rosters.items():
    team_totals = compute_team_totals(roster)
    for k, v in team_totals.items():
        league_totals[k] += v
league_averages = {k: v / num_teams for k, v in league_totals.items()}

weak_categories = identify_weak_categories(my_totals, league_averages)
safe_trade_bait = identify_safe_trade_bait(my_roster, my_totals, league_averages)
recommended_trades = find_trade_targets(all_rosters, weak_categories, league_averages)

payload = {
    "league": league.settings()["name"],
    "generated": datetime.now(timezone.utc).isoformat(),
    "my_team": my_team_key,
    "trade_analysis": {
        "weak_categories": weak_categories,
        "strong_categories": [],
        "my_totals": my_totals,
        "league_averages": league_averages,
        "safe_trade_bait": safe_trade_bait,
        "recommended_trades": recommended_trades
    }
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json updated successfully!")
