import os
import json
from yahoo_oauth import OAuth2
from yahoofantasyapi import Game

# Load OAuth from environment variable
oauth_data = os.environ.get("YAHOO_OAUTH_JSON")
if not oauth_data:
    raise RuntimeError("YAHOO_OAUTH_JSON not found in environment variables")

# Write temporary oauth2.json
with open("oauth2_temp.json", "w") as f:
    f.write(oauth_data)

# Authenticate
oauth = OAuth2(None, None, from_file="oauth2_temp.json")

# Connect to Yahoo Fantasy Hockey
gm = Game(oauth, 'nhl')

# Get the first league you are in
leagues = gm.leagues()
if not leagues:
    raise RuntimeError("No leagues found for this account")

league = leagues[0]  # Adjust if needed
league_key = league.league_key

# Dump full league raw data
league_raw = league._yhandler.get_league_raw(league_key)

# Save to file for inspection
with open("league_dump.json", "w") as f:
    json.dump(league_raw, f, indent=2)

print(f"✅ League dump saved to league_dump.json")
