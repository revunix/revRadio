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

# For System Information
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
bot.remove_command('help')  # Add this line here

# FFmpeg options for audio streaming
ffmpeg_options = {
    'options': '-vn'
}
# Store the current stream URL and station information
current_stream_url = None
current_station = "No station playing"
current_title = "No title available"

async def fetch_cover_image_url(title):
    """
    Fetches album cover image URL from Spotify API for a given track title.
    
    Args:
        title (str): The title of the track to search for
        
    Returns:
        str: URL of the album cover image, or default cover URL if not found
    """
    try:
        # Load Spotify credentials from config
        config = configparser.ConfigParser()
        config.read('config.ini')
        client_id = config.get('spotify', 'client_id')
        client_secret = config.get('spotify', 'client_secret')
        
        # Get Spotify access token
        async with aiohttp.ClientSession() as session:
            # Encode credentials
            credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
            
            # Get access token
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
            
            # Search for track
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
    
# Function to load configuration settings
def load_config():
    global token, channel_id, default_voice_channel_id, default_stream_url, default_volume_percentage, allowed_role_ids, client_id, radio_stations
    try:
        token = config['settings']['token']
        channel_id = int(config['settings']['channel_id'])
        default_voice_channel_id = int(config['settings']['default_voice_channel_id'])
        default_stream_url = config['settings']['default_stream_url']
        default_volume_percentage = int(config['settings']['default_volume'])
        allowed_role_ids = list(map(int, config['settings']['allowed_role_ids'].split(',')))
        client_id = config['settings']['client_id']

        # Modified radio_stations loading to handle potential KeyErrors
        radio_stations = {}
        for s in config.sections():
            if s.startswith('radio_stations'):
                for i in range(1, len(config[s]) + 1):
                    name_key = f'station{i}_name'
                    url_key = f'station{i}_url'
                    if name_key in config[s] and url_key in config[s]:
                        radio_stations[config[s][name_key]] = config[s][url_key]
        logger.info("Configuration loaded successfully")
    except Exception as e:
        logger.error(f"Error loading configuration: {e}")
        raise

# Load initial configuration
load_config()

# Stream title fetching function
async def get_stream_title(url):
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

# Nickname change function
async def nickname_change(guild, station_name, bot_user):
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

# Stream check and restart function
async def check_and_restart_stream(guild, url):
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
                    after=lambda e: asyncio.create_task(check_and_restart_stream(guild, url)) if e else None
                )
                
                logger.info(f"Stream restarted successfully in {guild.name}")
            
            except Exception as restart_error:
                logger.error(f"Error restarting stream in {guild.name}: {restart_error}")
        
    except Exception as e:
        logger.error(f"Unexpected error in stream check for {guild.name}: {e}")

# Task to update bot activity
@tasks.loop(seconds=120)
async def update_activity():
    try:
        title = await get_stream_title(current_stream_url)
        track_name = f"{title}"

        cover_url = await fetch_cover_image_url(title)

        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=track_name
        )

        if bot.activity and bot.activity.name == track_name:
            logger.debug("Track already set, skipping update")
            return

        await bot.change_presence(activity=activity)
        
        try:
            config = configparser.ConfigParser()
            config.read('config.ini')
            channel_id = int(config['spotify']['update_channel_id'])
            channel = bot.get_channel(channel_id)

            last_message = None
            async for message in channel.history(limit=1):
                last_message = message
                break

            if last_message and last_message.embeds:
                last_embed = last_message.embeds[0]
                if last_embed.fields and last_embed.fields[0].value == track_name:
                    logger.debug("Track already posted, skipping update")
                    return

            embed = discord.Embed(color=0x1DB954)
            embed.set_thumbnail(url=cover_url)
            embed.add_field(name="Now Playing", value=track_name, inline=False)
            new_station_name = next((name for name, url in radio_stations.items() if url == current_stream_url), "Unknown Station")
            embed.set_footer(text=f"{new_station_name}", icon_url="")

            await channel.send(embed=embed)
            logger.info(f"Activity updated: Now playing {track_name} on {new_station_name}")
        except Exception as e:
            logger.error(f"Error updating activity message: {e}")
    except Exception as e:
        logger.error(f"Error in update_activity: {e}")

