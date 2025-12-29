import json
from yahoo_oauth import OAuth2
from yfantasy_api.teams import Team
from yfantasy_api.league import League

# ---------------------------
# CONFIG
# ---------------------------
LEAGUE_ID = "465.l.33140"
TEAM_KEY = "465.l.33140.t.11"
MAX_WEEKS = 12

# ---------------------------
# AUTHENTICATE
# ---------------------------
yahoo = OAuth2(None, None, from_file="oauth2.json")
if not yahoo.token_is_valid():
    yahoo.refresh_access_token()

print("🔑 Authenticated with Yahoo...")

# ---------------------------
# GET LEAGUE
# ---------------------------
league = League(LEAGUE_ID, yahoo=yahoo)
print(f"🏒 League: {league.name}")

# ---------------------------
# DEBUG: Inspect raw matchups for week 1
# ---------------------------
week = 1
try:
    raw_matchups = league.matchups(week)
except Exception as e:
    print(f"❌ Error fetching matchups: {e}")
    raw_matchups = None

print("🗂️ RAW matchups for week 1:")
print(json.dumps(raw_matchups, indent=2))

# Stop here so you can inspect the output and see the correct keys
exit()

# ---------------------------
# PLACEHOLDER for processing weekly stats
# ---------------------------
# Once you know the correct structure, you can parse it like:
# weekly_stats = {}
# for matchup in raw_matchups:
#     for team in matchup['teams']:
#         if team['team_key'] == TEAM_KEY:
#             weekly_stats[week] = team['team_stats']
