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
WEEKS = 12  # adjust as season progresses

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
teams = league.teams()  # metadata

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
weekly_team_stats = {}   # week -> team_key -> stats
weekly_team_ranks = {}   # week -> team_key -> stat_name -> rank
avg_team_ranks = {}      # team_key -> stat_name -> avg_rank
trend_data = {}          # team_key -> stat_name -> trend

# =========================
# LOOP WEEKS
# =========================
for week in range(1, WEEKS + 1):
    raw = league.yhandler.get_scoreboard_raw(league.league_id, week)
    league_data = raw["fantasy_content"]["league"][1]
    matchups = league_data["scoreboard"]["0"]["matchups"]

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

    # ---------- Rank stats this week ----------
    week_ranks = {tk: {} for tk in week_stats.keys()}

    for stat_id, stat_name in STAT_MAP.items():
        values = {
            tk: stats.get(stat_id)
            for tk, stats in week_stats.items()
            if stats.get(stat_id) is not None
        }

        sorted_teams = sorted(values.items(), key=lambda x: x[1], reverse=True)

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

        for week in weekly_team_ranks.values():
            r = week.get(team_key, {}).get(stat_name)
            if r is not None:
                total += r
                count += 1

        avg_team_ranks[team_key][stat_name] = round(total / count, 2) if count else None

# =========================
# TREND DETECTION
# =========================
for team_key in teams.keys():
    trend_data[team_key] = {}

    for stat_name in STAT_MAP.values():
        ranks = []
        for week in range(1, WEEKS + 1):
            r = weekly_team_ranks.get(str(week), {}).get(team_key, {}).get(stat_name)
            if r is not None:
                ranks.append(r)

        if len(ranks) < 2:
            trend = "no_data"
        else:
            delta = ranks[-1] - ranks[0]
            if delta < -1:
                trend = "improving"
            elif delta > 1:
                trend = "declining"
            else:
                trend = "stable"

        trend_data[team_key][stat_name] = {
            "start_rank": ranks[0] if ranks else None,
            "end_rank": ranks[-1] if ranks else None,
            "trend": trend
        }

# =========================
# CURRENT MATCHUP
# =========================
raw = league.yhandler.get_scoreboard_raw(league.league_id, current_week)
league_data = raw["fantasy_content"]["league"][1]
matchups = league_data["scoreboard"]["0"]["matchups"]

opponent_key = None

for _, v in matchups.items():
    if _ == "count":
        continue

    teams_block = v["matchup"]["0"]["teams"]
    keys = []

    for _, tv in teams_block.items():
        if _ == "count":
            continue
        keys.append(tv["team"][0][0]["team_key"])

    if my_team_key in keys:
        opponent_key = next(k for k in keys if k != my_team_key)
        break

if not opponent_key:
    raise RuntimeError("Could not find current matchup")

# =========================
# CATEGORY PREDICTION
# =========================
predictions = {}

for stat in STAT_MAP.values():
    my_rank = avg_team_ranks[my_team_key].get(stat)
    opp_rank = avg_team_ranks[opponent_key].get(stat)

    if my_rank is None or opp_rank is None:
        result = "unknown"
    elif my_rank < opp_rank:
        result = "win"
    elif my_rank > opp_rank:
        result = "loss"
    else:
        result = "tie"

    predictions[stat] = {
        "my_avg_rank": my_rank,
        "opp_avg_rank": opp_rank,
        "prediction": result
    }

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "weeks_analyzed": WEEKS,
    "current_week": current_week,
    "my_team_key": my_team_key,
    "opponent_team_key": opponent_key,
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
    "trend_data": trend_data,
    "current_matchup_prediction": predictions,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/team_analysis.json updated with matchup prediction + trends")
