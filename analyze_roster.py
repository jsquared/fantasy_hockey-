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

STAT_MAP = {
    "1": "G",
    "2": "A",
    "8": "PPP",
    "14": "SOG",
    "16": "FW",
    "31": "HIT",
    "32": "BLK",
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

# =========================
# Helpers
# =========================
def extract_team_stats(team_block):
    stats = {}
    for item in team_block[1]["team_stats"]["stats"]:
        stat_id = str(item["stat"]["stat_id"])
        if stat_id in STAT_MAP:
            try:
                stats[STAT_MAP[stat_id]] = float(item["stat"]["value"])
            except Exception:
                stats[STAT_MAP[stat_id]] = 0.0
    return stats

# =========================
# COLLECT WEEKLY TEAM STATS
# =========================
weekly_stats = defaultdict(dict)

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

            team_block = team_entry["team"]
            team_key = team_block[0][0]["team_key"]
            weekly_stats[week][team_key] = extract_team_stats(team_block)

# =========================
# SEASON AVERAGES
# =========================
team_averages = defaultdict(dict)

for team_key in teams.keys():
    for stat in STAT_MAP.values():
        values = [
            weekly_stats[w].get(team_key, {}).get(stat, 0)
            for w in range(1, WEEKS + 1)
        ]
        team_averages[team_key][stat] = sum(values) / len(values)

league_averages = {
    stat: sum(team_averages[t][stat] for t in teams) / len(teams)
    for stat in STAT_MAP.values()
}

my_totals = team_averages[my_team_key]

# =========================
# CATEGORY ANALYSIS
# =========================
strong_categories = [
    stat for stat in STAT_MAP.values()
    if my_totals[stat] > league_averages[stat]
]

weak_categories = [
    stat for stat in STAT_MAP.values()
    if my_totals[stat] < league_averages[stat]
]

# =========================
# TRADE PARTNER TARGETING
# =========================
recommended_trades = []

for team_key, stats in team_averages.items():
    if team_key == my_team_key:
        continue

    helps_us = [s for s in weak_categories if stats[s] > league_averages[s]]
    needs_from_us = [s for s in strong_categories if stats[s] < league_averages[s]]

    if helps_us and needs_from_us:
        recommended_trades.append({
            "team_key": team_key,
            "they_help_us_in": helps_us,
            "they_need_from_us": needs_from_us
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
        "my_team_averages": my_totals,
        "league_averages": league_averages,
        "recommended_trade_partners": recommended_trades
    }
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/roster.json updated (stable team-based trade analysis)")
