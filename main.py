# main.py
# A bot for Discord Linked Roles using the simple, non-bitwise method (for up to 5 roles).

import discord
from discord.ext import commands
import os
import requests
from flask import Flask, request, redirect
from threading import Thread

# --- Configuration ---

# These credentials must be set as Environment Variables in your Render dashboard.
try:
    BOT_TOKEN = os.environ['BOT_TOKEN']
    CLIENT_ID = os.environ['CLIENT_ID']
    CLIENT_SECRET = os.environ['CLIENT_SECRET']
    REDIRECT_URI = os.environ['REDIRECT_URI']
except KeyError as e:
    print(f"FATAL ERROR: The environment variable '{e.args[0]}' is not set.")
    print("Please configure all required secrets in your hosting environment.")
    exit()

# --- Your Server and Role IDs Have Been Added Below ---

# The ID of your server (guild).
GUILD_ID = 1400496639231393865

# This dictionary maps your Role IDs to the metadata keys.
# In the Discord Developer Portal, you must create a "Boolean" metadata field
# for each string key you define here (e.g., a field named "founder", "manager", etc.).
STAFF_ROLE_METADATA_MAP = {
    1400496639680057407: "founder",
    1400496639680057406: "manager",
    1400496639675990026: "developer",
    1400496639675990033: "moderator",
    1400496639675990028: "event_hoster"  # Using "event_hoster" to avoid spaces
}

# --- Discord Bot Setup ---
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!linkedroles-", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")
    print("Linked Roles Bot is operational.")
    print("---")


# --- Web Server for OAuth2 Authentication ---
app = Flask(__name__)

@app.route('/')
def home():
    oauth_url = f'https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope=role_connections.write%20identify'
    return f'<a href="{oauth_url}"><h1>Click here to verify your Staff Roles</h1></a>'


@app.route('/callback')
async def oauth_callback():
    code = request.args.get('code')
    if not code:
        return "Error: No authorization code provided by Discord.", 400

    data = {
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    try:
        token_response = requests.post('https://discord.com/api/v10/oauth2/token', data=data, headers=headers)
        token_response.raise_for_status()
        access_token = token_response.json()['access_token']
    except requests.RequestException as e:
        print(f"Error exchanging code for token: {e}")
        return "Failed to authenticate with Discord. Please try again.", 500

    headers = {'Authorization': f'Bearer {access_token}'}
    try:
        user_response = requests.get('https://discord.com/api/v10/users/@me', headers=headers)
        user_response.raise_for_status()
        user_id = int(user_response.json()['id'])
    except requests.RequestException as e:
        print(f"Error getting user info: {e}")
        return "Failed to retrieve user information from Discord.", 500

    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print(f"Error: Bot is not a member of the target guild (ID: {GUILD_ID}).")
        return "Server configuration error. Please contact an administrator.", 500

    member = guild.get_member(user_id)
    metadata = {} # Start with an empty dictionary for our metadata keys

    if member:
        member_role_ids = {role.id for role in member.roles}
        # This is the simple, non-bitwise logic.
        for role_id, metadata_key in STAFF_ROLE_METADATA_MAP.items():
            if role_id in member_role_ids:
                # If the user has a role, add its key to the metadata.
                # The value is set to 1, which represents "true".
                metadata[metadata_key] = 1

    url = f'https://discord.com/api/v10/users/@me/applications/{CLIENT_ID}/role-connection'
    payload = {
        'platform_name': 'Server Staff Roles',
        'metadata': metadata
    }
    try:
        requests.put(url, json=payload, headers=headers).raise_for_status()
    except requests.RequestException as e:
        print(f"Error pushing metadata: {e}")
        return "An error occurred while updating your linked role. Please try again.", 500

    return "<h1>✅ Verification Successful!</h1><p>Your roles have been linked. You can now close this browser tab.</p>"


def run_web_server():
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)


if __name__ == "__main__":
    flask_thread = Thread(target=run_web_server)
    flask_thread.daemon = True
    flask_thread.start()
    bot.run(BOT_TOKEN)
