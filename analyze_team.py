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

# ---------- Helper ----------
def unwrap(x):
    return x[0] if isinstance(x, list) else x

# ---------- Get stat categories (SAFE SOURCE) ----------
raw_league = league.yhandler.get_league_raw(league.league_id)

league_block = unwrap(raw_league["fantasy_content"]["league"])

settings_block = unwrap(league_block["settings"])
stat_categories_block = unwrap(settings_block["stat_categories"])
stats_list = stat_categories_block["stats"]

stat_categories = {}

for entry in stats_list:
    stat = entry.get("stat")
    if not stat:
        continue

    stat_id = None
    name = None

    for item in stat:
        if "stat_id" in item:
            stat_id = item["stat_id"]
        if "name" in item:
            name = item["name"]

    if stat_id and name:
        stat_categories[stat_id] = name

# ---------- Get team stats ----------
raw_team = league.yhandler.get_team_stats_raw(team_key, current_week)

team_block = unwrap(raw_team["fantasy_content"]["team"])
team_stats_list = team_block["team_stats"]["stats"]

team_stats = {}

for entry in team_stats_list:
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
        name = stat_categories.get(stat_id, stat_id)
        team_stats[name] = value

# ---------- Classify strengths / weaknesses ----------
strengths = {}
weaknesses = {}

for stat, value in team_stats.items():
    try:
        numeric = float(value)
    except (ValueError, TypeError):
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
