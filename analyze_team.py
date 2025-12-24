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
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)
    print("🔐 oauth2.json created from environment variable")

print("🔑 Authenticating with Yahoo...")
oauth = OAuth2(None, None, from_file="oauth2.json")

# ---------- Yahoo Objects ----------
gm = yfa.Game(oauth, "nhl")
league = gm.to_league(LEAGUE_ID)

settings = league.settings()
league_name = settings.get("name", "Unknown League")
current_week = league.current_week()

print(f"🏒 League: {league_name}")
print(f"📅 Analyzing weeks 1 → {current_week}")

# ---------- Load Stat Categories (RAW API — FINAL FIX) ----------
print("🗂️ Loading stat categories via raw league settings...")

raw = league.yhandler.get_league_settings_raw(LEAGUE_ID)

try:
    league_block = raw["fantasy_content"]["league"]
    settings_block = league_block["settings"]
    stat_blocks = settings_block["stat_categories"]["stats"]
except Exception as e:
    raise RuntimeError(f"❌ Failed to locate stat categories in raw API: {e}")

stat_id_to_name = {}

for item in stat_blocks:
    stat = item.get("stat", {})
    sid = stat.get("stat_id")
    name = stat.get("display_name") or stat.get("name")

    if sid is not None and name:
        stat_id_to_name[str(sid)] = name

if not stat_id_to_name:
    raise RuntimeError("❌ Stat categories parsed but empty")

print(f"✅ Loaded {len(stat_id_to_name)} stat categories")

# ---------- Identify Team ----------
teams = league.teams()
if not teams:
    raise RuntimeError("❌ No teams found")

my_team = teams[0]   # adjust index if needed
team_key = my_team["team_key"]

print(f"👥 Team key: {team_key}")

# ---------- Aggregate Weekly Stats ----------
team_totals = {}

for week in range(1, current_week + 1):
    print(f"🗂️ Week {week}")

    weekly_stats = league.team_stats(team_key, week)

    for stat_id, value in weekly_stats.items():
        try:
            team_totals[stat_id] = team_totals.get(stat_id, 0) + float(value)
        except (TypeError, ValueError):
            continue

# ---------- Strengths & Weaknesses ----------
strengths = []
weaknesses = []

for stat_id, total in team_totals.items():
    entry = {
        "stat_id": str(stat_id),
        "name": stat_id_to_name.get(str(stat_id), f"Stat {stat_id}"),
        "value": round(total, 2),
    }

    if total >= 0:
        strengths.append(entry)
    else:
        weaknesses.append(entry)

strengths.sort(key=lambda x: x["value"], reverse=True)
weaknesses.sort(key=lambda x: x["value"])

# ---------- Output ----------
payload = {
    "league": league_name,
    "team_key": team_key,
    "weeks_analyzed": current_week,
    "strengths": strengths,
    "weaknesses": weaknesses,
    "lastUpdated": datetime.now(timezone.utc).isoformat(),
}

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, "w") as f:
    json.dump(payload, f, indent=2)

print(f"✅ Analysis written to {OUTPUT_FILE}")
