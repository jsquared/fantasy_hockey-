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

# ---------- Helpers ----------
def unwrap(x):
    return x[0] if isinstance(x, list) else x

# ---------- Get raw team data (WITH STATS) ----------
raw_team = league.yhandler.get_team_raw(team_key, stats=current_week)
team_block = unwrap(raw_team["fantasy_content"]["team"])

stats_block = team_block["team_stats"]["stats"]

team_stats = {}

for entry in stats_block:
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

    if stat_id is not None and value is not None:
        team_stats[stat_id] = value

# ---------- Simple strength / weakness detection ----------
strengths = {}
weaknesses = {}

for stat_id, value in team_stats.items():
    try:
        numeric = float(value)
    except (ValueError, TypeError):
        continue

    if numeric > 0:
        strengths[stat_id] = numeric
    else:
        weaknesses[stat_id] = numeric

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