# Task for automatic fix execution
@tasks.loop(hours=6)
async def auto_fix():
    try:
        logger.info("Starting automated fix execution")
        for guild in bot.guilds:
            if guild.voice_client and guild.voice_client.is_connected():
                channel = bot.get_channel(channel_id)
                if channel:
                    ctx = await bot.get_context(await channel.send("Auto-fix initiated"))
                    await fix_stream(ctx)
                    logger.info(f"Auto-fix executed successfully in {guild.name}")
                else:
                    logger.warning(f"Could not find commands channel in {guild.name}")
    except Exception as e:
        logger.error(f"Error in auto_fix task: {e}")

# Bot ready event
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user}")
    global current_stream_url
    current_stream_url = default_stream_url
    
    # Start background tasks
    update_activity.start()
    auto_fix.start()
    logger.info("Started update_activity and auto_fix tasks")
    
    # Connect to default voice channel
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

# Fix stream command
@bot.command(name='fix', help='Fixes the FFmpeg stream by restarting it')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def fix_stream(ctx):
    global current_stream_url

    logger.info(f"Fix command initiated by {ctx.author} in {ctx.guild.name}")

    # Sicherstellen, dass bot im Voice-Channel ist
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
                await ctx.send("Cannot connect to voice channel!")
                return

    # Sicherstellen, dass ein Stream gesetzt ist
    if not current_stream_url:
        current_stream_url = default_stream_url
        logger.warning(f"No current stream found in {ctx.guild.name}, fallback to default")
        await ctx.send("No current stream found, starting default station.")

    try:
        def after_playing(error):
            if error:
                logger.error(f"Playback error: {error} in {ctx.guild.name}")

            # Restart-Task
            bot.loop.create_task(
                check_and_restart_stream(ctx.guild, current_stream_url)
            )

        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            logger.info(f"Stopped current stream in {ctx.guild.name}")

        await asyncio.sleep(1)

        player = discord.FFmpegPCMAudio(current_stream_url, **ffmpeg_options)
        ctx.voice_client.play(player, after=after_playing)

        station_name = next((name for name, url in radio_stations.items() if url == current_stream_url), "Unknown Station")
        await nickname_change(ctx.guild, station_name, ctx.guild.me)

        logger.info(f"Stream restarted: {station_name} in {ctx.guild.name}")
        await ctx.send(f"Stream restarted: {station_name}")

    except Exception as e:
        logger.error(f"Error in fix_stream: {str(e)} in {ctx.guild.name}")
        await ctx.send(f"Error starting stream: {str(e)}")


# Error handling
@bot.event
async def on_command_error(ctx, error):
    logger.error(f"Command error: {str(error)}")

    if isinstance(error, commands.CheckFailure):
        await ctx.send("You don't have permission to use this command or wrong channel.")
    else:
        await ctx.send(f"An error occurred: {str(error)}")

# Disconnection handling
@bot.event
async def on_disconnect():
    logger.warning("Bot disconnected. Attempting to reconnect...")

@bot.event
async def on_resumed():
    logger.info("Bot reconnected successfully")

# Voice state update handling
@bot.event
async def on_voice_state_update(member, before, after):
    if member == bot.user:
        await check_and_move_bot(member.guild)
    if before.channel and not after.channel:
        await check_and_move_bot(member.guild)

async def check_and_move_bot(guild):
    voice_client = guild.voice_client
    if voice_client and voice_client.channel:
        if len(voice_client.channel.members) == 1:
            default_channel = bot.get_channel(default_voice_channel_id)
            if default_channel and voice_client.channel.id != default_channel.id:
                await voice_client.move_to(default_channel)
                logger.info(f"Bot moved back to default channel: {default_channel.name}")

