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
teams = league.teams()
current_week = league.current_week()

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
    Pull roster + SEASON stats using CURRENT WEEK roster.
    Season totals are embedded in player_stats.
    """
    raw = league.yhandler.get_roster_raw(team_key, current_week)
    players = []

    roster_block = raw["fantasy_content"]["team"][1]["roster"]["0"]["players"]

    for _, item in roster_block.items():
        if _ == "count":
            continue

        pdata = item["player"]
        meta = pdata[0]

        # --- player identifiers ---
        player_id = int(meta[1]["player_id"])
        name = meta[2]["name"]["full"]

        # --- stats (guard for missing blocks) ---
        season_stats = {k: 0.0 for k in STAT_KEYS}

        if len(pdata) > 1 and "player_stats" in pdata[1]:
            for s in pdata[1]["player_stats"]["stats"]:
                stat = s["stat"]
                key = stat["name"]
                if key in STAT_KEYS:
                    season_stats[key] = safe_float(stat["value"])

        players.append({
            "player_id": player_id,
            "name": name,
            "team_key": team_key,
            "season_stats": season_stats
        })

    return players

# =========================
# Pull All Rosters
# =========================
all_rosters = {tk: get_team_roster(tk) for tk in teams.keys()}
my_roster = all_rosters[my_team_key]

# =========================
# Team Totals
# =========================
def team_totals(roster):
    totals = {k: 0.0 for k in STAT_KEYS}
    for p in roster:
        for k in STAT_KEYS:
            totals[k] += p["season_stats"].get(k, 0.0)
    return totals

my_totals = team_totals(my_roster)

league_totals = {k: 0.0 for k in STAT_KEYS}
for roster in all_rosters.values():
    t = team_totals(roster)
    for k in STAT_KEYS:
        league_totals[k] += t[k]

league_averages = {
    k: round(league_totals[k] / len(all_rosters), 2)
    for k in STAT_KEYS
}

# =========================
# Strength / Weakness
# =========================
weak_categories = [k for k in STAT_KEYS if my_totals[k] < league_averages[k]]
strong_categories = [k for k in STAT_KEYS if my_totals[k] > league_averages[k]]

# =========================
# Safe Trade Bait
# =========================
safe_trade_bait = []

for p in my_roster:
    strength_hits = sum(
        p["season_stats"][k] > league_averages[k] / len(my_roster)
        for k in strong_categories
    )

    if strength_hits >= 2:
        safe_trade_bait.append({
            "player_id": p["player_id"],
            "name": p["name"],
            "strengths": strong_categories
        })

# =========================
# Trade Recommendations
# =========================
recommended_trades = []

for team_key, roster in all_rosters.items():
    if team_key == my_team_key:
        continue

    opp_totals = team_totals(roster)

    # Teams strong where you're weak
    opp_strong = [
        k for k in weak_categories
        if opp_totals[k] > league_averages[k]
    ]

    if not opp_strong:
        continue

    for p in roster:
        helps = [
            k for k in opp_strong
            if p["season_stats"][k] > 0
        ]

        if helps:
            score = sum(p["season_stats"][k] for k in helps)
            recommended_trades.append({
                "team_key": team_key,
                "player_id": p["player_id"],
                "name": p["name"],
                "helps": helps,
                "score": round(score, 1)
            })

recommended_trades = sorted(
    recommended_trades,
    key=lambda x: x["score"],
    reverse=True
)[:10]

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
        "recommended_trades": recommended_trades
    }
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json updated with league-wide trade recommendations")
