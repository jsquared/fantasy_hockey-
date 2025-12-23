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

# Fallback to raw API if settings are empty
if not stat_categories:
    print("⚠️ Stat categories missing from settings, using raw API fallback")
    raw_league = gm.yhandler.get_leagues_raw()  # get all leagues for user
    league_block = next(iter(raw_league.get("fantasy_content", {}).values()), {})
    stat_categories = league_block.get("stat_categories", {}).get("stats", [])
    if not stat_categories:
        raise RuntimeError("❌ No stat categories found in league (even from raw API)")

stat_id_to_name = {
    str(stat.get("stat_id")): stat.get("name", f"Stat {stat.get('stat_id')}")
    for stat in stat_categories
}

# ---------- Aggregate weekly stats ----------
teams = league.teams()
if not teams:
    raise RuntimeError("❌ No teams found in league")

team = teams[0]  # adjust index if needed
team_key = team["team_key"]

print(f"🏒 League: {league_name}")
print(f"👥 Team key: {team_key}")
print(f"📅 Analyzing weeks 1 → {current_week}")

team_stats = {}

for week in range(1, current_week + 1):
    print(f"🗂️ Week {week}")
    try:
        all_teams_stats = league.stats(week)
        for t in all_teams_stats:
            if t["team_key"] == team_key:
                for s in t.get("stats", []):
                    sid = str(s.get("stat_id"))
                    val = s.get("value")
                    if sid and val is not None:
                        try:
                            team_stats[sid] = team_stats.get(sid, 0) + float(val)
                        except ValueError:
                            continue
    except Exception as e:
        print(f"⚠️ Error fetching stats for week {week}: {e}")

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
