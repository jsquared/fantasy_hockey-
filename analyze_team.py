import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
from statistics import mean

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"
WEEKS = 12  # weeks to analyze

# Higher is better (False = lower is better)
STAT_BETTER_HIGH = {
    "Goals": True,
    "Assists": True,
    "+/-": True,
    "PIM": True,
    "PPP": True,
    "SHP": True,
    "GWG": True,
    "SOG": True,
    "FW": True,
    "Hits": True,
    "Blocks": True,
    "Wins": True,
    "GA": False,
    "GAA": False,
    "Shots Against": False,
    "Saves": True,
    "SV%": True,
    "Shutouts": True,
}

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

teams = league.teams()
my_team_key = league.team_key()
current_week = league.current_week()

# =========================
# HELPERS
# =========================
def extract_team_stats(team_block):
    stats = {}
    for item in team_block[1]["team_stats"]["stats"]:
        stat_id = str(item["stat"]["stat_id"])
        raw = item["stat"]["value"]
        try:
            stats[STAT_MAP[stat_id]] = float(raw)
        except (TypeError, ValueError):
            stats[STAT_MAP[stat_id]] = None
    return stats

# =========================
# DATA COLLECTION
# =========================
weekly_stats = {}   # week -> team -> stat -> value
weekly_ranks = {}   # week -> team -> stat -> rank

for week in range(1, WEEKS + 1):
    raw = league.yhandler.get_scoreboard_raw(league.league_id, week)
    matchups = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

    week_data = {}

    for _, matchup in matchups.items():
        if _ == "count":
            continue

        teams_block = matchup["matchup"]["0"]["teams"]
        for _, team_entry in teams_block.items():
            if _ == "count":
                continue

            team_block = team_entry["team"]
            tkey = team_block[0][0]["team_key"]
            week_data[tkey] = extract_team_stats(team_block)

    weekly_stats[str(week)] = week_data

    # Ranking
    week_rank = {t: {} for t in week_data}
    for stat in STAT_MAP.values():
        values = {
            t: s.get(stat)
            for t, s in week_data.items()
            if s.get(stat) is not None
        }

        reverse = STAT_BETTER_HIGH.get(stat, True)
        sorted_vals = sorted(values.items(), key=lambda x: x[1], reverse=reverse)

        for rank, (t, _) in enumerate(sorted_vals, start=1):
            week_rank[t][stat] = rank

    weekly_ranks[str(week)] = week_rank

# =========================
# AVERAGES & TRENDS
# =========================
avg_values = {}
avg_ranks = {}
trends = {}

for tkey in teams:
    avg_values[tkey] = {}
    avg_ranks[tkey] = {}
    trends[tkey] = {}

    for stat in STAT_MAP.values():
        vals = []
        ranks = []

        for w in weekly_stats.values():
            v = w.get(tkey, {}).get(stat)
            if v is not None:
                vals.append(v)

        for w in weekly_ranks.values():
            r = w.get(tkey, {}).get(stat)
            if r is not None:
                ranks.append(r)

        avg_values[tkey][stat] = mean(vals) if vals else None
        avg_ranks[tkey][stat] = mean(ranks) if ranks else None

        # Trend = last 3 weeks slope
        if len(vals) >= 3:
            trends[tkey][stat] = vals[-1] - vals[-3]
        else:
            trends[tkey][stat] = 0

# =========================
# CURRENT MATCHUP
# =========================
raw = league.yhandler.get_scoreboard_raw(league.league_id, current_week)
matchups = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

opp_key = None

for _, v in matchups.items():
    if _ == "count":
        continue
    teams_block = v["matchup"]["0"]["teams"]
    team_keys = [
        tv["team"][0][0]["team_key"]
        for tk, tv in teams_block.items()
        if tk != "count"
    ]
    if my_team_key in team_keys:
        opp_key = next(t for t in team_keys if t != my_team_key)
        break

# =========================
# PREDICTION ENGINE
# =========================
predictions = {}

for stat in STAT_MAP.values():
    my_avg = avg_values[my_team_key][stat]
    opp_avg = avg_values[opp_key][stat]

    my_rank = avg_ranks[my_team_key][stat]
    opp_rank = avg_ranks[opp_key][stat]

    my_trend = trends[my_team_key][stat]
    opp_trend = trends[opp_key][stat]

    score = 0

    if my_avg is not None and opp_avg is not None:
        score += 1 if my_avg > opp_avg else -1

    if my_rank is not None and opp_rank is not None:
        score += 1 if my_rank < opp_rank else -1

    score += 0.5 if my_trend > opp_trend else -0.5

    if score >= 1.5:
        result = "WIN"
    elif score <= -1.5:
        result = "LOSE"
    else:
        result = "TOSS_UP"

    predictions[stat] = {
        "prediction": result,
        "my_avg": my_avg,
        "opp_avg": opp_avg,
        "my_avg_rank": my_rank,
        "opp_avg_rank": opp_rank,
        "trend_diff": my_trend - opp_trend
    }

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "weeks_analyzed": WEEKS,
    "my_team": teams[my_team_key]["name"],
    "opponent": teams[opp_key]["name"],
    "average_stat_values": avg_values,
    "average_stat_ranks": avg_ranks,
    "trends": trends,
    "current_matchup_predictions": predictions,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/team_analysis.json updated with matchup predictions")
