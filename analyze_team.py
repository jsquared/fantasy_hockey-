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
print(f"🏒 League: {league.settings()['name']}")
print(f"📅 Analyzing weeks 1 → {current_week}")

# ---------- Load league stat categories safely ----------
settings_raw = league.yhandler.get_settings_raw(league.league_id)
league_block = settings_raw.get("fantasy_content", {}).get("league")

if isinstance(league_block, list):
    league_block = league_block[0]

settings = league_block.get("settings") if league_block else None
if not settings:
    print("⚠️ 'settings' not found in league block, dumping league_block for debugging:")
    print(json.dumps(league_block, indent=2))
    raise RuntimeError("❌ Could not find 'settings' in league block")

stat_categories = settings.get("stat_categories", {}).get("stats", [])
stat_id_to_name = {
    str(stat.get("stat_id")): stat.get("name", f"Stat {stat.get('stat_id')}")
    for stat in stat_categories
}

# ---------- Analyze each week ----------
team_stats = {}
for week in range(1, current_week + 1):
    print(f"🗂️ Week {week} stats...")
    scoreboard_raw = league.yhandler.get_scoreboard_raw(league.league_id, week)
    league_data = scoreboard_raw.get("fantasy_content", {}).get("league")
    if isinstance(league_data, list):
        league_data = league_data[1] if len(league_data) > 1 else league_data[0]

    matchups = league_data.get("scoreboard", {}).get("0", {}).get("matchups", {})

    for k, v in matchups.items():
        if k == "count":
            continue

        matchup = v.get("matchup")
        if not matchup:
            continue

        teams = matchup.get("0", {}).get("teams", {})
        my_team_data = None

        for tk, tv in teams.items():
            if tk == "count":
                continue
            tkey = tv.get("team", [{}])[0].get("team_key")
            if tkey == league.team_key():
                my_team_data = tv.get("team", [{}])[1].get("team_stats", {}).get("stats", [])
                break

        if my_team_data:
            for s in my_team_data:
                sid = str(s.get("stat", {}).get("stat_id"))
                val = s.get("stat", {}).get("value")
                if sid and val is not None:
                    team_stats[sid] = team_stats.get(sid, 0) + float(val)

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

# ---------- Output ----------
payload = {
    "league": league.settings()["name"],
    "team_key": league.team_key(),
    "week": current_week,
    "strengths": sorted(strengths, key=lambda x: x["value"], reverse=True),
    "weaknesses": sorted(weaknesses, key=lambda x: x["value"]),
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, "w") as f:
    json.dump(payload, f, indent=2)

print(f"✅ Analysis written to {OUTPUT_FILE}")
