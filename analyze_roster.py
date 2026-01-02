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
WEEKS = 12

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
# Helpers
# =========================
def safe_float(v):
    try:
        return float(v)
    except Exception:
        return 0.0

# =========================
# TEAM WEEKLY STATS (KNOWN GOOD)
# =========================
weekly_totals = defaultdict(lambda: defaultdict(float))

for week in range(1, WEEKS + 1):
    raw = league.yhandler.get_scoreboard_raw(league.league_id, week)
    matchups = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

    for _, matchup in matchups.items():
        if _ == "count":
            continue

        teams = matchup["matchup"]["0"]["teams"]
        for _, team_entry in teams.items():
            if _ == "count":
                continue

            team_block = team_entry["team"]
            team_key = team_block[0][0]["team_key"]

            stats = team_block[1]["team_stats"]["stats"]
            for s in stats:
                name = s["stat"]["name"]
                if name in STAT_KEYS:
                    weekly_totals[team_key][name] += safe_float(s["stat"]["value"])

# =========================
# AVERAGES
# =========================
team_averages = {}
for team_key, stats in weekly_totals.items():
    team_averages[team_key] = {
        k: stats[k] / WEEKS for k in STAT_KEYS
    }

league_averages = {
    k: sum(team_averages[t][k] for t in team_averages) / len(team_averages)
    for k in STAT_KEYS
}

my_avgs = team_averages[my_team_key]

# =========================
# CATEGORY ANALYSIS
# =========================
strong_categories = [
    k for k in STAT_KEYS if my_avgs[k] > league_averages[k]
]

weak_categories = [
    k for k in STAT_KEYS if my_avgs[k] < league_averages[k]
]

# =========================
# TRADE PARTNERS
# =========================
trade_partners = []

for team_key, avgs in team_averages.items():
    if team_key == my_team_key:
        continue

    helps_us = [k for k in weak_categories if avgs[k] > league_averages[k]]
    needs_us = [k for k in strong_categories if avgs[k] < league_averages[k]]

    if helps_us and needs_us:
        trade_partners.append({
            "team_key": team_key,
            "they_help_us_in": helps_us,
            "they_need_from_us": needs_us
        })

# =========================
# ROSTER (NAMES ONLY – SAFE)
# =========================
def get_team_players(team_key):
    raw = league.yhandler.get_roster_raw(team_key)
    players = []

    for _, item in raw["fantasy_content"]["team"][1]["roster"]["0"]["players"].items():
        if _ == "count":
            continue

        pdata = item["player"][0]
        name = pdata[2]["name"]["full"]
        pos = pdata[4].get("display_position", "")

        players.append({
            "name": name,
            "position": pos
        })

    return players

my_players = get_team_players(my_team_key)

# =========================
# PLAYER ARCHETYPES
# =========================
def player_profile(player):
    pos = player["position"]
    if "D" in pos:
        return ["HIT", "BLK"]
    if "C" in pos:
        return ["A", "FW"]
    if "LW" in pos or "RW" in pos:
        return ["G", "SOG", "PPP"]
    return []

# =========================
# TRADE SUGGESTIONS
# =========================
trade_suggestions = []

for partner in trade_partners:
    opp_key = partner["team_key"]
    opp_players = get_team_players(opp_key)

    # 1-for-1
    for give in my_players:
        give_cats = player_profile(give)
        if not any(c in strong_categories for c in give_cats):
            continue

        for get in opp_players:
            get_cats = player_profile(get)
            if any(c in weak_categories for c in get_cats):
                trade_suggestions.append({
                    "type": "1-for-1",
                    "partner": opp_key,
                    "we_give": give["name"],
                    "we_get": get["name"],
                    "addresses": get_cats
                })

    # 2-for-1
    give_pool = [
        p for p in my_players
        if any(c in strong_categories for c in player_profile(p))
    ]

    if len(give_pool) >= 2:
        for get in opp_players:
            get_cats = player_profile(get)
            if any(c in weak_categories for c in get_cats):
                trade_suggestions.append({
                    "type": "2-for-1",
                    "partner": opp_key,
                    "we_give": [give_pool[0]["name"], give_pool[1]["name"]],
                    "we_get": get["name"],
                    "addresses": get_cats
                })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "generated": datetime.now(timezone.utc).isoformat(),
    "my_team": my_team_key,
    "trade_analysis": {
        "strong_categories": strong_categories,
        "weak_categories": weak_categories,
        "my_team_averages": my_avgs,
        "league_averages": league_averages,
        "recommended_trade_partners": trade_partners,
        "trade_suggestions": trade_suggestions[:15]
    }
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with full trade recommendations")
