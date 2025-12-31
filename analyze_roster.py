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
teams = league.teams()  # dict keyed by team_key

# =========================
# Helpers
# =========================
def extract_players_from_roster(raw_roster):
    """Safely extract player blocks from Yahoo roster payload"""
    team_block = raw_roster["fantasy_content"]["team"]
    roster_block = team_block[1]["roster"]

    players = []

    for key, slot in roster_block.items():
        if not key.isdigit():
            continue
        if "players" not in slot:
            continue

        for p in slot["players"].values():
            if not isinstance(p, dict):
                continue
            players.append(p)

    return players


def parse_player(player_block):
    """Extract metadata + selected position"""
    player_main = player_block["player"]

    meta = player_main[0]
    sel = player_main[1][0]["selected_position"][1]["position"]

    return {
        "player_key": meta.get("player_key"),
        "player_id": meta.get("player_id"),
        "name": meta.get("name", {}).get("full"),
        "team": meta.get("editorial_team_full_name"),
        "team_abbr": meta.get("editorial_team_abbr"),
        "primary_position": meta.get("primary_position"),
        "selected_position": sel,
    }


def get_season_stats(player_key):
    """Correct Yahoo call — NO extra params"""
    raw = league.yhandler.get_player_stats_raw(player_key)

    try:
        stats = raw["fantasy_content"]["player"][1]["player_stats"]["stats"]
    except Exception:
        return {}

    out = {}
    for s in stats:
        stat = s["stat"]
        out[stat["stat_id"]] = stat.get("value")

    return out


# =========================
# Main
# =========================
output = {
    "league": league.settings().get("name"),
    "week": current_week,
    "teams": {},
    "lastUpdated": datetime.now(timezone.utc).isoformat()
}

for team_key, team_meta in teams.items():
    print(f"Pulling roster for {team_key}")

    raw_roster = league.yhandler.get_roster_raw(team_key, current_week)
    players_raw = extract_players_from_roster(raw_roster)

    team_entry = {
        "team_key": team_key,
        "team_name": team_meta["name"],
        "manager": None,
        "players": []
    }

    for p in players_raw:
        try:
            player = parse_player(p)
            player["stats"] = get_season_stats(player["player_key"])
            team_entry["players"].append(player)
        except Exception as e:
            print(f"Skipping player due to parse error: {e}")

    output["teams"][team_key] = team_entry

# =========================
# Write Output
# =========================
os.makedirs("docs", exist_ok=True)
with open("docs/roster.json", "w") as f:
    json.dump(output, f, indent=2)

print("✅ docs/roster.json written successfully")
