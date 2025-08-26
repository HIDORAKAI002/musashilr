import discord
from discord.ext import commands
import os
import requests
from flask import Flask, request, redirect
from threading import Thread

# --- Configuration (Loaded from Environment Variables) ---
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']
    CLIENT_ID = os.environ['CLIENT_ID']
    CLIENT_SECRET = os.environ['CLIENT_SECRET']
    REDIRECT_URI = os.environ['REDIRECT_URI']
    GUILD_ID = int(os.environ['GUILD_ID'])
except KeyError as e:
    print(f"FATAL ERROR: The environment variable '{e.args[0]}' is not set.")
    exit()

# This dictionary maps your Role IDs to unique powers of 2.
STAFF_ROLE_BITWISE_MAP = {
    1400496639680057407: 1,  # Founder (bit 0)
    1400496639680057406: 2,  # Manager (bit 1)
    1400496639675990033: 4,  # Moderation Team (bit 2)
    1400496639675990026: 8,  # Developer (bit 3)
    1400496639675990028: 16, # Event Management (bit 4)
    1401960472269291520: 32, # sky (bit 5)
}

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!lr-", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name}")
    print("Bitwise Linked Roles Bot is operational.")

# --- Web Server ---
app = Flask(__name__)
@app.route('/linked-role')
async def oauth_callback():
    code = request.args.get('code')
    if not code: return "Error: No code provided.", 400
    
    data = {'client_id': CLIENT_ID, 'client_secret': CLIENT_SECRET, 'grant_type': 'authorization_code', 'code': code, 'redirect_uri': REDIRECT_URI}
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        token_response = requests.post('https://discord.com/api/v10/oauth2/token', data=data, headers=headers)
        token_response.raise_for_status()
        access_token = token_response.json()['access_token']
    except requests.RequestException: return "Failed to authenticate.", 500

    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        user_response = requests.get('https://discord.com/api/v10/users/@me', headers=headers)
        user_response.raise_for_status()
        user_id = int(user_response.json()['id'])
    except requests.RequestException: return "Failed to retrieve user info.", 500

    guild = bot.get_guild(GUILD_ID)
    if not guild: return "Server config error.", 500

    member = guild.get_member(user_id)
    combined_role_value = 0 

    if member:
        member_role_ids = {role.id for role in member.roles}
        for role_id, bit_value in STAFF_ROLE_BITWISE_MAP.items():
            if role_id in member_role_ids:
                combined_role_value |= bit_value
    
    url = f'https://discord.com/api/v10/users/@me/applications/{CLIENT_ID}/role-connection'
    payload = {'platform_name': 'Server Staff Roles', 'metadata': {'staff_roles': combined_role_value}}
    try:
        requests.put(url, json=payload, headers=headers).raise_for_status()
    except requests.RequestException: return "Error updating linked role.", 500

    return "<h1>✅ Verification Successful!</h1>"

def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    flask_thread = Thread(target=run_web_server)
    flask_thread.daemon = True
    flask_thread.start()
    bot.run(BOT_TOKEN)