# Commands for radio station management
@bot.command(name='radio', help='Displays available radio stations')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def stations(ctx):
    logger.info(f"Radio command initiated by {ctx.author} in {ctx.guild.name}")

    if not radio_stations:
        await ctx.send("No radio stations available.")
        return

    current_station_name = next((name for name, url in radio_stations.items() if url == current_stream_url), None)

    options = [
        discord.SelectOption(label=station_name, value=str(index))
        for index, station_name in enumerate(radio_stations.keys(), start=1)
        if station_name != current_station_name
    ]

    select = discord.ui.Select(placeholder="Choose a radio station...", options=options)

    async def select_callback(interaction):
        index = int(select.values[0])
        station_names = list(radio_stations.keys())
        station_name = station_names[index - 1]
        url = radio_stations[station_name]

        global current_stream_url

        if current_stream_url != url:
            guild = interaction.guild
            voice_client = guild.voice_client

            if voice_client and voice_client.is_connected():
                if voice_client.is_playing():
                    voice_client.stop()
                player = discord.FFmpegPCMAudio(url, **ffmpeg_options)
                voice_client.play(
                    player,
                    after=lambda e: bot.loop.create_task(check_and_restart_stream(guild, url))
                )
                current_stream_url = url
                await nickname_change(guild, station_name, guild.me)
                await interaction.response.send_message(f"Now playing: {station_name}", ephemeral=True)
            else:
                await interaction.response.send_message("Bot ist nicht im Voice-Channel! Bitte nutze !join.", ephemeral=True)
        else:
            await interaction.response.send_message(f"Already playing: {station_name}", ephemeral=True)

    select.callback = select_callback
    view = discord.ui.View()
    view.add_item(select)

    embed = discord.Embed(
        title="📻 Available Radio Stations",
        description="Select a station from the dropdown menu",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=view)

@bot.command(name='play', help='Plays a radio station by index or URL')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def play(ctx, arg):
    logger.info(f"Play command initiated by {ctx.author} with arg: {arg}")
    
    if ctx.voice_client is None:
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
            logger.info(f"Connected to voice channel in {ctx.guild.name}")
        else:
            await ctx.send("You must be in a voice channel to use this command.")
            return

    if ctx.voice_client:
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            logger.info("Stopped current playback")

        try:
            if arg.isdigit():
                index = int(arg)
                station_names = list(radio_stations.keys())
                if 1 <= index <= len(station_names):
                    station_name = station_names[index - 1]
                    url = radio_stations[station_name]
                else:
                    await ctx.send("Invalid station number.")
                    return
            else:
                url = arg
                station_name = "Custom URL"

            async with ctx.typing():
                title = await get_stream_title(url)
                if title:
                    player = discord.FFmpegPCMAudio(url, **ffmpeg_options)
                    ctx.voice_client.play(
                        player, 
                        after=lambda e: asyncio.create_task(check_and_restart_stream(ctx.guild, url))
                    )
                    await ctx.send(f"Now playing: {station_name if arg.isdigit() else title}")
                    logger.info(f"Started playing: {station_name if arg.isdigit() else title}")
                else:
                    await ctx.send("Error fetching stream title.")
                    logger.error("Error fetching stream title")
        except Exception as e:
            logger.error(f"Error in play command: {e}")
            await ctx.send(f"Error playing stream: {str(e)}")

@bot.command(name='stop', help='Stops the playback')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def stop(ctx):
    logger.info(f"Stop command initiated by {ctx.author}")
    if ctx.voice_client:
        ctx.voice_client.stop()
        logger.info("Playback stopped")
        await ctx.send("Playback stopped")
    else:
        await ctx.send("Not playing anything!")
        logger.info("Stop command failed: Not playing anything")

@bot.command(name='vol', help='Adjusts volume (0-100)')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def vol(ctx, volume: int):
    logger.info(f"Volume command initiated by {ctx.author} with value: {volume}")
    if ctx.voice_client and ctx.voice_client.is_playing():
        if 0 <= volume <= 100:
            ctx.voice_client.source.volume = volume / 100.0
            logger.info(f"Volume set to {volume}%")
            await ctx.send(f"Volume set to {volume}%")
        else:
            await ctx.send("Volume must be between 0 and 100")
            logger.warning(f"Invalid volume value attempted: {volume}")
    else:
        await ctx.send("Not playing anything!")
        logger.info("Volume command failed: Not playing anything")

@bot.command(name='join', help='Joins your voice channel')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def join(ctx):
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

@bot.command(name='leave', help='Leaves the voice channel')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def leave(ctx):
    logger.info(f"Leave command initiated by {ctx.author}")
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        logger.info("Left voice channel")
        await ctx.send("Left voice channel")
    else:
        await ctx.send("I am not in a voice channel!")
        logger.info("Leave command failed: Not in a voice channel")

