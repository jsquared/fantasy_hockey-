import json
import os
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
from statistics import mean

LEAGUE_ID = "465.l.33140"

# ---------- OAuth ----------
if "YAHOO_OAUTH_JSON" in os.environ:
    oauth_data = json.loads(os.environ["YAHOO_OAUTH_JSON"])
    with open("oauth2.json", "w") as f:
        json.dump(oauth_data, f)

oauth = OAuth2(None, None, from_file="oauth2.json")

# ---------- Yahoo objects ----------
game = yfa.Game(oauth, "nhl")
league = game.to_league(LEAGUE_ID)

team_key = league.team_key()
current_week = league.current_week()

my_team = league.to_team(team_key)

# ---------- League stat categories ----------
stat_categories = {
    s["stat"]["stat_id"]: s["stat"]["name"]
    for s in league.stat_categories()
}

# ---------- Get all teams ----------
teams = league.teams()

# ---------- Pull weekly stats for all teams ----------
league_stats = {}
my_stats = {}

for t in teams:
    t_key = t["team_key"]
    team = league.to_team(t_key)

    stats = team.stats(week=current_week)

    for stat_id, value in stats.items():
        if stat_id not in stat_categories:
            continue

        try:
            value = float(value)
        except:
            continue

        league_stats.setdefault(stat_id, []).append(value)

        if t_key == team_key:
            my_stats[stat_id] = value

# ---------- Analyze strengths / weaknesses ----------
analysis = {
    "strengths": [],
    "average": [],
    "weaknesses": []
}

detailed = {}

for stat_id, values in league_stats.items():
    avg = mean(values)
    mine = my_stats.get(stat_id, 0)

    diff = mine - avg
    name = stat_categories[stat_id]

    detailed[name] = {
        "my_value": mine,
        "league_avg": round(avg, 2),
        "difference": round(diff, 2)
    }

    if diff > 0.75:
        analysis["strengths"].append(name)
    elif diff < -0.75:
        analysis["weaknesses"].append(name)
    else:
        analysis["average"].append(name)

# ---------- Output ----------
output = {
    "team": my_team.team_name(),
    "week": current_week,
    "summary": analysis,
    "details": detailed
}

os.makedirs("docs", exist_ok=True)
with open("docs/team_analysis.json", "w") as f:
    json.dump(output, f, indent=2)

print("team_analysis.json created")
