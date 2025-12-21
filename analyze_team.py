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
def normalize_stat(stat):
    if isinstance(stat, dict):
        return stat.get("stat_id"), stat.get("value")

    if isinstance(stat, list):
        stat_id = None
        value = None
        for item in stat:
            if "stat_id" in item:
                stat_id = item["stat_id"]
            if "value" in item:
                value = item["value"]
        return stat_id, value

    return None, None

# ---------- Stat ID → Name (SAFE) ----------
stat_map = {}

settings = league.settings()

if "stat_categories" in settings:
    cats = settings["stat_categories"]
    if isinstance(cats, dict) and "stats" in cats:
        cats = cats["stats"]

    for s in cats:
        stat_map[str(s["stat_id"])] = s["name"]

# ---------- Scoreboard ----------
raw = league.yhandler.get_scoreboard_raw(league.league_id, current_week)
league_data = raw["fantasy_content"]["league"][1]
matchups = league_data["scoreboard"]["0"]["matchups"]

my_stats = {}

for k, v in matchups.items():
    if k == "count":
        continue

    teams = v["matchup"]["0"]["teams"]

    for tk, tv in teams.items():
        if tk == "count":
            continue

        team = tv["team"]
        meta = team[0]
        stats = team[1]

        if meta[0]["team_key"] != team_key:
            continue

        for entry in stats["team_stats"]["stats"]:
            stat_id, value = normalize_stat(entry["stat"])
            if stat_id and value is not None:
                my_stats[str(stat_id)] = float(value)

# ---------- Rank Strengths / Weaknesses ----------
named = []
for stat_id, value in my_stats.items():
    named.append({
        "stat_id": stat_id,
        "name": stat_map.get(stat_id, f"Stat {stat_id}"),
        "value": value
    })

strengths = sorted(
    [s for s in named if s["value"] > 0],
    key=lambda x: x["value"],
    reverse=True
)

weaknesses = sorted(
    [s for s in named if s["value"] <= 0],
    key=lambda x: x["value"]
)

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
