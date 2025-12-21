import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

LEAGUE_ID = "465.l.33140"

# ---------- OAuth ----------
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        f.write(os.environ["YAHOO_OAUTH_JSON"])

oauth = OAuth2(None, None, from_file="oauth2.json")

# ---------- Yahoo objects ----------
game = yfa.Game(oauth, "nhl")
league = game.to_league(LEAGUE_ID)
team_key = league.team_key()
current_week = league.current_week()

# ---------- Get stat categories ----------
raw_settings = league.yhandler.get_settings_raw(league.league_id)

stat_categories = {}

stats_list = (
    raw_settings["fantasy_content"]["league"][1]
    ["settings"][0]
    ["stat_categories"][0]
    ["stats"]
)

for entry in stats_list:
    stat = entry.get("stat")
    if not stat:
        continue

    stat_id = None
    stat_name = None

    for item in stat:
        if "stat_id" in item:
            stat_id = item["stat_id"]
        if "name" in item:
            stat_name = item["name"]

    if stat_id and stat_name:
        stat_categories[stat_id] = stat_name

# ---------- Get team stats ----------
raw_team = league.yhandler.get_team_stats_raw(team_key, current_week)

team_stats_raw = (
    raw_team["fantasy_content"]["team"][1]
    ["team_stats"]["stats"]
)

team_stats = {}

for entry in team_stats_raw:
    stat = entry.get("stat")
    if not stat:
        continue

    stat_id = None
    value = None

    for item in stat:
        if "stat_id" in item:
            stat_id = item["stat_id"]
        if "value" in item:
            value = item["value"]

    if stat_id and value is not None:
        team_stats[stat_categories.get(stat_id, stat_id)] = value

# ---------- Strength classification ----------
strengths = {}
weaknesses = {}

for stat, value in team_stats.items():
    try:
        numeric = float(value)
    except ValueError:
        continue

    if numeric > 0:
        strengths[stat] = numeric
    else:
        weaknesses[stat] = numeric

# ---------- Output ----------
analysis = {
    "league": league.settings()["name"],
    "team": league.team_name(),
    "week": current_week,
    "strengths": strengths,
    "weaknesses": weaknesses,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/analysis.json", "w") as f:
    json.dump(analysis, f, indent=2)

print("analysis.json updated")
