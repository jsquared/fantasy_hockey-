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

current_week = int(league.current_week())
weeks = list(range(1, current_week + 1))

# =========================
# TEAMS (FIXED FOR YOUR VERSION)
# =========================
teams = {}

for team_key in league.teams():
    team_obj = league.to_team(team_key)

    teams[team_key] = {
        "name": team_obj.name(),
        "team_id": team_obj.team_id
    }

# =========================
# WEEKLY STATS
# =========================
weekly_stats = {}

for week in weeks:
    raw = league.yhandler.get_scoreboard_raw(league.league_id, week)
    scoreboard = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]

    weekly_stats[str(week)] = {}

    for m_key, matchup in scoreboard["matchups"].items():
        if m_key == "count":
            continue

        for t_key, tdata in matchup["matchup"]["0"]["teams"].items():
            if t_key == "count":
                continue

            team_key = tdata["team"][0][0]["team_key"]
            stats = tdata["team"][1]["team_stats"]["stats"]

            weekly_stats[str(week)].setdefault(team_key, {})

            for s in stats:
                sid = s["stat"]["stat_id"]
                val = s["stat"]["value"]

                if sid not in SKATER_STATS:
                    continue

                try:
                    weekly_stats[str(week)][team_key][SKATER_STATS[sid]] = float(val)
                except:
                    continue

# =========================
# AVERAGES
# =========================
def compute_avg(team_key):
    totals = {}
    counts = {}

    for week in weekly_stats.values():
        stats = week.get(team_key, {})
        for k, v in stats.items():
            totals[k] = totals.get(k, 0) + v
            counts[k] = counts.get(k, 0) + 1

    return {k: totals[k] / counts[k] for k in totals}

my_avg = compute_avg(MY_TEAM_KEY)

league_avg = {}
for stat in SKATER_STATS.values():
    vals = []
    for team_key in teams:
        avg = compute_avg(team_key)
        if stat in avg:
            vals.append(avg[stat])
    league_avg[stat] = sum(vals) / len(vals)

# =========================
# STRENGTH / WEAKNESS
# =========================
strong = [s for s in my_avg if my_avg[s] > league_avg[s]]
weak = [s for s in my_avg if my_avg[s] < league_avg[s]]

# =========================
# 1-FOR-1 TRADE IDEAS
# =========================
trade_ideas = []

for team_key, team in teams.items():
    if team_key == MY_TEAM_KEY:
        continue

    their_avg = compute_avg(team_key)

    helps_us = [
        s for s in weak
        if s in their_avg and their_avg[s] > league_avg[s]
    ]

    they_need = [
        s for s in strong
        if s in their_avg and their_avg[s] < league_avg[s]
    ]

    if helps_us and they_need:
        trade_ideas.append({
            "partner": team_key,
            "team_name": team["name"],
            "they_help_us_in": helps_us,
            "they_need_from_us": they_need,
            "type": "1-for-1"
        })

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings()["name"],
    "generated": datetime.now(timezone.utc).isoformat(),
    "my_team": MY_TEAM_KEY,
    "my_averages": my_avg,
    "league_averages": league_avg,
    "strengths": strong,
    "weaknesses": weak,
    "trade_ideas": trade_ideas,
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json written — 1-for-1 trade logic restored")
