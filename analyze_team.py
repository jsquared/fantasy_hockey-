import json
from datetime import datetime
from yahoo_oauth import OAuth2
from yfantasy_api.teams import Team
from yfantasy_api.league import League

# --- CONFIG ---
LEAGUE_ID = "465.l.33140"       # Your league key
TEAM_KEY = "465.l.33140.t.11"   # Your team key
WEEKS_TO_ANALYZE = range(1, 13)  # Weeks 1 → 12

# Authenticate with Yahoo
oauth = OAuth2(None, None, from_file="oauth2.json")
if not oauth.token_is_valid():
    oauth.refresh_access_token()

print("🔑 Authenticated with Yahoo...")

# Initialize League object
league = League(LEAGUE_ID, oauth)

# Initialize Team object
team = Team(TEAM_KEY, oauth)

# Output structure
results = {
    "league": league.name,
    "team_key": TEAM_KEY,
    "weeks_analyzed": len(WEEKS_TO_ANALYZE),
    "total_stats": {},
    "weekly_stats": {},
    "lastUpdated": datetime.utcnow().isoformat()
}

# Loop through each week
for week in WEEKS_TO_ANALYZE:
    print(f"🗂️ Week {week}")
    
    try:
        # Fetch stats for the week
        stats = team.stats(week)
    except AttributeError:
        # Fallback if stats method isn’t available
        stats = league.team_stats(TEAM_KEY, week)
    
    results["weekly_stats"][str(week)] = stats or {}

    # Aggregate total stats
    for k, v in (stats or {}).items():
        results["total_stats"][k] = results["total_stats"].get(k, 0) + v

# Print results
print(json.dumps(results, indent=2))
