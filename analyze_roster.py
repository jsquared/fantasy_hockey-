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
MY_TEAM_KEY = "465.l.33140.t.13"

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
    "32": "BLK",
}

GOALIE_STATS = {
    "19": "W",
    "22": "GA",
    "23": "GAA",
    "24": "SA",
    "25": "SV",
    "26": "SV%",
    "27": "SHO",
}

ALL_STATS = {**SKATER_STATS, **GOALIE_STATS}

LOWER_IS_BETTER = {"GA", "GAA"}

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

# =========================
# Teams
# =========================
teams = {}
for t in league.teams():
    teams[t["team_key"]] = {
        "name": t["name"],
        "team_id": t["team_id"],
    }

# =========================
# DATA STORAGE
# =========================
weekly_stats = {}

# =========================
# FETCH WEEKLY DATA
# =========================
for week in weeks:
    raw = league.yhandler.get_scoreboard_raw(league.league_id, week)
    scoreboard = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]

    weekly_stats[str(week)] = {}

    for m_key, matchup in scoreboard["matchups"].items():
        if m_key == "count":
            continue

        for t_key, t_data in matchup["matchup"]["0"]["teams"].items():
            if t_key == "count":
                continue

            team_meta = t_data["team"][0]
            stats = t_data["team"][1]["team_stats"]["stats"]

            team_key = team_meta[0]["team_key"]
            weekly_stats[str(week)].setdefault(team_key, {})

            for s in stats:
                sid = s["stat"]["stat_id"]
                val = s["stat"]["value"]

                if sid not in ALL_STATS:
                    continue

                try:
                    val = float(val)
                except:
                    continue

                weekly_stats[str(week)][team_key][ALL_STATS[sid]] = val

# =========================
# AVERAGES
# =========================
def average_stats(stat_group):
    league_avg = {}
    my_avg = {}

    for stat in stat_group.values():
        league_vals = []
        my_vals = []

        for week in weekly_stats.values():
            for team, stats in week.items():
                if stat in stats:
                    league_vals.append(stats[stat])
                    if team == MY_TEAM_KEY:
                        my_vals.append(stats[stat])

        if league_vals:
            league_avg[stat] = sum(league_vals) / len(league_vals)
        if my_vals:
            my_avg[stat] = sum(my_vals) / len(my_vals)

    return my_avg, league_avg

my_skater_avg, league_skater_avg = average_stats(SKATER_STATS)
my_goalie_avg, league_goalie_avg = average_stats(GOALIE_STATS)

# =========================
# STRENGTH / WEAKNESS
# =========================
def compare(my, league):
    strong = []
    weak = []

    for stat, my_val in my.items():
        lg = league.get(stat)
        if lg is None:
            continue

        if stat in LOWER_IS_BETTER:
            if my_val < lg:
                strong.append(stat)
            else:
                weak.append(stat)
        else:
            if my_val > lg:
                strong.append(stat)
            else:
                weak.append(stat)

    return strong, weak

skater_strong, skater_weak = compare(my_skater_avg, league_skater_avg)
goalie_strong, goalie_weak = compare(my_goalie_avg, league_goalie_avg)

# =========================
# TRADE PARTNERS (LOGIC ONLY)
# =========================
trade_targets = []

for team_key, team in teams.items():
    if team_key == MY_TEAM_KEY:
        continue

    helps_us = []
    they_need = []

    for stat in skater_weak:
        if stat in league_skater_avg:
            helps_us.append(stat)

    for stat in skater_strong:
        they_need.append(stat)

    if helps_us and they_need:
        trade_targets.append({
            "team_key": team_key,
            "team_name": team["name"],
            "they_help_us_in": helps_us,
            "they_need_from_us": they_need,
            "type": "skater"
        })

# goalie trades only if goalie weakness exists
if goalie_weak:
    for team_key, team in teams.items():
        if team_key == MY_TEAM_KEY:
            continue

        trade_targets.append({
            "team_key": team_key,
            "team_name": team["name"],
            "they_help_us_in": goalie_weak,
            "they_need_from_us": goalie_strong,
            "type": "goalie"
        })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "generated": datetime.now(timezone.utc).isoformat(),
    "my_team": MY_TEAM_KEY,
    "skater_analysis": {
        "my_averages": my_skater_avg,
        "league_averages": league_skater_avg,
        "strengths": skater_strong,
        "weaknesses": skater_weak,
    },
    "goalie_analysis": {
        "my_averages": my_goalie_avg,
        "league_averages": league_goalie_avg,
        "strengths": goalie_strong,
        "weaknesses": goalie_weak,
    },
    "trade_suggestions": trade_targets,
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json written successfully")
