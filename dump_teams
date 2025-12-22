import json
import yahoo_fantasy_api as yfa
from yahoo_oauth import OAuth2

oauth = OAuth2(None, None, from_file="oauth2.json")
gm = yfa.Game(oauth, "nhl")
league = gm.to_league("465.l.33140")

# Dump the teams object
teams_raw = league.teams()
with open("dump_teams.json", "w") as f:
    json.dump(teams_raw, f, indent=2)

print("✅ Dump written to dump_teams.json")
