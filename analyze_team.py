import os
import json
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# ---------- Configuration ----------
LEAGUE_KEY = "465.l.33140"
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
league = gm.to_league(LEAGUE_KEY)

settings = league.settings()
league_name = settings["name"]
current_week = int(settings["current_week"])

print(f"🏒 League: {league_name}")
print(f"📅 Analyzing weeks 1 → {current_week}")

# ---------- Resolve Team ----------
teams = league.teams()   # dict keyed by team_key
team_key = next(iter(teams))
team = yfa.Team(oauth, team_key)

print(f"👥 Team key: {team_key}")

# ---------- Aggregate Weekly Stats ----------
totals = {}

for week in range(1, current_week + 1):
    print(f"🗂️ Week {week}")
    weekly_stats = team.stats(week)

    for s in weekly_stats:
        sid = str(s["stat_id"])
        val = s["value"]

        try:
            val = float(val)
        except (TypeError, ValueError):
            continue

        totals[sid] = totals.get(sid, 0) + val

# ---------- Build Output ----------
stats = [
    {
        "stat_id": sid,
        "value": round(val, 3)
    }
    for sid, val in totals.items()
]

payload = {
    "league": league_name,
    "team_key": team_key,
    "weeks_analyzed": current_week,
    "stats": sorted(stats, key=lambda x: x["value"], reverse=True),
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

# ---------- Write File ----------
os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
with open(OUTPUT_FILE, "w") as f:
    json.dump(payload, f, indent=2)

print(f"✅ Analysis written to {OUTPUT_FILE}")
