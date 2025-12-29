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
WEEKS = 12  # adjust if needed

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
teams = league.teams()  # dict keyed by team_key

# =========================
# STAT MAP
# =========================
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
    "31": "Hits",
    "32": "Blocks",
    "19": "Wins",
    "22": "GA",
    "23": "GAA",
    "24": "Shots Against",
    "25": "Saves",
    "26": "SV%",
    "27": "Shutouts"
}

# =========================
# HELPERS
# =========================
def extract_team_stats(team_block):
    stats = {}
    for item in team_block[1]["team_stats"]["stats"]:
        stat_id = str(item["stat"]["stat_id"])
        raw = item["stat"]["value"]
        try:
            stats[stat_id] = float(raw)
        except (TypeError, ValueError):
            stats[stat_id] = None
    return stats

# =========================
# DATA STRUCTURES
# =========================
weekly_team_stats = {}     # week -> team_key -> stats
weekly_team_ranks = {}     # week -> team_key -> stat_name -> rank
avg_team_ranks = {}        # team_key -> stat_name -> avg_rank
trend_analysis = {}        # team_key -> stat_name -> trend data

# =========================
# LOOP WEEKS
# =========================
for week in range(1, WEEKS + 1):
    raw = league.yhandler.get_scoreboard_raw(league.league_id, week)
    league_data = raw["fantasy_content"]["league"][1]
    scoreboard = league_data["scoreboard"]["0"]
    matchups = scoreboard["matchups"]

    week_stats = {}

    for _, matchup_block in matchups.items():
        if _ == "count":
            continue

        teams_block = matchup_block["matchup"]["0"]["teams"]

        for _, team_entry in teams_block.items():
            if _ == "count":
                continue

            team_block = team_entry["team"]
            team_key = team_block[0][0]["team_key"]
            week_stats[team_key] = extract_team_stats(team_block)

    weekly_team_stats[str(week)] = week_stats

    # =========================
    # RANKING FOR THIS WEEK
    # =========================
    week_ranks = {team_key: {} for team_key in week_stats}

    for stat_id, stat_name in STAT_MAP.items():
        stat_values = {
            team: stats.get(stat_id)
            for team, stats in week_stats.items()
            if stats.get(stat_id) is not None
        }

        # Higher is better for now (GA/GAA logic later)
        sorted_teams = sorted(
            stat_values.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for rank, (team_key, _) in enumerate(sorted_teams, start=1):
            week_ranks[team_key][stat_name] = rank

    weekly_team_ranks[str(week)] = week_ranks

# =========================
# AVERAGE RANKS
# =========================
for team_key in teams.keys():
    avg_team_ranks[team_key] = {}

    for stat_name in STAT_MAP.values():
        total = 0
        count = 0

        for week_data in weekly_team_ranks.values():
            rank = week_data.get(team_key, {}).get(stat_name)
            if rank is not None:
                total += rank
                count += 1

        avg_team_ranks[team_key][stat_name] = total / count if count else None

# =========================
# TREND DETECTION
# =========================
for team_key in teams.keys():
    trend_analysis[team_key] = {}

    for stat_name in STAT_MAP.values():
        ranks = []

        for week in range(1, WEEKS + 1):
            rank = weekly_team_ranks.get(str(week), {}).get(team_key, {}).get(stat_name)
            if rank is not None:
                ranks.append((week, rank))

        if len(ranks) < 2:
            continue

        movements = []
        for i in range(1, len(ranks)):
            prev_rank = ranks[i - 1][1]
            curr_rank = ranks[i][1]

            if curr_rank < prev_rank:
                movements.append("up")
            elif curr_rank > prev_rank:
                movements.append("down")
            else:
                movements.append("flat")

        net_change = ranks[-1][1] - ranks[0][1]

        if net_change < 0:
            summary = "improving"
        elif net_change > 0:
            summary = "declining"
        else:
            summary = "stable"

        trend_analysis[team_key][stat_name] = {
            "weekly_ranks": ranks,
            "movements": movements,
            "net_change": net_change,
            "trend": summary
        }

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings().get("name", "Unknown League"),
    "weeks_analyzed": WEEKS,
    "teams": {
        k: {
            "name": v["name"],
            "manager": v.get("managers", [{}])[0].get("nickname")
        }
        for k, v in teams.items()
    },
    "weekly_team_stats": weekly_team_stats,
    "weekly_team_ranks": weekly_team_ranks,
    "average_team_ranks": avg_team_ranks,
    "trend_analysis": trend_analysis,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/team_analysis.json updated with league-wide ranks and trends")
