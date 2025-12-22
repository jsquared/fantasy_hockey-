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

# ---------- Yahoo objects ----------
gm = yfa.Game(oauth, "nhl")
league = gm.to_league(LEAGUE_KEY)

settings = league.settings()
league_name = settings.get("name", "Unknown League")
current_week = int(settings.get("current_week", 1))

# ---------- Stat ID → Name ----------
stat_categories = settings.get("stat_categories", {}).get("stats", [])
stat_id_to_name = {
    str(s["stat_id"]): s.get("name", f"Stat {s['stat_id']}")
    for s in stat_categories
}

# ---------- Resolve YOUR team ----------
teams = league.teams()              # dict
team = next(iter(teams.values()))   # first team object
team_key = team["team_key"]

print(f"🏒 League: {league_name}")
print(f"👥 Team key: {team_key}")
print(f"📅 Analyzing weeks 1 → {current_week}")

# ---------- Aggregate stats ----------
team_totals = {}

for week in range(1, current_week + 1):
    print(f"🗂️ Week {week} stats...")

    # ✅ POSITIONAL ARGS — THIS IS THE FIX
    raw = league.yhandler.get_scoreboard_raw(LEAGUE_KEY, week)

    matchups = (
        raw.get("fantasy_content", {})
           .get("league", [{}])[1]
           .get("scoreboard", {})
           .get("matchups", {})
    )

    for matchup in matchups.values():
        if not isinstance(matchup, dict):
            continue

        teams_block = matchup.get("teams", {})
        for t in teams_block.values():
            if not isinstance(t, dict):
                continue

            if t.get("team_key") != team_key:
                continue

            stats = (
                t.get("team_stats", {})
                 .get("stats", {})
            )

            for s in stats.values():
                stat = s.get("stat", {})
                sid = str(stat.get("stat_id"))
                val = stat.get("value")

                try:
                    val = float(val)
                except (TypeError, ValueError):
                    continue

                team_totals[sid] = team_totals.get(sid, 0) + val

# ---------- Strengths & weaknesses ----------
strengths = []
weaknesses = []

for sid, val in team_totals.items():
    entry = {
        "stat_id": sid,
        "name": stat_id_to_name.get(sid, f"Stat {sid}"),
        "value": round(val, 3)
    }

    if val >= 0:
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
