import os
import json
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# ---------- Config ----------
LEAGUE_KEY = "465.l.33140"
OUTPUT_FILE = "docs/analysis.json"

# ---------- OAuth ----------
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

print("🔑 Authenticating with Yahoo...")
oauth = OAuth2(None, None, from_file="oauth2.json")

# ---------- Yahoo Objects ----------
gm = yfa.Game(oauth, "nhl")
league = gm.to_league(LEAGUE_KEY)

settings = league.settings()
league_name = settings["name"]
current_week = int(settings["current_week"])

# ---------- Stat Categories ----------
stat_id_to_name = {
    str(s["stat_id"]): s["name"]
    for s in settings["stat_categories"]["stats"]
}

# ---------- Resolve YOUR Team ----------
teams = league.teams()
team_meta = next(iter(teams.values()))
team_key = team_meta["team_key"]

team = yfa.Team(oauth, team_key)  # ✅ THIS IS THE KEY FIX

print(f"🏒 League: {league_name}")
print(f"👥 Team key: {team_key}")
print(f"📅 Analyzing weeks 1 → {current_week}")

# ---------- Aggregate Stats ----------
totals = {}

for week in range(1, current_week + 1):
    print(f"🗂️ Week {week}")

    stats = team.stats(week)  # ✅ WORKS FOR NHL

    for s in stats:
        sid = str(s["stat_id"])
        val = s["value"]

        try:
            val = float(val)
        except (TypeError, ValueError):
            continue

        totals[sid] = totals.get(sid, 0) + val

# ---------- Strengths / Weaknesses ----------
strengths = []
weaknesses = []

for sid, val in totals.items():
    entry = {
        "stat_id": sid,
        "name": stat_id_to_name.get(sid, f"Stat {sid}"),
        "value": round(val, 3)
    }

    if val >= 0:
        strengths.append(entry)
    else:
        weaknesses.append(entry)

# ---------- Output ----------
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
