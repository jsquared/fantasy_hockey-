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
league_settings = league.settings()
league_name = league_settings.get("name", "Unknown League")

# ---------- Get stat categories ----------
stat_categories = league_settings.get("stat_categories", {}).get("stats", [])
stat_id_to_name = {
    str(stat.get("stat_id")): stat.get("name", f"Stat {stat.get('stat_id')}")
    for stat in stat_categories
}

# ---------- Identify your team ----------
teams = league.teams()
if not teams:
    raise RuntimeError("❌ No teams found in league!")
team = teams[0]  # change index if needed
team_key = team["team_key"]

print(f"🏒 League: {league_name}")
print(f"👥 Team key: {team_key}")
print(f"📅 Analyzing weeks 1 → {current_week}")

# ---------- Aggregate stats over all weeks ----------
team_stats = {}

for week in range(1, current_week + 1):
    print(f"🗂️ Week {week} stats...")
    scoreboard = league.scoreboard(week)
    # scoreboard contains "teams" with their stats
    my_team_data = next(
        (t for t in scoreboard["teams"] if t["team_key"] == team_key), None
    )
    if not my_team_data:
        print(f"⚠️ Team not found in week {week}")
        continue

    # Extract stats safely
    weekly_stats = my_team_data.get("team_stats", {}).get("stats", [])
    for s in weekly_stats:
        stat_id = str(s["stat"].get("stat_id"))
        value = s["stat"].get("value", 0)
        try:
            value = float(value)
        except (ValueError, TypeError):
            continue
        team_stats[stat_id] = team_stats.get(stat_id, 0) + value

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
    "week": current_week,
    "strengths": sorted(strengths, key=lambda x: x["value"], reverse=True),
    "weaknesses": sorted(weaknesses, key=lambda x: x["value"]),
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, "w") as f:
    json.dump(payload, f, indent=2)

print(f"✅ Analysis written to {OUTPUT_FILE}")
