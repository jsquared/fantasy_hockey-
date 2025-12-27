import os
import json
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# ---------------- CONFIG ----------------
LEAGUE_ID = "465.l.33140"
OUTPUT_FILE = "docs/analysis.json"

# ---------------- AUTH ------------------
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)
    print("🔐 oauth2.json created from environment variable")

print("🔑 Authenticating with Yahoo...")
oauth = OAuth2(None, None, from_file="oauth2.json")

# ---------------- OBJECTS ----------------
gm = yfa.Game(oauth, "nhl")
league = gm.to_league(LEAGUE_ID)

settings = league.settings()
league_name = settings.get("name", "Unknown League")
current_week = league.current_week()

print(f"🏒 League: {league_name}")
print(f"📅 Analyzing weeks 1 → {current_week}")

# ---------------- RAW SEARCH UTILS ----------------
def find_league_block(obj, league_id):
    """
    Recursively search Yahoo raw API for the target league block
    """
    if isinstance(obj, dict):
        if obj.get("league_key") == league_id:
            return obj
        for v in obj.values():
            found = find_league_block(v, league_id)
            if found:
                return found

    elif isinstance(obj, list):
        for item in obj:
            found = find_league_block(item, league_id)
            if found:
                return found

    return None

# ---------------- LOAD STAT CATEGORIES ----------------
print("🗂️ Loading stat categories from raw API (recursive search)...")

raw = league.yhandler.get_leagues_raw()

league_block = find_league_block(raw, LEAGUE_ID)

if not league_block:
    raise RuntimeError("❌ League not found anywhere in raw Yahoo response")

settings_block = league_block.get("settings")

if not settings_block:
    raise RuntimeError("❌ League settings missing")

stats_block = (
    settings_block
    .get("stat_categories", {})
    .get("stats", [])
)

if not stats_block:
    raise RuntimeError("❌ League contains no stat categories")

stat_id_to_name = {}

for entry in stats_block:
    stat = entry.get("stat", {})
    stat_id = stat.get("stat_id")
    name = stat.get("display_name") or stat.get("name")

    if stat_id is not None and name:
        stat_id_to_name[str(stat_id)] = name

print(f"✅ Loaded {len(stat_id_to_name)} stat categories")

# ---------------- TEAM ----------------
teams = league.teams()
if not teams:
    raise RuntimeError("❌ No teams found")

team = teams[0]  # change index if needed
team_key = team["team_key"]

print(f"👥 Team key: {team_key}")

# ---------------- WEEKLY STATS ----------------
team_totals = {}

for week in range(1, current_week + 1):
    print(f"🗂️ Week {week}")
    weekly_stats = league.team_stats(team_key, week)

    for stat_id, value in weekly_stats.items():
        try:
            team_totals[stat_id] = team_totals.get(stat_id, 0) + float(value)
        except (TypeError, ValueError):
            continue

# ---------------- ANALYSIS ----------------
strengths = []
weaknesses = []

for stat_id, total in team_totals.items():
    entry = {
        "stat_id": str(stat_id),
        "name": stat_id_to_name.get(str(stat_id), f"Stat {stat_id}"),
        "value": round(total, 2)
    }

    if total >= 0:
        strengths.append(entry)
    else:
        weaknesses.append(entry)

strengths.sort(key=lambda x: x["value"], reverse=True)
weaknesses.sort(key=lambda x: x["value"])

# ---------------- OUTPUT ----------------
payload = {
    "league": league_name,
    "team_key": team_key,
    "weeks_analyzed": current_week,
    "strengths": strengths,
    "weaknesses": weaknesses,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, "w") as f:
    json.dump(payload, f, indent=2)

print(f"✅ Analysis written to {OUTPUT_FILE}")
