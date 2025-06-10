# Core Discord Functionality
import discord
from discord.ext import commands, tasks
from discord.ui import Button, View

# Essential System and Helper Libraries
import asyncio
import configparser
import subprocess
import re
import os
import sys

# For System Information (only needed for !stats)
import psutil
import platform
import pkg_resources

# For Spotify Integration
import aiohttp
import base64

# For Timestamps and Logging
import datetime
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.FileHandler('discord_radio_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('RadioBot')

# Load configuration file
config = configparser.ConfigParser()
config.read('config.ini')

# Set up bot intents and create bot instance
intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents)

# Remove the default help command
bot.remove_command('help')

# FFmpeg options for audio streaming
ffmpeg_options = {
    'options': '-vn'
}

# Store the current stream URL and related info
current_stream_url = None
current_station = "No station playing"
current_title = "No title available"
last_posted_title = None

# Function to load configuration settings
def load_config():
    global token, channel_id, default_voice_channel_id, default_stream_url, default_volume_percentage
    global allowed_role_ids, client_id, radio_stations, BANNED_TITLES

    try:
        token = config['settings']['token']
        channel_id = int(config['settings']['channel_id'])
        default_voice_channel_id = int(config['settings']['default_voice_channel_id'])
        default_stream_url = config['settings']['default_stream_url']
        default_volume_percentage = int(config['settings']['default_volume'])
        allowed_role_ids = list(map(int, config['settings']['allowed_role_ids'].split(',')))
        client_id = config['settings']['client_id']

        # Load radio stations from config, handle possible KeyErrors
        radio_stations = {}
        for s in config.sections():
            if s.startswith('radio_stations'):
                for i in range(1, len(config[s]) + 1):
                    name_key = f'station{i}_name'
                    url_key = f'station{i}_url'
                    if name_key in config[s] and url_key in config[s]:
                        radio_stations[config[s][name_key]] = config[s][url_key]
        
        # Load banned titles for push (Wildcard/Teilstring-Suche)
        if 'push' in config and 'banned_titles' in config['push']:
            BANNED_TITLES = [
                title.strip()
                for title in config['push']['banned_titles'].split(',')
                if title.strip()
            ]
        else:
            BANNED_TITLES = []

        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        raise

# Load initial configuration
load_config()

