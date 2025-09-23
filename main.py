from yahoo_oauth import OAuth2
import yahoo_fantasy_api as yfa
from datetime import datetime
import smtplib
from email.mime.text import MIMEText

# --- AUTH ---
oauth = OAuth2(None, None, from_file="oauth2.json")
game = yfa.Game(oauth, "nhl")
league_id = "465.l.33140"
league = game.to_league(league_id)

# --- TEAM INFO ---
team_key = league.team_key()
team = league.to_team(team_key)
today = datetime.now().strftime("%Y-%m-%d")

# --- FETCH ROSTER ---
roster = team.roster()

# --- SIMPLE LINEUP LOGIC ---
# (placeholder: bench inactive players, start active ones)
starters, bench = [], []
for p in roster:
    if p["status"] == "A":  # active today
        starters.append(p["name"])
    else:
        bench.append(p["name"])

# --- UPDATE LINEUP (write action) ---
# This depends on league settings - yahoo_fantasy_api supports edit_roster
# Example call:
# team.edit_roster(date=today, players=[list_of_player_keys])

# --- REPORT ---
report = f"""
Auto-GM Report - {today}

Starters set:
{starters}

Benched:
{bench}
"""

# --- SEND EMAIL ---
msg = MIMEText(report)
msg["Subject"] = f"Fantasy GM Lineup - {today}"
msg["From"] = "yourbot@email.com"
msg["To"] = "jknutson103@gmail.com"

with smtplib.SMTP("smtp.gmail.com", 587) as server:
    server.starttls()
    server.login("yourbot@email.com", "APP_PASSWORD")
    server.send_message(msg)

print("Lineup set + email sent!")
