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

STAT_MAP = {
    "G": "1",
    "A": "2",
    "PPP": "8",
    "SOG": "14",
    "FW": "16",
    "HIT": "31",
    "BLK": "32",
}

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

def extract_team_week_stats(team_block):
    stats = {}
    for item in team_block[1]["team_stats"]["stats"]:
        stat_id = str(item["stat"]["stat_id"])
        stats[stat_id] = safe_float(item["stat"]["value"])
    return stats

# =========================
# WEEKLY TEAM STATS
# =========================
weekly = defaultdict(dict)

for week in range(1, WEEKS + 1):
    raw = league.yhandler.get_scoreboard_raw(league.league_id, week)
    matchups = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

    for _, matchup in matchups.items():
        if _ == "count":
            continue
        teams_block = matchup["matchup"]["0"]["teams"]
        for _, team_entry in teams_block.items():
            if _ == "count":
                continue
            team = team_entry["team"]
            team_key = team[0][0]["team_key"]
            weekly[team_key].setdefault("weeks", []).append(
                extract_team_week_stats(team)
            )

# =========================
# AVERAGES
# =========================
team_avgs = defaultdict(dict)

for team_key, data in weekly.items():
    for cat, stat_id in STAT_MAP.items():
        vals = [w.get(stat_id, 0) for w in data["weeks"]]
        team_avgs[team_key][cat] = sum(vals) / len(vals) if vals else 0.0

league_avgs = {
    cat: sum(team_avgs[t][cat] for t in team_avgs) / len(team_avgs)
    for cat in STAT_MAP
}

my_avgs = team_avgs[my_team_key]

strong_cats = [c for c in STAT_MAP if my_avgs[c] > league_avgs[c]]
weak_cats = [c for c in STAT_MAP if my_avgs[c] < league_avgs[c]]

# =========================
# TRADE PARTNERS
# =========================
trade_partners = []

for team_key, avgs in team_avgs.items():
    if team_key == my_team_key:
        continue

    helps_us = [c for c in weak_cats if avgs[c] > league_avgs[c]]
    needs_from_us = [c for c in strong_cats if avgs[c] < league_avgs[c]]

    if helps_us and needs_from_us:
        trade_partners.append({
            "team_key": team_key,
            "they_help_us_in": helps_us,
            "they_need_from_us": needs_from_us
        })

# =========================
# PLAYER POOLS (RAW ROSTERS)
# =========================
def get_roster(team_key):
    raw = league.yhandler.get_roster_raw(team_key)
    players = []

    for _, item in raw["fantasy_content"]["team"][1]["roster"]["0"]["players"].items():
        if _ == "count":
            continue
        meta = item["player"][0]
        players.append({
            "player_id": int(meta[1]["player_id"]),
            "name": meta[2]["name"]["full"]
        })

    return players

my_players = get_roster(my_team_key)
all_rosters = {tk: get_roster(tk) for tk in teams}

# =========================
# SAFE TRADE BAIT
# =========================
safe_trade_bait = my_players[:5]  # conservative: top 5 movable assets

# =========================
# TRADE IDEAS
# =========================
trade_ideas = []

for partner in trade_partners:
    tk = partner["team_key"]
    targets = all_rosters[tk][:5]

    # 1-for-1
    for give in safe_trade_bait[:3]:
        for get in targets[:3]:
            trade_ideas.append({
                "type": "1-for-1",
                "give": [give["name"]],
                "get": [get["name"]],
                "partner": tk
            })

    # 2-for-1
    if len(safe_trade_bait) >= 2:
        trade_ideas.append({
            "type": "2-for-1",
            "give": [safe_trade_bait[0]["name"], safe_trade_bait[1]["name"]],
            "get": [targets[0]["name"]],
            "partner": tk
        })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "generated": datetime.now(timezone.utc).isoformat(),
    "my_team": my_team_key,
    "trade_analysis": {
        "strong_categories": strong_cats,
        "weak_categories": weak_cats,
        "my_team_averages": my_avgs,
        "league_averages": league_avgs,
        "recommended_trade_partners": trade_partners,
        "safe_trade_bait": safe_trade_bait,
        "trade_ideas": trade_ideas[:15]
    }
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with player-level trade recommendations")
