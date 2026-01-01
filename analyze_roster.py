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
all_team_keys = list(teams_meta.keys())

# =========================
# ROSTER FUNCTIONS
# =========================
def get_team_roster(team_key):
    roster_raw = league.yhandler.get_roster_raw(team_key)
    roster = []
    for item in roster_raw:
        player_meta = item["player"][0]
        stats = item.get("player_stats", {})
        roster.append({
            "team_key": team_key,
            "player_id": int(player_meta["player_id"]),
            "player_key": player_meta["player_key"],
            "name": player_meta["name"]["full"],
            "positions": [p["position"] for p in player_meta.get("eligible_positions", [])],
            "status": player_meta.get("status", ""),
            "season_stats": stats
        })
    return roster

# =========================
# LEAGUE STATS
# =========================
def get_team_totals(roster):
    totals = defaultdict(float)
    for player in roster:
        stats = player.get("season_stats", {})
        for k, v in stats.items():
            if isinstance(v, (int, float)):
                totals[k] += v
    return totals

def calculate_league_averages():
    totals = defaultdict(list)
    for tk in all_team_keys:
        roster = get_team_roster(tk)
        team_totals = get_team_totals(roster)
        for stat, value in team_totals.items():
            totals[stat].append(value)
    league_avg = {stat: sum(vals)/len(vals) for stat, vals in totals.items()}
    return league_avg

# =========================
# TRADE ANALYSIS
# =========================
def analyze_roster(roster, league_avg):
    my_totals = get_team_totals(roster)
    weak_categories = [stat for stat, val in my_totals.items() if val < league_avg.get(stat, val)]
    strong_categories = [stat for stat, val in my_totals.items() if val > league_avg.get(stat, val)]

    # Safe trade bait = players that help weak categories least
    safe_trade_bait = []
    for p in roster:
        score = sum(p.get("season_stats", {}).get(stat, 0) for stat in weak_categories)
        if score < 0.5 * sum(my_totals.get(stat, 0) for stat in weak_categories):
            safe_trade_bait.append(p)

    # Recommended targets = players from other teams that boost weak categories
    recommended_trades = []
    for tk in all_team_keys:
        if tk == my_team_key:
            continue
        other_roster = get_team_roster(tk)
        for p in other_roster:
            boost_stats = [stat for stat in weak_categories if p.get("season_stats", {}).get(stat, 0) > league_avg.get(stat, 0)]
            if boost_stats:
                recommended_trades.append({
                    "team_key": tk,
                    "player_id": p["player_id"],
                    "name": p["name"],
                    "helps": boost_stats,
                    "boost_score": sum(p["season_stats"].get(stat, 0) for stat in boost_stats)
                })
    return weak_categories, strong_categories, my_totals, safe_trade_bait, recommended_trades

# =========================
# MAIN
# =========================
my_roster = get_team_roster(my_team_key)
league_avg = calculate_league_averages()

weak_categories, strong_categories, my_totals, safe_trade_bait, recommended_trades = analyze_roster(my_roster, league_avg)

payload = {
    "league": league.settings()["name"],
    "generated": datetime.now(timezone.utc).isoformat(),
    "my_team": my_team_key,
    "trade_analysis": {
        "weak_categories": weak_categories,
        "strong_categories": strong_categories,
        "my_totals": my_totals,
        "league_averages": league_avg,
        "safe_trade_bait": safe_trade_bait,
        "recommended_trades": recommended_trades
    }
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json updated with roster, stats, and trade analysis")
