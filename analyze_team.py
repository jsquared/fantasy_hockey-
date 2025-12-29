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
WEEKS = 12  # adjust to number of weeks you want to analyze

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

# =========================
# Stat ID → Name Map
# =========================
STAT_MAP = {
    # Skater stats
    "1": "Goals", "2": "Assists", "4": "+/-", "5": "PIM", "8": "PPP",
    "11": "SHP", "12": "GWG", "14": "SOG", "16": "FW", "31": "Hit", "32": "Blk",
    # Goalie stats
    "19": "Wins", "22": "GA", "23": "GAA", "24": "Shots Against", 
    "25": "Saves", "26": "SV%", "27": "Shutouts"
}

NEGATIVE_STATS = {"22","23","24"}  # lower is better for ranking

# =========================
# Initialize storage
# =========================
weekly_ranks = {str(week): [] for week in range(1, WEEKS+1)}
all_team_stats_by_week = {}

# =========================
# Loop over weeks
# =========================
for week in range(1, WEEKS+1):
    raw = league.yhandler.get_scoreboard_raw(LEAGUE_ID, week)
    league_data = raw["fantasy_content"]["league"][1]
    scoreboard = league_data["scoreboard"]["0"]
    matchups = scoreboard["matchups"]

    # Collect all teams stats
    league_stats = {}
    for k, v in matchups.items():
        if k == "count":
            continue
        matchup = v["matchup"]
        teams = matchup["0"]["teams"]
        for tk, tv in teams.items():
            if tk == "count":
                continue
            team_block = tv["team"]
            meta = team_block[0]
            team_key = meta[0]["team_key"]
            team_name = meta[2]["name"]
            stats_raw = team_block[1]["team_stats"]["stats"]
            stats = {}
            for item in stats_raw:
                stat = item.get("stat")
                if stat is None:
                    continue
                stat_id = str(stat.get("stat_id"))
                value_raw = stat.get("value")
                try:
                    value = float(value_raw)
                except (TypeError, ValueError):
                    value = value_raw
                stats[stat_id] = value
            league_stats[team_key] = {
                "team_name": team_name,
                "stats": stats
            }

    all_team_stats_by_week[str(week)] = league_stats

    # Rank my stats
    my_stats = league_stats[my_team_key]["stats"]
    for stat_id, my_value in my_stats.items():
        try:
            my_val_num = float(my_value)
        except (TypeError, ValueError):
            continue

        league_values = []
        for team_data in league_stats.values():
            val = team_data["stats"].get(stat_id)
            try:
                league_values.append(float(val))
            except (TypeError, ValueError):
                continue
        if not league_values:
            continue

        # Determine rank
        if stat_id in NEGATIVE_STATS:
            league_values_sorted = sorted(league_values)
        else:
            league_values_sorted = sorted(league_values, reverse=True)

        try:
            rank = league_values_sorted.index(my_val_num) + 1
        except ValueError:
            rank = None

        weekly_ranks[str(week)].append({
            "stat_id": stat_id,
            "name": STAT_MAP.get(stat_id, f"Stat {stat_id}"),
            "value": my_val_num,
            "rank": rank,
            "total_teams": len(league_values)
        })

# =========================
# Compute average rank per stat
# =========================
avg_ranks = {}
for week_data in weekly_ranks.values():
    for item in week_data:
        sid = item["stat_id"]
        avg_ranks.setdefault(sid, []).append(item["rank"])

avg_ranks_final = []
for sid, ranks in avg_ranks.items():
    avg_ranks_final.append({
        "stat_id": sid,
        "name": STAT_MAP.get(sid, f"Stat {sid}"),
        "average_rank": sum(ranks)/len(ranks) if ranks else None,
        "num_weeks": len(ranks)
    })

# =========================
# Save to JSON
# =========================
payload = {
    "league": league.settings().get("name", "Unknown League"),
    "my_team_key": my_team_key,
    "team_name": league.team_name(),
    "weeks_analyzed": WEEKS,
    "all_team_stats_by_week": all_team_stats_by_week,
    "weekly_ranks": weekly_ranks,
    "average_rank_per_stat": avg_ranks_final,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/team_analysis.json updated with weekly ranks and averages")
