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

# ---------- Yahoo ----------
game = yfa.Game(oauth, "nhl")
league = game.to_league(LEAGUE_ID)

team_key = league.team_key()
current_week = league.current_week()

# ---------- Helpers ----------
def unwrap(x):
    return x[0] if isinstance(x, list) else x

def normalize_stat(stat):
    """Always return (stat_id, value) or (None, None)"""
    if isinstance(stat, dict):
        return stat.get("stat_id"), stat.get("value")

    if isinstance(stat, list):
        stat_id = None
        value = None
        for item in stat:
            if isinstance(item, dict):
                if "stat_id" in item:
                    stat_id = item["stat_id"]
                if "value" in item:
                    value = item["value"]
        return stat_id, value

    return None, None

# ---------- Scoreboard (trusted source) ----------
raw = league.yhandler.get_scoreboard_raw(league.league_id, current_week)
league_data = raw["fantasy_content"]["league"][1]
matchups = league_data["scoreboard"]["0"]["matchups"]

my_stats = {}

# ---------- Extract my team stats ----------
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
        stats_block = team_block[1]

        tkey = meta[0]["team_key"]

        if tkey != team_key:
            continue

        for stat_entry in stats_block["team_stats"]["stats"]:
            stat = stat_entry.get("stat")
            stat_id, value = normalize_stat(stat)

            if stat_id is not None and value is not None:
                my_stats[stat_id] = value

# ---------- Sanity check ----------
if not my_stats:
    raise RuntimeError("Could not extract team stats from scoreboard")

# ---------- Strengths / Weaknesses ----------
strengths = {}
weaknesses = {}

for stat_id, value in my_stats.items():
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
    "team_key": team_key,
    "week": current_week,
    "strengths": strengths,
    "weaknesses": weaknesses,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/analysis.json", "w") as f:
    json.dump(analysis, f, indent=2)

print("analysis.json updated")
