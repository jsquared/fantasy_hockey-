import os
import json
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# ---------- Configuration ----------
LEAGUE_ID = "465.l.33140"
OUTPUT_FILE = "docs/analysis.json"

# ---------- OAuth ----------
if "YAHOO_OAUTH_JSON" in os.environ:
    oauth_data = json.loads(os.environ["YAHOO_OAUTH_JSON"])
    with open("oauth2.json", "w") as f:
        json.dump(oauth_data, f)

print("🔑 Authenticating with Yahoo...")
oauth = OAuth2(None, None, from_file="oauth2.json")

# ---------- Yahoo objects ----------
gm = yfa.Game(oauth, "nhl")
league = gm.to_league(LEAGUE_ID)

current_week = league.current_week()
league_name = league.settings().get("name", "Unknown League")

# ---------- Get stat categories safely ----------
stat_categories = league.settings().get("stat_categories", {}).get("stats", [])
if not stat_categories:
    raise RuntimeError("❌ No stat categories found in league settings")

stat_id_to_name = {
    str(stat.get("stat_id")): stat.get("name", f"Stat {stat.get('stat_id')}")
    for stat in stat_categories
}

# ---------- Resolve team safely ----------
teams = league.teams()
if not teams:
    raise RuntimeError("❌ No teams found in the league")

# handle both dict and list
if isinstance(teams, dict):
    team_key, team_obj = next(iter(teams.items()))
elif isinstance(teams, list):
    team_obj = teams[0]
    team_key = team_obj["team_key"]
else:
    raise RuntimeError("❌ Unexpected type for league.teams()")

print(f"🏒 League: {league_name}")
print(f"👥 Team key: {team_key}")
print(f"📅 Analyzing weeks 1 → {current_week}")

# ---------- Aggregate weekly stats ----------
team_stats = {}

for week in range(1, current_week + 1):
    print(f"🗂️ Week {week} stats...")

    # Using raw API to get team stats (avoids team.stats() AttributeError)
    raw = league.yhandler.get_scoreboard_raw(week=week)
    matchups = raw["fantasy_content"]["league"][1]["scoreboard"]["0"]["matchups"]

    # Find this team's matchup
    for matchup in matchups.values():
        teams_block = matchup["matchup"]["teams"]
        for t in teams_block.values():
            t_key = t["team"][0]["team_key"]
            if t_key == team_key:
                stats_list = t["team"][1]["team_stats"]["stats"]
                for s in stats_list:
                    sid = str(s["stat"]["stat_id"])
                    val = s["stat"]["value"]
                    try:
                        val = float(val)
                        team_stats[sid] = team_stats.get(sid, 0) + val
                    except ValueError:
                        continue

# ---------- Determine strengths and weaknesses ----------
strengths = []
weaknesses = []

for sid, val in team_stats.items():
    name = stat_id_to_name.get(sid, f"Stat {sid}")
    entry = {"stat_id": sid, "name": name, "value": val}
    if val > 0:
        strengths.append(entry)
    else:
        weaknesses.append(entry)

# ---------- Write output ----------
payload = {
    "league": league_name,
    "team_key": team_key,
    "weeks_analyzed": current_week,
    "strengths": sorted(strengths, key=lambda x: x["value"], reverse=True),
    "weaknesses": sorted(weaknesses, key=lambda x: x["value"]),
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, "w") as f:
    json.dump(payload, f, indent=2)

print(f"✅ Analysis written to {OUTPUT_FILE}")
