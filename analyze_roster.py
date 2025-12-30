import json
import os
from datetime import datetime, timezone
from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa

# =========================
# CONFIG
# =========================
LEAGUE_ID = "465.l.33140"
GAME_CODE = "nhl"

# =========================
# OAuth (GitHub-safe)
# =========================
if "YAHOO_OAUTH_JSON" in os.environ:
    with open("oauth2.json", "w") as f:
        json.dump(json.loads(os.environ["YAHOO_OAUTH_JSON"]), f)

oauth = OAuth2(None, None, from_file="oauth2.json")

# =========================
# Yahoo Objects
# =========================
game = yfa.Game(oauth, GAME_CODE)
league = game.to_league(LEAGUE_ID)

current_week = league.current_week()
season = league.settings().get("season")
teams = league.teams()

# =========================
# Helpers
# =========================
def extract_stats(raw_stats):
    """Convert Yahoo stat array to dict"""
    stats = {}
    if not raw_stats:
        return stats

    stat_list = (
        raw_stats.get("fantasy_content", {})
        .get("player", [{}])[1]
        .get("player_stats", {})
        .get("stats", [])
    )

    for entry in stat_list:
        stat = entry.get("stat", {})
        stats[stat.get("stat_id")] = stat.get("value")

    return stats

# =========================
# Pull rosters + stats
# =========================
league_output = {}

for team_key, team_info in teams.items():
    print(f"Pulling roster for {team_key}")

    roster_raw = league.yhandler.get_roster_raw(team_key, current_week)
    team_block = roster_raw["fantasy_content"]["team"]

    team_data = {
        "team_key": team_key,
        "team_name": team_info.get("name"),
        "manager": None,
        "players": []
    }

    # Manager
    for section in team_block:
        if isinstance(section, dict) and "managers" in section:
            mgrs = section["managers"]
            if mgrs:
                team_data["manager"] = mgrs[0]["manager"].get("nickname")

    # Players
    roster_section = team_block[1]["roster"]["0"]["players"]

    for p in roster_section.values():
        if not isinstance(p, dict):
            continue

        player_arr = p["player"]
        meta = player_arr[0]

        player_key = meta[0]["player_key"]

        # Selected position
        selected_position = None
        if len(player_arr) > 1:
            for item in player_arr[1]:
                if "position" in item:
                    selected_position = item["position"]

        # Fetch stats (THIS IS THE IMPORTANT PART)
        raw_stats = league.yhandler.get_player_stats_raw(player_key, season)
        stats = extract_stats(raw_stats)

        player_data = {
            "player_key": player_key,
            "player_id": meta[1]["player_id"],
            "name": meta[2]["name"]["full"],
            "team": meta[6]["editorial_team_full_name"],
            "team_abbr": meta[7]["editorial_team_abbr"],
            "primary_position": meta[14],
            "eligible_positions": [p["position"] for p in meta[15]],
            "selected_position": selected_position,
            "stats": stats
        }

        team_data["players"].append(player_data)

    league_output[team_key] = team_data

# =========================
# OUTPUT
# =========================
payload = {
    "league": league.settings().get("name"),
    "week": current_week,
    "teams": league_output,
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(payload, f, indent=2)

print("✅ docs/roster.json updated with rosters + player stats")
