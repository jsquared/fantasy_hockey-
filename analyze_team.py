import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

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

# ---------- Fetch latest scoreboard ----------
raw = league.yhandler.get_scoreboard_raw(league.league_id, current_week)

# Extract league block safely
league_data = raw.get("fantasy_content", {}).get("league", [None, {}])[1]
matchups = league_data.get("scoreboard", {}).get("0", {}).get("matchups", {})

# Find my matchup
my_team_data = None
for k, v in matchups.items():
    if k == "count":
        continue
    matchup = v.get("matchup", {})
    teams = matchup.get("0", {}).get("teams", {})
    for tk, tv in teams.items():
        if tk == "count":
            continue
        tmeta = tv["team"][0]
        stats = tv["team"][1]
        tkey = tmeta[0]["team_key"]
        name = tmeta[2]["name"]
        score = float(stats["team_points"]["total"])
        if tkey == team_key:
            my_team_data = {"team_key": tkey, "name": name, "score": score, "stats": stats.get("team_stats", {})}
            break
    if my_team_data:
        break

if not my_team_data:
    raise RuntimeError("Could not find your team in the matchup")

# ---------- Translate stat IDs to names ----------
stat_categories = {}
try:
    league_settings = league.settings()
    for s in league_settings.get("stat_categories", []):
        sid = s.get("stat_id")
        sname = s.get("name")
        if sid and sname:
            stat_categories[sid] = sname
except Exception:
    # fallback: use raw stat IDs
    stat_categories = {}

# ---------- Build strengths and weaknesses ----------
strengths = []
weaknesses = []

team_stats = my_team_data.get("stats", {}).get("stats", [])

for s in team_stats:
    try:
        sid = str(s["stat"]["stat_id"])
        val = float(s["stat"]["value"])
        name = stat_categories.get(sid, f"Stat {sid}")
        entry = {"stat_id": sid, "name": name, "value": val}
        if val > 0:
            strengths.append(entry)
        else:
            weaknesses.append(entry)
    except Exception:
        continue

# ---------- Output JSON ----------
payload = {
    "league": league.settings().get("name", "Unknown League"),
    "team_key": team_key,
    "week": current_week,
    "strengths": strengths,
    "weaknesses": weaknesses,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/analyzed_team.json", "w") as f:
    json.dump(payload, f, indent=2)

print("docs/analyzed_team.json updated")
