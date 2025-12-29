import json
import os
import statistics
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"

STAT_MAP = {
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
    "24": "Shots Against",
    "25": "Saves",
    "26": "SV%",
    "27": "Shutouts",
}

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

current_week = int(league.current_week())
weeks = list(range(1, current_week + 1))

teams_raw = league.teams()
teams = {}

for t in teams_raw:
    teams[t["team_key"]] = {
        "name": t["name"],
        "team_id": t["team_id"]
    }

# =========================
# STORAGE
# =========================
weekly_team_stats = {}
weekly_team_ranks = {}

# =========================
# FETCH WEEKLY DATA
# =========================
for week in weeks:
    raw = league.yhandler.get_scoreboard_raw(
        league.league_id, week
    )

    league_data = raw["fantasy_content"]["league"][1]
    scoreboard = league_data["scoreboard"]["0"]
    matchups = scoreboard["matchups"]

    weekly_team_stats[str(week)] = {}

    for matchup_key, matchup_data in matchups.items():
        if matchup_key == "count":
            continue

        teams_block = matchup_data["matchup"]["0"]["teams"]

        for team_key, team_data in teams_block.items():
            if team_key == "count":
                continue

            team = team_data["team"]
            meta = team[0]
            stats_block = team[1]["team_stats"]["stats"]

            t_key = meta[0]["team_key"]

            weekly_team_stats[str(week)][t_key] = {}

            for item in stats_block:
                stat = item["stat"]
                stat_id = stat["stat_id"]
                value = stat["value"]

                if stat_id not in STAT_MAP:
                    continue

                try:
                    value = float(value)
                except (TypeError, ValueError):
                    continue

                weekly_team_stats[str(week)][t_key][STAT_MAP[stat_id]] = value

# =========================
# WEEKLY RANKINGS
# =========================
for week, team_stats in weekly_team_stats.items():
    weekly_team_ranks[week] = {}

    for stat_name in STAT_MAP.values():
        stat_values = []

        for team_key, stats in team_stats.items():
            if stat_name in stats:
                stat_values.append((team_key, stats[stat_name]))

        reverse = stat_name not in ["GA", "GAA", "Shots Against"]

        stat_values.sort(key=lambda x: x[1], reverse=reverse)

        for rank, (team_key, _) in enumerate(stat_values, start=1):
            weekly_team_ranks[week].setdefault(team_key, {})
            weekly_team_ranks[week][team_key][stat_name] = rank

# =========================
# AVERAGE RANKS
# =========================
avg_team_ranks = {}

for team_key in teams.keys():
    avg_team_ranks[team_key] = {}

    for stat_name in STAT_MAP.values():
        ranks = []

        for week in weekly_team_ranks:
            rank = weekly_team_ranks[week].get(team_key, {}).get(stat_name)
            if rank is not None:
                ranks.append(rank)

        if ranks:
            avg_team_ranks[team_key][stat_name] = round(
                sum(ranks) / len(ranks), 3
            )

# =========================
# TREND DETECTION
# =========================
team_trends = {}

for team_key in teams.keys():
    team_trends[team_key] = {}

    for stat_name in STAT_MAP.values():
        weekly = {}

        for week in weekly_team_ranks:
            rank = weekly_team_ranks[week].get(team_key, {}).get(stat_name)
            if rank is not None:
                weekly[int(week)] = rank

        if len(weekly) < 2:
            continue

        weeks_sorted = sorted(weekly.keys())
        ranks = [weekly[w] for w in weeks_sorted]

        deltas = {}
        for i in range(1, len(weeks_sorted)):
            deltas[str(weeks_sorted[i])] = ranks[i - 1] - ranks[i]

        avg_delta = sum(deltas.values()) / len(deltas)

        x = list(range(len(ranks)))
        x_mean = sum(x) / len(x)
        y_mean = sum(ranks) / len(ranks)

        num = sum((x[i] - x_mean) * (ranks[i] - y_mean) for i in range(len(x)))
        den = sum((x[i] - x_mean) ** 2 for i in range(len(x)))
        slope = num / den if den else 0

        team_trends[team_key][stat_name] = {
            "weekly_ranks": weekly,
            "week_over_week_delta": deltas,
            "avg_delta": round(avg_delta, 3),
            "trend_slope": round(slope, 3),
            "stdev": round(statistics.stdev(ranks), 3)
        }

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings().get("name"),
    "weeks_analyzed": weeks,
    "teams": teams,
    "weekly_team_stats": weekly_team_stats,
    "weekly_team_ranks": weekly_team_ranks,
    "average_team_ranks": avg_team_ranks,
    "trend_analysis": team_trends,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/team_analysis.json updated")
