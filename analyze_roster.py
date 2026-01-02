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

MY_TEAM_KEY = "465.l.33140.t.13"

# Stat definitions
SKATER_STATS = {
    "1": "G",
    "2": "A",
    "4": "+/-",
    "5": "PIM",
    "8": "PPP",
    "11": "SHP",
    "12": "GWG",
    "14": "SOG",
    "16": "FW",
    "31": "HIT",
    "32": "BLK"
}

GOALIE_STATS = {
    "19": "W",
    "22": "GA",
    "23": "GAA",
    "24": "SA",
    "25": "SV",
    "26": "SV%",
    "27": "SHO"
}

LOWER_IS_BETTER = {"22", "23"}  # GA, GAA

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

current_week = league.current_week()
weeks = list(range(1, current_week + 1))

# =========================
# DATA STRUCTURES
# =========================
league_week_stats = defaultdict(lambda: defaultdict(dict))
my_week_ranks = defaultdict(lambda: defaultdict(int))
stat_rank_history = defaultdict(list)

# =========================
# FETCH LEAGUE DATA
# =========================
for week in weeks:
    raw = league.yhandler.get_scoreboard_raw(league.league_id, week)
    scoreboard = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

    for _, matchup_block in scoreboard.items():
        if _ == "count":
            continue

        teams = matchup_block["matchup"]["0"]["teams"]

        for _, team_block in teams.items():
            if _ == "count":
                continue

            team_key = team_block["team"][0][0]["team_key"]
            stats = team_block["team"][1]["team_stats"]["stats"]

            for stat_item in stats:
                stat = stat_item["stat"]
                stat_id = stat["stat_id"]
                value = stat.get("value")

                try:
                    value = float(value)
                except (TypeError, ValueError):
                    continue

                league_week_stats[week][stat_id][team_key] = value

# =========================
# RANKING ENGINE
# =========================
for week, stats_by_cat in league_week_stats.items():
    for stat_id, team_values in stats_by_cat.items():

        reverse = stat_id not in LOWER_IS_BETTER
        ranked = sorted(team_values.items(), key=lambda x: x[1], reverse=reverse)

        for rank, (team_key, _) in enumerate(ranked, start=1):
            if team_key == MY_TEAM_KEY:
                my_week_ranks[stat_id][week] = rank
                stat_rank_history[stat_id].append(rank)

# =========================
# AVERAGE RANKS
# =========================
avg_ranks = {
    stat_id: sum(ranks) / len(ranks)
    for stat_id, ranks in stat_rank_history.items()
}

# =========================
# OUTPUT
# =========================
output = {
    "league": league.settings().get("name", "Unknown League"),
    "generated": datetime.now(timezone.utc).isoformat(),
    "my_team": MY_TEAM_KEY,
    "weeks_analyzed": weeks,
    "average_ranks": {
        (SKATER_STATS | GOALIE_STATS).get(stat_id, stat_id): round(avg, 2)
        for stat_id, avg in avg_ranks.items()
    },
    "weekly_ranks": {
        (SKATER_STATS | GOALIE_STATS).get(stat_id, stat_id): {
            str(week): rank for week, rank in week_ranks.items()
        }
        for stat_id, week_ranks in my_week_ranks.items()
    }
}

os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(output, f, indent=2)

print("✅ League-wide goalie-normalized analysis complete")
