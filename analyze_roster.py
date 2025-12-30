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
teams = league.teams()

# =========================
# Helpers
# =========================
def parse_player_stats(raw_stats):
    """
    Convert Yahoo stat blocks into {stat_id: value}
    """
    stats = {}
    if not raw_stats:
        return stats

    stat_list = raw_stats.get("stats", [])
    for entry in stat_list:
        stat = entry.get("stat", {})
        stats[stat.get("stat_id")] = stat.get("value")
    return stats

# =========================
# Main
# =========================
league_output = {}

for team_key, team in teams.items():
    print(f"Pulling roster for {team_key}")
    raw_roster = league.yhandler.get_roster_raw(team_key, current_week)

    team_block = raw_roster["fantasy_content"]["team"]
    roster_block = team_block[1]["roster"]["0"]["players"]

    players_out = []

    for entry in roster_block.values():
        if not isinstance(entry, dict):
            continue

        player_data = entry.get("player")
        if not player_data or not isinstance(player_data, list):
            continue

        info = player_data[0]

        player_key = info[0]["player_key"]
        player_id = info[1]["player_id"]
        name = info[2]["name"]["full"]
        team_name = info[6]["editorial_team_full_name"]
        team_abbr = info[7]["editorial_team_abbr"]
        primary_position = info[15]["primary_position"]

        # selected position
        selected_position = None
        if len(player_data) > 1:
            for item in player_data[1]:
                if isinstance(item, dict) and "position" in item:
                    selected_position = item["position"]

        # =========================
        # PLAYER STATS (SEPARATE CALL)
        # =========================
        raw_stats = league.yhandler.get_player_stats_raw(
            player_key,
            stats_type="season"
        )

        stats = {}
        try:
            stats_block = (
                raw_stats["fantasy_content"]["player"][1]["player_stats"]
            )
            stats = parse_player_stats(stats_block)
        except Exception:
            stats = {}

        players_out.append({
            "player_key": player_key,
            "player_id": player_id,
            "name": name,
            "team": team_name,
            "team_abbr": team_abbr,
            "primary_position": primary_position,
            "selected_position": selected_position,
            "stats": stats
        })

    league_output[team_key] = {
        "team_key": team_key,
        "team_name": team["name"],
        "players": players_out
    }

# =========================
# WRITE OUTPUT
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

print("✅ docs/roster.json updated with FULL rosters + player stats")
