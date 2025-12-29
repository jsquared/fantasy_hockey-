import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"
WEEKS = 12  # number of weeks to analyze

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

my_team_key = league.team_key()  # your team key

# =========================
# STAT MAP
# =========================
stat_map = {
    "1": "Goals",
    "2": "Assists",
    "4": "+/-",
    "5": "PIM",
    "8": "PPP",
    "11": "SHP",
    "12": "GWG",
    "14": "SOG",
    "16": "FW",
    "31": "Hit",
    "32": "Blk",
    "19": "Wins",
    "22": "GA",
    "23": "GAA",
    "24": "SA",
    "25": "Saves",
    "26": "SV%",
    "27": "Shutouts"
}

# =========================
# HELPER FUNCTION TO GET TEAM STATS
# =========================
def get_team_stats(team_block):
    stats = team_block[1]["team_stats"]["stats"]
    result = {}
    for item in stats:
        stat_id = str(item["stat"]["stat_id"])
        raw_value = item["stat"]["value"]
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            value = None
        result[stat_id] = value
    return result

# =========================
# ANALYSIS
# =========================
all_team_stats_by_week = {}
weekly_ranks = {}

for week in range(1, WEEKS + 1):
    raw = league.yhandler.get_scoreboard_raw(league.league_id, week)
    league_data = raw["fantasy_content"]["league"][1]
    scoreboard = league_data["scoreboard"]["0"]
    matchups = scoreboard["matchups"]

    # Collect all teams stats
    week_team_stats = {}
    for k, v in matchups.items():
        if k == "count":
            continue
        matchup = v["matchup"]
        teams = matchup["0"]["teams"]
        for tk, tv in teams.items():
            if tk == "count":
                continue
            team_block = tv["team"]
            team_key = team_block[0][0]["team_key"]
            week_team_stats[team_key] = get_team_stats(team_block)

    all_team_stats_by_week[str(week)] = week_team_stats

    # Compute ranks for my team
    my_stats = week_team_stats[my_team_key]
    ranks = {}
    for stat_id in my_stats:
        values = [v.get(stat_id) for v in week_team_stats.values() if v.get(stat_id) is not None]
        values_sorted = sorted(values, reverse=True)  # higher is better
        my_value = my_stats[stat_id]
        if my_value is None:
            ranks[stat_map.get(stat_id, stat_id)] = None
        else:
            ranks[stat_map.get(stat_id, stat_id)] = values_sorted.index(my_value) + 1
    weekly_ranks[str(week)] = ranks

# =========================
# Compute average ranks across weeks
# =========================
avg_ranks = {}
for stat_name in stat_map.values():
    total = count = 0
    for week_ranks in weekly_ranks.values():
        rank = week_ranks.get(stat_name)
        if rank is not None:
            total += rank
            count += 1
    avg_ranks[stat_name] = total / count if count else None

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings().get("name", "Unknown League"),
    "my_team_key": my_team_key,
    "team_name": league.teams()[my_team_key]["name"],
    "weeks_analyzed": WEEKS,
    "all_team_stats_by_week": all_team_stats_by_week,
    "weekly_ranks": weekly_ranks,
    "average_rank_per_stat": avg_ranks,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/team_analysis.json updated successfully")
