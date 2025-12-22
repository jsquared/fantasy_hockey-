import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# ---------------- CONFIG ----------------
LEAGUE_ID = "465.l.33140"
OUTPUT_FILE = "analysis.json"

# ---------- OAuth ----------
if "YAHOO_OAUTH_JSON" in os.environ:
    oauth_data = json.loads(os.environ["YAHOO_OAUTH_JSON"])
    with open("oauth2.json", "w") as f:
        json.dump(oauth_data, f)
    print("🔐 oauth2.json created from environment variable")

oauth = OAuth2(None, None, from_file="oauth2.json")
if not oauth.token_is_valid():
    print("⚠️ Yahoo OAuth token expired, refreshing...")
    oauth.refresh_access_token()

# ---------- Yahoo objects ----------
gm = yfa.Game(oauth, "nhl")
league = gm.to_league(LEAGUE_ID)

# Helper to safely unwrap Yahoo API lists/dicts
def unwrap(block):
    if isinstance(block, list):
        return block[0]
    return block

# ---------- Load stat categories ----------
print(f"🏒 League: {league.settings().get('name', LEAGUE_ID)}")
current_week = league.current_week()
weeks = list(range(1, current_week + 1))
print(f"📅 Analyzing weeks 1 → {current_week}")

settings_raw = league.yhandler.get_settings_raw(league.league_id)
league_block = settings_raw["fantasy_content"]["league"]
if isinstance(league_block, list):
    league_block = league_block[0]
settings = league_block.get("settings", {})
if not settings:
    raise RuntimeError("❌ Could not find 'settings' in league block")

stat_categories = settings.get("stat_categories", {}).get("stats", [])
stat_id_to_name = {str(stat.get("stat_id")): stat.get("name", f"Stat {stat.get('stat_id')}") for stat in stat_categories}

# ---------- Load my team ----------
teams_raw = league.yhandler.get_teams_raw(league.league_id)
teams_block = teams_raw["fantasy_content"]["league"]["0"]["teams"]
my_team_key = league.team_key()

my_team = None
for tk, tv in teams_block.items():
    if tk == "count":
        continue
    team_data = unwrap(tv["team"])
    if team_data[0]["team_key"] == my_team_key:
        my_team = team_data
        break

if not my_team:
    raise RuntimeError("❌ Could not find your team")

# ---------- Historical stats ----------
strengths = {}
weaknesses = {}

for week in weeks:
    raw_scoreboard = league.yhandler.get_scoreboard_raw(league.league_id, week)
    matchups = raw_scoreboard["fantasy_content"]["league"]["1"]["scoreboard"]
    # Find your matchup
    for k, v in matchups.items():
        if k == "count":
            continue
        matchup = v["matchup"]
        teams = matchup["0"]["teams"]
        for tk, tv in teams.items():
            if tk == "count":
                continue
            team_block = unwrap(tv["team"])
            if team_block[0]["team_key"] == my_team_key:
                stats_block = team_block[1].get("team_stats", {}).get("stats", [])
                for s in stats_block:
                    stat_id = str(s.get("stat", {}).get("stat_id"))
                    value = s.get("stat", {}).get("value")
                    if stat_id is None or value is None:
                        continue
                    # Aggregate
                    if value > 0:
                        strengths[stat_id] = strengths.get(stat_id, 0) + value
                    else:
                        weaknesses[stat_id] = weaknesses.get(stat_id, 0) + value

# ---------- Convert IDs to names ----------
strengths_list = [
    {"stat_id": k, "name": stat_id_to_name.get(k, f"Stat {k}"), "value": v}
    for k, v in strengths.items()
]
weaknesses_list = [
    {"stat_id": k, "name": stat_id_to_name.get(k, f"Stat {k}"), "value": v}
    for k, v in weaknesses.items()
]

# ---------- Output ----------
payload = {
    "league": league.settings().get("name", LEAGUE_ID),
    "team_key": my_team_key,
    "week": current_week,
    "strengths": sorted(strengths_list, key=lambda x: -x["value"]),
    "weaknesses": sorted(weaknesses_list, key=lambda x: x["value"]),
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open(os.path.join("docs", OUTPUT_FILE), "w") as f:
    json.dump(payload, f, indent=2)

print(f"✅ {OUTPUT_FILE} updated with historical analysis")
