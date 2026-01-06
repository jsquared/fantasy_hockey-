import json
import os
from datetime import datetime, timedelta, timezone

from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa


OUTPUT_PATH = "docs/roster.json"


def iso(d):
    return d.strftime("%Y-%m-%d")


def safe_player_block(p):
    """
    Yahoo player blocks can be:
    - dict
    - list
    - int (index)
    This normalizes it.
    """
    if isinstance(p, dict):
        return p
    if isinstance(p, list):
        for item in p:
            if isinstance(item, dict) and "player_id" in item:
                return item
    return None


def extract_stats(stats_block):
    """
    Converts Yahoo stat list → {stat_id: value}
    """
    out = {}
    if not stats_block:
        return out

    stats = stats_block.get("stats", [])
    for s in stats:
        stat = s.get("stat", {})
        sid = stat.get("stat_id")
        val = stat.get("value")
        if sid is not None and val is not None:
            try:
                out[str(sid)] = float(val)
            except ValueError:
                pass
    return out


def games_played(stats):
    """
    Yahoo does NOT always return GP explicitly.
    Stat ID 0 is usually GP when available.
    Fallback: assume games = 1 if stats exist.
    """
    if "0" in stats:
        return int(stats["0"])
    return 1 if stats else 0


def avg_stats(stats, gp):
    if gp <= 0:
        return {}
    return {k: round(v / gp, 3) for k, v in stats.items()}


def pull_range_stats(league, player_key, start_date, end_date):
    raw = league.yhandler.get(
        f"player/{player_key}/stats",
        params={"start_date": start_date, "end_date": end_date},
    )

    p = safe_player_block(raw.get("player"))
    if not p:
        return {}, 0

    stats = extract_stats(p.get("player_stats"))
    gp = games_played(stats)
    return stats, gp


def pull_season_stats(league, player_key):
    raw = league.yhandler.get(
        f"player/{player_key}/stats",
        params={"stats_type": "season"},
    )

    p = safe_player_block(raw.get("player"))
    if not p:
        return {}, 0

    stats = extract_stats(p.get("player_stats"))
    gp = games_played(stats)
    return stats, gp


def main():
    oauth = OAuth2(None, None, from_file="oauth.json")
    gm = yfa.Game(oauth, "nhl")
    league = gm.to_league("465.l.33140")

    team = league.to_team("465.l.33140.t.13")
    roster = team.roster()

    today = datetime.now(timezone.utc).date()

    windows = {
        "today": (today, today),
        "last_week": (today - timedelta(days=7), today - timedelta(days=1)),
        "last_2_weeks": (today - timedelta(days=14), today - timedelta(days=1)),
        "last_month": (today - timedelta(days=30), today - timedelta(days=1)),
    }

    output = {
        "league": league.settings()["name"],
        "team_key": team.team_key(),
        "generated": datetime.now(timezone.utc).isoformat(),
        "roster": [],
    }

    for slot in roster:
        p = safe_player_block(slot.get("player"))
        if not p:
            continue

        player_key = p["player_key"]
        player_id = p["player_id"]

        name = None
        team_abbr = None
        for item in p:
            if isinstance(item, dict):
                name = item.get("name", {}).get("full", name)
                team_abbr = item.get("editorial_team_abbr", team_abbr)

        selected_pos = slot.get("selected_position", {}).get("position")

        splits = {}

        for label, (start, end) in windows.items():
            stats, gp = pull_range_stats(
                league, player_key, iso(start), iso(end)
            )
            splits[label] = {
                "stats": stats,
                "games": gp,
            }
            splits[f"{label}_avg"] = {
                "stats": avg_stats(stats, gp)
            }

        season_stats, season_gp = pull_season_stats(league, player_key)
        splits["season"] = {
            "stats": season_stats,
            "games": season_gp,
        }
        splits["season_avg"] = {
            "stats": avg_stats(season_stats, season_gp)
        }

        output["roster"].append(
            {
                "player_id": player_id,
                "name": name,
                "editorial_team": team_abbr,
                "selected_position": selected_pos,
                "splits": splits,
            }
        )

    os.makedirs("docs", exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Roster stats written to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
