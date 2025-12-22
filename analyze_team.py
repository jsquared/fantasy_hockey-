import json
from datetime import datetime
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa


# =========================
# Helpers
# =========================

def unwrap(node):
    """
    Yahoo API returns dicts and lists inconsistently.
    This safely unwraps both.
    """
    if isinstance(node, list):
        for item in node:
            if isinstance(item, dict):
                return item
    return node


# =========================
# Authenticate
# =========================

print("🔑 Authenticating with Yahoo...")

oauth = OAuth2(None, None, from_file="oauth2.json")

gm = yfa.Game(oauth, "nhl")
league = gm.to_league("465.l.33140")

print(f"🏒 League: {league.settings()['name']}")

# =========================
# Build stat_id → stat_name
# =========================

print("🗂️ Loading stat categories...")

stat_id_to_name = {}

settings_raw = league.yhandler.get_settings_raw(league.league_key)
settings = unwrap(settings_raw["fantasy_content"]["league"])

stat_cats = unwrap(settings["settings"])["stat_categories"]["stats"]

for s in stat_cats:
    stat = unwrap(s)["stat"]
    stat_id_to_name[str(stat["stat_id"])] = stat["name"]

# =========================
# Resolve your team
# =========================

print("👥 Resolving your team...")

my_team = None
teams_raw = league.teams()

for _, team_wrapper in teams_raw.items():
    if not isinstance(team_wrapper, dict):
        continue

    team_block = team_wrapper.get("team")
    if not team_block:
        continue

    team_block = unwrap(team_block)

    if isinstance(team_block, dict):
        team_key = team_block.get("team_key")
        if team_key and team_key.endswith(".t.13"):
            my_team = yfa.Team(oauth, team_key)
            break

if not my_team:
    raise RuntimeError("❌ Could not find your team")

print(f"✅ Found team: {my_team.team_key}")

# =========================
# Analyze all weeks
# =========================

current_week = int(league.current_week())
print(f"📅 Analyzing weeks 1 → {current_week}")

historical_totals = {}

for week in range(1, current_week + 1):
    stats_raw = my_team.yhandler.get_team_stats_raw(
        my_team.team_key, week
    )

    team_stats = (
        stats_raw["fantasy_content"]["team"][1]
        ["team_stats"]["stats"]
    )

    for item in team_stats:
        stat = unwrap(item)["stat"]
        stat_id = str(stat["stat_id"])
        value = float(stat["value"])

        historical_totals.setdefault(stat_id, []).append(value)

# =========================
# Compute averages
# =========================

averages = {
    stat_id: sum(vals) / len(vals)
    for stat_id, vals in historical_totals.items()
}

# =========================
# Strengths & Weaknesses
# =========================

sorted_stats = sorted(
    averages.items(), key=lambda x: x[1], reverse=True
)

strengths = sorted_stats[:8]
weaknesses = sorted_stats[-4:]

def format_block(items):
    return [
        {
            "stat_id": stat_id,
            "name": stat_id_to_name.get(stat_id, "Unknown"),
            "value": round(value, 3),
        }
        for stat_id, value in items
    ]

# =========================
# Output
# =========================

output = {
    "league": league.settings()["name"],
    "team_key": my_team.team_key,
    "weeks_analyzed": current_week,
    "strengths": format_block(strengths),
    "weaknesses": format_block(weaknesses),
    "lastUpdated": datetime.utcnow().isoformat() + "Z",
}

with open("analysis.json", "w") as f:
    json.dump(output, f, indent=2)

print("✅ analysis.json updated successfully")