# Function to fetch the stream title via ffmpeg
async def get_stream_title(url):
    """
    Returns the current stream title using ffmpeg.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            'ffmpeg', 
            '-re',
            '-i', url, 
            '-f', 'ffmetadata', 
            '-', 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE
        )
        _, stderr = await process.communicate()
        match = re.search(r'Title\s*:\s*(.*)', stderr.decode())
        title = match.group(1).strip() if match else 'Unknown Title'
        logger.debug(f"Stream title fetched: {title}")
        return title
    except Exception as e:
        logger.error(f"Error fetching stream title: {e}")
        return 'Unknown Title'

# Function to change the bot's nickname in a guild
async def nickname_change(guild, station_name, bot_user):
    """
    Changes the bot's nickname in the guild to reflect the current station.
    """
    try:
        member = guild.get_member(bot_user.id)
        if member:
            current_nick = member.display_name
            new_nick = f"# {station_name}"
            if current_nick != new_nick:
                await member.edit(nick=new_nick)
                logger.info(f"Bot nickname changed to '{new_nick}' in {guild.name}")
            else:
                logger.debug(f"Bot nickname already set to '{new_nick}' in {guild.name}")
        else:
            logger.warning(f"Bot user not found in guild {guild.name}")
    except discord.HTTPException as e:
        if e.code == 50035:
            logger.warning("Nickname change rate limited")
        elif e.code == 429:
            retry_after = e.retry_after
            logger.warning(f"Rate limit hit. Retrying after {retry_after} seconds")
            await asyncio.sleep(retry_after)
            await nickname_change(guild, station_name, bot_user)
        else:
            logger.error(f"Failed to change bot nickname: {e}")

# Function to fetch album cover image URL from Spotify API for a given track title
async def fetch_cover_image_url(title):
    """
    Fetches album cover image URL from Spotify API for a given track title.
    """
    try:
        config = configparser.ConfigParser()
        config.read('config.ini')
        client_id = config.get('spotify', 'client_id')
        client_secret = config.get('spotify', 'client_secret')
        async with aiohttp.ClientSession() as session:
            credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
            auth_response = await session.post(
                'https://accounts.spotify.com/api/token',
                data={'grant_type': 'client_credentials'},
                headers={'Authorization': f'Basic {credentials}'}
            )
            if auth_response.status != 200:
                logger.error(f"Failed to get Spotify access token. Status: {auth_response.status}")
                return 'default_cover_url'
            auth_data = await auth_response.json()
            access_token = auth_data['access_token']
            search_response = await session.get(
                f"https://api.spotify.com/v1/search",
                params={'q': title, 'type': 'track', 'limit': 1},
                headers={'Authorization': f'Bearer {access_token}'}
            )
            if search_response.status == 200:
                data = await search_response.json()
                if data['tracks']['items']:
                    track = data['tracks']['items'][0]
                    album = track['album']
                    if album['images']:
                        logger.info(f"Found cover image for track: {title}")
                        return album['images'][0]['url']
                logger.warning(f"No cover image found for track: {title}")
                return 'default_cover_url'
            else:
                logger.error(f"Spotify API search failed. Status: {search_response.status}")
                return 'default_cover_url'
    except Exception as e:
        logger.error(f"Error fetching cover image: {e}")
        return 'default_cover_url'

# Function to check if the stream has stopped and restart it
async def check_and_restart_stream(guild, url):
    """
    Checks whether the stream is still playing, and restarts it if necessary.
    """
    try:
        if not guild.voice_client:
            logger.warning(f"No voice client available in {guild.name}")
            return
        if not guild.voice_client.is_playing():
            logger.info(f"Stream stopped. Attempting to restart in {guild.name}")
            try:
                if guild.voice_client.is_playing():
                    guild.voice_client.stop()
                await asyncio.sleep(1)
                player = discord.FFmpegPCMAudio(url, **ffmpeg_options)
                guild.voice_client.play(
                    player, 
                    after=lambda e: bot.loop.create_task(check_and_restart_stream(guild, url)) if e else None
                )
                logger.info(f"Stream restarted successfully in {guild.name}")
            except Exception as restart_error:
                logger.error(f"Error restarting stream in {guild.name}: {restart_error}")
    except Exception as e:
        logger.error(f"Unexpected error in stream check for {guild.name}: {e}")

# Background task to monitor the stream and push updates only when the track actually changes

def load_banned_titles():
    if 'push' in config and 'banned_titles' in config['push']:
        return [
            title.strip()
            for title in config['push']['banned_titles'].split(',')
            if title.strip()
        ]
    else:
        return []

BANNED_TITLES = load_banned_titles()

def is_title_banned(title: str) -> bool:
    """Checks if any entry from the banlist is contained in the title (case-insensitive)."""
    return any(banned.lower() in title.lower() for banned in BANNED_TITLES)

@tasks.loop(seconds=5)
async def monitor_track():
    global last_posted_title
    try:
        if not current_stream_url:
            return
        title = await get_stream_title(current_stream_url)
        if not title or is_title_banned(title):
            if title and is_title_banned(title):
                logger.info(f"Track '{title}' matches banlist, skipping update.")
            return
        if title != last_posted_title:
            last_posted_title = title

            # --- Deine Push-Logik, z.B. Embed bauen und posten ---
            cover_url = await fetch_cover_image_url(title)
            activity = discord.Activity(type=discord.ActivityType.listening, name=title)
            await bot.change_presence(activity=activity)
            try:
                channel_id = int(config['spotify']['update_channel_id'])
                channel = bot.get_channel(channel_id)
                new_station_name = next(
                    (name for name, url in radio_stations.items() if url == current_stream_url),
                    "Unknown Station"
                )
                embed = discord.Embed(color=0x1DB954)
                embed.set_thumbnail(url=cover_url)
                embed.add_field(name="Now Playing", value=title, inline=False)
                embed.set_footer(text=f"{new_station_name}")
                await channel.send(embed=embed)
                logger.info(f"Pushed new track: {title} on {new_station_name}")
            except Exception as e:
                logger.error(f"Error posting track update: {e}")
    except Exception as e:
        logger.error(f"Error in monitor_track: {e}")

# Task for automatic fix execution (every 6 hours)
@tasks.loop(hours=6)
async def auto_fix():
    """
    Periodically triggers the fix_stream command to ensure the stream is running.
    Posts a visually enhanced embed in the channel to inform about the auto-fix.
    """
    try:
        logger.info("Starting automated fix execution")
        for guild in bot.guilds:
            # Check if the bot is connected to a voice client in this guild
            if guild.voice_client and guild.voice_client.is_connected():
                channel = bot.get_channel(channel_id)
                if channel:
                    # Try to get the current station name
                    station_name = next(
                        (name for name, url in radio_stations.items() if url == current_stream_url),
                        "Unknown Station"
                    )

                    # Create a visually appealing embed for the autofix
                    embed = discord.Embed(
                        title="🛠️ Auto-Fix Triggered",
                        description=(
                            f"The radio stream has been automatically checked and restarted if necessary.\n\n"
                            f"**Now playing:** `{station_name}`"
                        ),
                        color=discord.Color.blurple()
                    )
                    embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/727/727245.png")
                    embed.set_footer(
                        text="This was triggered by the auto-fix system.",
                        icon_url=guild.icon.url if guild.icon else discord.Embed.Empty
                    )
                    embed.timestamp = datetime.now()

                    await channel.send(embed=embed)
                    logger.info(f"Auto-fix embed sent in {guild.name}")

                    # Context is needed for fix_stream, simulate with a dummy message
                    ctx = await bot.get_context(await channel.send("(auto-fix)"))
                    await fix_stream(ctx)
                    logger.info(f"Auto-fix executed successfully in {guild.name}")
                else:
                    logger.warning(f"Could not find commands channel in {guild.name}")
    except Exception as e:
        logger.error(f"Error in auto_fix task: {e}")

# Event that triggers when the bot is ready
@bot.event
async def on_ready():
    """
    Handles actions when the bot connects and is ready.
    """
    logger.info(f"Logged in as {bot.user}")
    global current_stream_url
    current_stream_url = default_stream_url

    # Start background tasks
    monitor_track.start()
    auto_fix.start()
    logger.info("Started update_activity and auto_fix tasks")

    # Connect to default voice channel and start default station
    default_channel = bot.get_channel(default_voice_channel_id)
    if default_channel:
        try:
            if not default_channel.guild.voice_client:
                await default_channel.connect()
                logger.info(f"Connected to default channel: {default_channel.name}")
                station_name = next((name for name, url in radio_stations.items() if url == default_stream_url), "Unknown Station")
                voice_client = default_channel.guild.voice_client
                audio_source = discord.FFmpegPCMAudio(default_stream_url)
                voice_client.play(audio_source)
                logger.info(f"Playing {station_name} in default channel: {default_channel.name}")
            else:
                logger.info(f"Already connected to voice channel: {default_channel.name}")
                if default_channel.guild.voice_client.is_playing():
                    logger.info(f"Default station already playing in: {default_channel.name}")
                else:
                    station_name = next((name for name, url in radio_stations.items() if url == default_stream_url), "Unknown Station")
                    voice_client = default_channel.guild.voice_client
                    audio_source = discord.FFmpegPCMAudio(default_stream_url)
                    voice_client.play(audio_source)
                    logger.info(f"Started playing {station_name} in: {default_channel.name}")
        except Exception as e:
            logger.error(f"Error in on_ready event: {e}")

    # Update nicknames in all guilds
    for guild in bot.guilds:
        station_name = next((name for name, url in radio_stations.items() if url == current_stream_url), "Unknown Station")
        await nickname_change(guild, station_name, bot.user)

# Command to fix/restart the current stream with logging and event loop safe callback
@bot.command(name='fix', help='Fixes the FFmpeg stream by restarting it')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def fix_stream(ctx):
    """
    Restarts the current stream or the default stream if no stream is currently set.
    Provides a modern, visually enhanced embed as response.
    """
    global current_stream_url

    logger.info(f"Fix command initiated by {ctx.author} in {ctx.guild.name}")

    # Ensure the bot is connected to a voice channel
    if not ctx.voice_client:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
            logger.info(f"Connected to voice channel in {ctx.guild.name}")
        else:
            default_channel = bot.get_channel(default_voice_channel_id)
            if default_channel:
                await default_channel.connect()
                logger.info(f"Connected to default channel in {ctx.guild.name}")
            else:
                logger.error(f"Cannot connect to voice channel in {ctx.guild.name}")
                embed = discord.Embed(
                    title="❌ Connection Failed",
                    description="Cannot connect to any voice channel!",
                    color=discord.Color.red()
                )
                await ctx.send(embed=embed)
                return

    # Ensure current_stream_url is set
    if not current_stream_url:
        current_stream_url = default_stream_url
        logger.warning(f"No current stream found in {ctx.guild.name}, fallback to default")

    try:
        def after_playing(error):
            if error:
                logger.error(f"Playback error: {error} in {ctx.guild.name}")
            bot.loop.create_task(
                check_and_restart_stream(ctx.guild, current_stream_url)
            )

        # Stop current stream if playing
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            logger.info(f"Stopped current stream in {ctx.guild.name}")

        await asyncio.sleep(1)

        player = discord.FFmpegPCMAudio(current_stream_url, **ffmpeg_options)
        ctx.voice_client.play(player, after=after_playing)

        station_name = next((name for name, url in radio_stations.items() if url == current_stream_url), "Unknown Station")
        await nickname_change(ctx.guild, station_name, ctx.guild.me)

        embed = discord.Embed(
            title="🔄 Stream Restarted!",
            description=f"The stream was successfully restarted.\n\n**Now playing:** `{station_name}`",
            color=discord.Color.green()
        )
        embed.set_thumbnail(url="https://cdn-icons-png.flaticon.com/512/727/727245.png")  # Optional: add your own stream/radio icon
        embed.set_footer(
            text=f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.avatar.url if ctx.author.avatar else discord.Embed.Empty
        )
        embed.timestamp = datetime.now()

        await ctx.send(embed=embed)
        logger.info(f"Stream restarted: {station_name} in {ctx.guild.name}")

    except Exception as e:
        logger.error(f"Error in fix_stream: {str(e)} in {ctx.guild.name}")
        embed = discord.Embed(
            title="❌ Stream Error",
            description=f"Error starting stream: `{str(e)}`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

# Command to play a radio station by index or URL
@bot.command(name='play', help='Plays a radio station by index or URL')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def play(ctx, arg):
    """
    Plays a radio station by number or direct stream URL.
    """
    global current_stream_url

    logger.info(f"Play command initiated by {ctx.author} with arg: {arg}")

    # Join voice if not already connected
    if ctx.voice_client is None:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
            logger.info(f"Connected to voice channel in {ctx.guild.name}")
        else:
            await ctx.send(embed=discord.Embed(
                description=":x: **Du musst in einem Voice-Channel sein, um diesen Befehl zu nutzen.**",
                color=discord.Color.red()
            ))
            return

    if ctx.voice_client:
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            logger.info("Stopped current playback")

        try:
            # Radio-Station auswählen
            if arg.isdigit():
                index = int(arg)
                station_names = list(radio_stations.keys())
                if 1 <= index <= len(station_names):
                    station_name = station_names[index - 1]
                    url = radio_stations[station_name]
                    current_stream_url = url
                else:
                    await ctx.send(embed=discord.Embed(
                        description=f":warning: **Ungültige Sendernummer.** Es gibt nur {len(station_names)} Sender.",
                        color=discord.Color.orange()
                    ))
                    return
            else:
                url = arg
                station_name = "Custom URL"
                current_stream_url = url

            async with ctx.typing():
                title = await get_stream_title(url)
                if title:
                    player = discord.FFmpegPCMAudio(url, **ffmpeg_options)
                    ctx.voice_client.play(
                        player, 
                        after=lambda e: bot.loop.create_task(check_and_restart_stream(ctx.guild, url))
                    )
                    # Optional: Cover holen
                    cover_url = await fetch_cover_image_url(title)
                    embed = discord.Embed(
                        title="🎵 Now Playing",
                        color=0x1DB954  # Spotify-Grün
                    )
                    embed.add_field(name="Titel", value=title, inline=False)
                    embed.add_field(name="Sender", value=station_name, inline=False)
                    if cover_url:
                        embed.set_thumbnail(url=cover_url)
                    embed.set_footer(text=f"Angefordert von {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
                    await ctx.send(embed=embed)
                    logger.info(f"Started playing: {title} ({station_name})")
                else:
                    await ctx.send(embed=discord.Embed(
                        description=":x: **Fehler beim Abrufen des Stream-Titels.**",
                        color=discord.Color.red()
                    ))
                    logger.error("Error fetching stream title")
        except Exception as e:
            logger.error(f"Error in play command: {e}")
            await ctx.send(embed=discord.Embed(
                description=f":x: **Fehler beim Abspielen:** `{str(e)}`",
                color=discord.Color.red()
            ))

# Command to show available radio stations with a dropdown to play another station
@bot.command(name='radio', help='Displays available radio stations')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def stations(ctx):
    """
    Shows a visually enhanced dropdown menu for all available radio stations except the currently playing one.
    """
    global current_stream_url

    logger.info(f"Radio command initiated by {ctx.author} in {ctx.guild.name}")

    if not radio_stations:
        await ctx.send("No radio stations available.")
        return

    current_station_name = next((name for name, url in radio_stations.items() if url == current_stream_url), None)
    options = [
        discord.SelectOption(
            label=f"🎵 {station_name}",
            value=str(index),
            description=f"Select to play {station_name}"
        )
        for index, station_name in enumerate(radio_stations.keys(), start=1)
        if station_name != current_station_name
    ]

    select = discord.ui.Select(placeholder="🎧 Choose a radio station...", options=options, min_values=1, max_values=1)

    async def select_callback(interaction):
        global current_stream_url

        index = int(select.values[0])
        station_names = list(radio_stations.keys())
        station_name = station_names[index - 1]
        url = radio_stations[station_name]

        if current_stream_url != url:
            guild = interaction.guild
            voice_client = guild.voice_client

            current_stream_url = url  # Always update the current stream

            if voice_client and voice_client.is_connected():
                if voice_client.is_playing():
                    voice_client.stop()
                player = discord.FFmpegPCMAudio(url, **ffmpeg_options)
                voice_client.play(
                    player,
                    after=lambda e: bot.loop.create_task(check_and_restart_stream(guild, url))
                )
                await nickname_change(guild, station_name, guild.me)
                logger.info(f"Now playing: {station_name} in {guild.name}")
                embed = discord.Embed(
                    title="✅ Station switched!",
                    description=f"Now playing: **{station_name}**",
                    color=discord.Color.green()
                )
                embed.set_footer(text="Enjoy your music! 🎶")
                await interaction.response.send_message(embed=embed, ephemeral=True)
            else:
                await interaction.response.send_message("Bot is not in the voice channel! Please use !join.", ephemeral=True)
        else:
            embed = discord.Embed(
                title="ℹ️ Already Playing",
                description=f"**{station_name}** is already playing.",
                color=discord.Color.orange()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    select.callback = select_callback
    view = discord.ui.View()
    view.add_item(select)

    embed = discord.Embed(
        title="📻 Select a Radio Station",
        description="Use the dropdown below to switch to another station.\n\n"
                    "The currently playing station is not shown.",
        color=discord.Color.purple()
    )
    embed.set_footer(
        text="Tip: Use !listradio to see all stations with direct links.",
        icon_url=ctx.guild.icon.url if ctx.guild.icon else discord.Embed.Empty
    )
    embed.timestamp = datetime.now()

    await ctx.send(embed=embed, view=view)

# Command to stop playback
@bot.command(name='stop', help='Stops the playback')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def stop(ctx):
    """
    Stops the current audio playback.
    """
    logger.info(f"Stop command initiated by {ctx.author}")
    if ctx.voice_client:
        ctx.voice_client.stop()
        logger.info("Playback stopped")
        await ctx.send("Playback stopped")
    else:
        await ctx.send("Not playing anything!")
        logger.info("Stop command failed: Not playing anything")

# Command to adjust the volume (if supported)
@bot.command(name='vol', help='Adjusts volume (0-100)')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def vol(ctx, volume: int):
    """
    Adjusts the playback volume (if supported by the player).
    """
    logger.info(f"Volume command initiated by {ctx.author} with value: {volume}")
    if ctx.voice_client and ctx.voice_client.is_playing():
        if 0 <= volume <= 100:
            if hasattr(ctx.voice_client.source, "volume"):
                ctx.voice_client.source.volume = volume / 100.0
                logger.info(f"Volume set to {volume}%")
                await ctx.send(f"Volume set to {volume}%")
            else:
                await ctx.send("Volume control is not supported for this stream.")
                logger.warning("Volume control not supported")
        else:
            await ctx.send("Volume must be between 0 and 100")
            logger.warning(f"Invalid volume value attempted: {volume}")
    else:
        await ctx.send("Not playing anything!")
        logger.info("Volume command failed: Not playing anything")

# Command to join the user's voice channel
@bot.command(name='join', help='Joins your voice channel')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def join(ctx):
    """
    Joins the user's voice channel or the default channel.
    """
    logger.info(f"Join command initiated by {ctx.author}")
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        logger.info("Disconnected from current voice channel")

    if ctx.author.voice:
        await ctx.author.voice.channel.connect()
        logger.info(f"Joined voice channel: {ctx.author.voice.channel.name}")
        await ctx.send(f"Joined {ctx.author.voice.channel.name}")
    else:
        default_channel = bot.get_channel(default_voice_channel_id)
        if default_channel:
            await default_channel.connect()
            logger.info(f"Joined default channel: {default_channel.name}")
            await ctx.send(f"Joined default channel: {default_channel.name}")
        else:
            logger.error("Default voice channel not found")
            await ctx.send("Default voice channel not found!")

# Command to leave the voice channel
@bot.command(name='leave', help='Leaves the voice channel')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def leave(ctx):
    """
    Leaves the connected voice channel.
    """
    logger.info(f"Leave command initiated by {ctx.author}")
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        logger.info("Left voice channel")
        await ctx.send("Left voice channel")
    else:
        await ctx.send("I am not in a voice channel!")
        logger.info("Leave command failed: Not in a voice channel")

# Custom help command with detailed command information
@bot.command(name='help', help='Shows all available commands')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def help(ctx, command: str = None):
    """
    Displays the main help menu or detailed information for a specific command.
    """
    logger.info(f"Help command initiated by {ctx.author}")
    try:
        if command:
            command_details = {
                'radio': {
                    'title': '📻 Radio Command',
                    'description': 'Shows a dropdown menu with all available radio stations.',
                    'usage': '!radio',
                    'example': 'Just type !radio and select a station from the dropdown menu.'
                },
                'play': {
                    'title': '▶️ Play Command',
                    'description': 'Plays a radio station by number or direct stream URL.',
                    'usage': '!play <number/URL>',
                    'example': '!play 1\n!play http://stream.url'
                },
                'fix': {
                    'title': '🔧 Fix Command',
                    'description': 'Fixes stream issues by restarting the current stream.',
                    'usage': '!fix',
                    'example': 'Just type !fix when experiencing audio issues.'
                },
                'vol': {
                    'title': '🔊 Volume Command',
                    'description': 'Adjusts the playback volume.',
                    'usage': '!vol <0-100>',
                    'example': '!vol 50'
                },
                'join': {
                    'title': '➡️ Join Command',
                    'description': 'Makes the bot join your current voice channel.',
                    'usage': '!join',
                    'example': 'Just type !join while in a voice channel.'
                },
                'leave': {
                    'title': '⬅️ Leave Command',
                    'description': 'Makes the bot leave the current voice channel.',
                    'usage': '!leave',
                    'example': 'Just type !leave to disconnect the bot.'
                },
                'add': {
                    'title': '➕ Add Command',
                    'description': 'Adds a new radio station to the list.',
                    'usage': '!add <name> <url>',
                    'example': '!add "My Station" http://stream.url'
                },
                'remove': {
                    'title': '➖ Remove Command',
                    'description': 'Removes a radio station from the list.',
                    'usage': '!remove',
                    'example': 'Type !remove and select a station to remove.'
                },
                'stats': {
                    'title': '📊 Stats Command',
                    'description': 'Shows bot statistics and system information.',
                    'usage': '!stats',
                    'example': 'Just type !stats to see system information.'
                },
                'listradio': {
                    'title': '📋 List Radio Command',
                    'description': 'Shows a list of all configured radio stations.',
                    'usage': '!listradio',
                    'example': 'Just type !listradio to see all stations.'
                },
                'about': {
                    'title': 'ℹ️ About Command',
                    'description': 'Shows information about the bot.',
                    'usage': '!about',
                    'example': 'Just type !about to see bot information.'
                },
                'setdefault': {
                    'title': '⚙️ Set Default Command',
                    'description': 'Sets the default stream URL.',
                    'usage': '!setdefault <url>',
                    'example': '!setdefault http://stream.url'
                },
                'restart': {
                    'title': '🔄 Restart Command',
                    'description': 'Restarts the bot completely.',
                    'usage': '!restart',
                    'example': 'Just type !restart to reboot the bot.'
                },
                'reload': {
                    'title': '🔃 Reload Command',
                    'description': 'Reloads the bot configuration.',
                    'usage': '!reload',
                    'example': 'Just type !reload to refresh settings.'
                }
            }
            if command.lower() in command_details:
                cmd = command_details[command.lower()]
                embed = discord.Embed(
                    title=cmd['title'],
                    description=cmd['description'],
                    color=discord.Color.blue()
                )
                embed.add_field(name="Usage", value=f"```{cmd['usage']}```", inline=False)
                embed.add_field(name="Example", value=f"```{cmd['example']}```", inline=False)
                await ctx.send(embed=embed)
                logger.info(f"Detailed help displayed for command: {command}")
            else:
                await ctx.send(f"No detailed help available for command: {command}")
                logger.warning(f"Help requested for unknown command: {command}")
        else:
            embed = discord.Embed(
                title="📻 Radio Bot Commands",
                description="Here are all available commands:\nUse `!help <command>` for detailed information about a specific command.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="📻 Radio Controls",
                value="```\n!radio    - Show available stations\n!play #   - Play station by number\n!play URL - Play custom stream URL\n!stop     - Stop current playback\n!vol 0-100- Adjust volume\n!fix      - Fix stream issues```",
                inline=False
            )
            embed.add_field(
                name="🎤 Voice Channel Controls",
                value="```\n!join     - Join your voice channel\n!leave    - Leave voice channel```",
                inline=False
            )
            embed.add_field(
                name="⚙️ Station Management",
                value="```\n!add      - Add new radio station\n!remove   - Remove a radio station\n!listradio- List all radio stations```",
                inline=False
            )
            embed.add_field(
                name="🖥️ System Commands",
                value="```\n!stats    - Show bot statistics\n!about    - Show bot information\n!help     - Show this help message```",
                inline=False
            )
            embed.add_field(
                name="🔧 Admin Commands",
                value="```\n!setdefault - Set default stream URL\n!restart    - Restart the bot\n!reload     - Reload configuration```",
                inline=False
            )
            embed.set_footer(
                text=f"Requested by {ctx.author.name}",
                icon_url=ctx.author.avatar.url if ctx.author.avatar else None
            )
            await ctx.send(embed=embed)
            logger.info("Main help menu displayed")
    except Exception as e:
        logger.error(f"Error in help command: {e}")
        await ctx.send(f"Error displaying help: {str(e)}")

@bot.command(name='listradio', help='Lists all configured radio stations')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def listradio(ctx):
    """
    Lists all configured radio stations in a visually improved embed.
    """
    logger.info(f"listradio command initiated by {ctx.author} in {ctx.guild.name}")

    try:
        if not radio_stations:
            embed = discord.Embed(
                title="📻 Radio Stations",
                description="No radio stations found in configuration.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            logger.warning("No radio stations found in current configuration.")
            return

        embed = discord.Embed(
            title="📻 All Available Radio Stations",
            description="Here you can find all configured radio stations for this server.\n\n",
            color=discord.Color.green()
        )
        for index, (name, url) in enumerate(radio_stations.items(), 1):
            is_current = "🟢 **Currently playing**" if url == current_stream_url else ""
            embed.add_field(
            name=f"➖ {index}. {name}",
            value=f"[▶️ Listen]({url})" + ("\n" + is_current if is_current else ""),
            inline=False
        )

        embed.set_footer(
            text=f"Total Stations: {len(radio_stations)} • Use !radio to switch",
            icon_url=ctx.guild.icon.url if ctx.guild.icon else discord.Embed.Empty
        )
        embed.timestamp = datetime.now()

        await ctx.send(embed=embed)
        logger.info(f"Listed {len(radio_stations)} radio stations in {ctx.guild.name}")

    except Exception as e:
        logger.error(f"Error in listradio command: {e}")
        embed = discord.Embed(
            title="❌ Error",
            description=f"Could not read radio stations: {str(e)}",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

# Error event handler for command errors
@bot.event
async def on_command_error(ctx, error):
    """
    Generic error handler for command failures.
    """
    logger.error(f"Command error: {str(error)}")
    if isinstance(error, commands.CheckFailure):
        await ctx.send("You don't have permission to use this command or wrong channel.")
    else:
        await ctx.send(f"An error occurred: {str(error)}")

# Disconnection event
@bot.event
async def on_disconnect():
    """
    Handles bot disconnection events.
    """
    logger.warning("Bot disconnected. Attempting to reconnect...")

# Reconnection event
@bot.event
async def on_resumed():
    """
    Handles bot resuming events.
    """
    logger.info("Bot reconnected successfully")

# Voice state update for auto-move when alone
@bot.event
async def on_voice_state_update(member, before, after):
    """
    Handles bot movement back to the default voice channel if left alone.
    """
    if member == bot.user:
        await check_and_move_bot(member.guild)
    if before.channel and not after.channel:
        await check_and_move_bot(member.guild)

async def check_and_move_bot(guild):
    """
    If the bot is alone in a voice channel, moves it back to the default channel.
    """
    voice_client = guild.voice_client
    if voice_client and voice_client.channel:
        if len(voice_client.channel.members) == 1:
            default_channel = bot.get_channel(default_voice_channel_id)
            if default_channel and voice_client.channel.id != default_channel.id:
                await voice_client.move_to(default_channel)
                logger.info(f"Bot moved back to default channel: {default_channel.name}")

# Start the bot
if __name__ == "__main__":
    try:
        logger.info("Starting bot...")
        bot.run(token)
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