# Help Command with detailed command information
@bot.command(name='help', help='Shows all available commands')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def help(ctx, command: str = None):
    logger.info(f"Help command initiated by {ctx.author}")
    try:
        if command:
            # Dictionary with detailed command descriptions
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

            # Radio Controls
            embed.add_field(
                name="📻 Radio Controls",
                value="```\n!radio    - Show available stations\n!play #   - Play station by number\n!play URL - Play custom stream URL\n!stop     - Stop current playback\n!vol 0-100- Adjust volume\n!fix      - Fix stream issues```",
                inline=False
            )

            # Voice Channel Controls
            embed.add_field(
                name="🎤 Voice Channel Controls",
                value="```\n!join     - Join your voice channel\n!leave    - Leave voice channel```",
                inline=False
            )

            # Station Management
            embed.add_field(
                name="⚙️ Station Management",
                value="```\n!add      - Add new radio station\n!remove   - Remove a radio station\n!listradio- List all radio stations```",
                inline=False
            )

            # System Commands
            embed.add_field(
                name="🖥️ System Commands",
                value="```\n!stats    - Show bot statistics\n!about    - Show bot information\n!help     - Show this help message```",
                inline=False
            )

            # Admin Commands
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

@bot.command(name='stats', help='Shows bot statistics')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def stats(ctx):
    logger.info(f"Stats command initiated by {ctx.author}")
    try:
        cpu_usage = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        embed = discord.Embed(title="📊 Bot Statistics & System Information", color=0x00ff00)
        
        # Bot Info
        embed.add_field(
            name="🤖 Bot Status", 
            value=f"```\nStatus: 🟢 Online\nLatency: {round(bot.latency * 1000)}ms\nMemory: {round(psutil.Process().memory_info().rss / 1024 ** 2, 2)}MB```",
            inline=False
        )
        
        # System Info
        embed.add_field(
            name="💻 System Info", 
            value=f"```\nOS: {platform.system()} {platform.release()}\nCPU Usage: {cpu_usage}%\nRAM: {memory.percent}% ({round(memory.used/1024**3, 1)}/{round(memory.total/1024**3, 1)}GB)\nDisk: {disk.percent}% ({round(disk.used/1024**3, 1)}/{round(disk.total/1024**3, 1)}GB)```",
            inline=False
        )
        
        # Versions
        embed.add_field(
            name="📚 Versions", 
            value=f"```\nPython: {platform.python_version()}\nDiscord.py: {discord.__version__}```",
            inline=False
        )
        
        # Uptime
        process = psutil.Process()
        uptime = datetime.now() - datetime.fromtimestamp(process.create_time())
        embed.add_field(
            name="⏰ Uptime", 
            value=f"```\n{str(uptime).split('.')[0]}```",
            inline=False
        )
        
        # Current Station
        station_name = next((name for name, url in radio_stations.items() if url == current_stream_url), "Unknown Station")
        embed.add_field(
            name="📻 Current Station", 
            value=f"```\n{station_name}```",
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)
        embed.timestamp = datetime.now()
        
        await ctx.send(embed=embed)
        logger.info("Stats command executed successfully")
    except Exception as e:
        logger.error(f"Error in stats command: {e}")
        await ctx.send(f"Error getting statistics: {str(e)}")

@bot.command(name='about', help='Shows information about the bot')
async def about(ctx):
    logger.info(f"About command initiated by {ctx.author}")
    embed = discord.Embed(
        title="📻 Discord Radio Bot",
        description="A feature-rich Discord bot for streaming radio stations",
        color=discord.Color.blue()
    )
    embed.add_field(
        name="Features",
        value="• Multiple radio station support\n• Automatic stream recovery\n• Volume control\n• Station management\n• Status updates\n• Auto-fix system",
        inline=False
    )
    embed.add_field(
        name="Creator",
        value="Made with ❤️ by REVUNIX",
        inline=False
    )
    embed.set_footer(text="Use !help to see available commands")
    await ctx.send(embed=embed)

# Start the bot
if __name__ == "__main__":
    try:
        logger.info("Starting bot...")
        bot.run(token)
    except Exception as e:
        logger.critical(f"Failed to start bot: {e}")
