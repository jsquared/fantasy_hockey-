import os
import json
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# ---------- Configuration ----------
LEAGUE_ID = "465.l.33140"  # Update this after checking available league keys
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

# ---------- Dump all leagues so we can confirm league key ----------
all_leagues_raw = gm.yhandler.get_leagues_raw()
print("🔍 Accessible leagues for this user:")
for k in all_leagues_raw.keys():
    print(" -", k)

# Attempt to find the correct league block
league_block = None
for k, v in all_leagues_raw.items():
    if LEAGUE_ID in k or k in LEAGUE_ID:
        league_block = v
        break

if not league_block:
    raise RuntimeError(f"❌ League ID {LEAGUE_ID} not found in raw API. Check the printed keys above.")

league = gm.to_league(LEAGUE_ID)

current_week = league.current_week()
league_name = league.settings().get("name", "Unknown League")

# ---------- Get stat categories safely ----------
stat_categories = league.settings().get("stat_categories", {}).get("stats", [])
if not stat_categories:
    print("⚠️ No stat categories found in league settings; trying raw API...")
    raw_game = gm.yhandler.get_game_raw()
    stat_categories = raw_game.get("fantasy_content", {}).get("game", [{}])[0].get(
        "stat_categories", []
    )
    if not stat_categories:
        raise RuntimeError("❌ No stat categories found anywhere")

stat_id_to_name = {
    str(stat.get("stat_id")): stat.get("name", f"Stat {stat.get('stat_id')}")
    for stat in stat_categories
}

# ---------- Aggregate weekly stats ----------
teams = league.teams()
if not teams:
    raise RuntimeError("❌ No teams found in league")

team = teams[0]  # Change index if needed
team_key = team["team_key"]

print(f"🏒 League: {league_name}")
print(f"👥 Team key: {team_key}")
print(f"📅 Analyzing weeks 1 → {current_week}")

team_stats = {}

for week in range(1, current_week + 1):
    print(f"🗂️ Week {week}")
    try:
        # Fetch weekly stats for this team
        raw_matchup = league.yhandler.get_matchups_raw(week)
        # Each matchup has 'teams' list
        for matchup in raw_matchup.get("fantasy_content", {}).get("league", {}).get("scoreboard", {}).get("matchups", {}).values():
            for m in matchup.values():
                if isinstance(m, dict) and "teams" in m:
                    for t in m["teams"].values():
                        if t.get("team_key") == team_key:
                            stats_list = t.get("team_stats", {}).get("stats", [])
                            for s in stats_list:
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
