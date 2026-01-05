import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

GAME_CODE = "nhl"
LEAGUE_ID = "465.l.33140"

# ---- OAuth bootstrap (CI-safe) ----
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

team_key = league.team_key()
team = league.to_team(team_key)

roster_output = []

for p in team.roster():
    pid = p["player_id"]
    stats = {}

    try:
        # Pull raw player stats
        raw_stats = league.player_stats(pid, "season")

        # raw_stats is usually a nested list -> list -> dict containing "player_stats"
        if isinstance(raw_stats, list):
            for pdata in raw_stats:
                if isinstance(pdata, list):
                    for item in pdata:
                        if isinstance(item, dict) and "player_stats" in item:
                            # Regular stats
                            season_block = item["player_stats"].get("0", {})
                            for stat_entry in season_block.get("stats", []):
                                stat = stat_entry.get("stat", {})
                                sid = stat.get("stat_id")
                                val = stat.get("value")
                                if sid is not None:
                                    try:
                                        stats[str(sid)] = float(val)
                                    except (TypeError, ValueError):
                                        stats[str(sid)] = val

                            # Advanced stats (optional)
                            adv_block = item.get("player_advanced_stats", {}).get("0", {})
                            for stat_entry in adv_block.get("stats", []):
                                stat = stat_entry.get("stat", {})
                                sid = stat.get("stat_id")
                                val = stat.get("value")
                                if sid is not None:
                                    key = f"adv_{sid}"
                                    try:
                                        stats[key] = float(val)
                                    except (TypeError, ValueError):
                                        stats[key] = val

    except Exception as e:
        print(f"⚠️ Could not fetch stats for {p.get('name')}: {e}")

    roster_output.append({
        "player_id": pid,
        "name": p.get("name"),
        "selected_position": p.get("selected_position"),
        "editorial_team": p.get("editorial_team_abbr"),
        "stats": stats
    })

# ---- Final payload ----
payload = {
    "league": league.settings().get("name"),
    "team_key": team_key,
    "generated": datetime.now(timezone.utc).isoformat(),
    "roster": roster_output
}

# ---- Save to docs/roster.json ----
os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json written successfully")
