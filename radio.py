import discord
from discord.ext import commands, tasks
from discord.ui import Button, View
import asyncio, configparser, subprocess, re, os, sys, psutil, pkg_resources, platform, aiohttp, base64, json

# Load configuration file
config = configparser.ConfigParser()
config.read('config.ini')

# Set up bot intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.presences = True
bot = commands.Bot(command_prefix="!", intents=intents)

# FFmpeg options for audio streaming
ffmpeg_options = {'options': '-vn'}

# Function to load configuration settings
def load_config():
    global token, channel_id, default_voice_channel_id, default_stream_url, default_volume_percentage, allowed_role_ids, client_id, radio_stations
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

# Load configuration settings
load_config()

# Function to get the stream title using FFmpeg
async def get_stream_title(url):
    try:
        process = await asyncio.create_subprocess_exec('ffmpeg', '-i', url, '-f', 'ffmetadata', '-', stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, stderr = await process.communicate()
        match = re.search(r'Title\s*:\s*(.*)', stderr.decode())
        return match.group(1).strip() if match else 'Unknown Title'
    except Exception as e:
        print(f"Error fetching stream title: {e}")
        return 'Unknown Title'

# Function to change the bot's nickname in a guild
async def nickname_change(guild, station_name, bot_user):
    try:
        member = guild.get_member(bot_user.id)
        if member:
            current_nick = member.display_name
            if current_nick != f"# {station_name}":  # Check if the display_name is already correct
                await member.edit(nick=f"# {station_name}")
                print(f"Bot display name changed to 📻 {station_name} in guild {guild.name}")
            else:
                print(f"Bot display name is already set to 📻 {station_name} in guild {guild.name}")
        else:
            print(f"Bot user not found in guild {guild.name}")
    except discord.HTTPException as e:
        if e.code == 50035:
            print("You are changing your nickname too fast. Try again later.")
        elif e.code == 429:
            retry_after = e.retry_after
            print(f"Rate limit hit. Retrying after {retry_after} seconds.")
            await asyncio.sleep(retry_after)
            await nickname_change(guild, station_name, bot_user)
        else:
            print(f"Failed to change bot display name: {e}")

# Event handler for when the bot is ready
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')
    global current_stream_url  # Add this line
    current_stream_url = default_stream_url  # Add this line
    update_activity.start()
    station_name = next((name for name, url in radio_stations.items() if url == default_stream_url), "Unknown Station")
    for guild in bot.guilds:
        await nickname_change(guild, station_name, bot.user)
    default_channel = bot.get_channel(default_voice_channel_id)
    if default_channel:
        if not default_channel.guild.voice_client:
            await default_channel.connect()
        if bot.voice_clients[0]:
            title = await get_stream_title(default_stream_url)
            if title:
                player = discord.FFmpegPCMAudio(default_stream_url, **ffmpeg_options)
                bot.voice_clients[0].play(player, after=lambda e: print(f'Player error: {e}') if e else None)

# Store the current stream URL
current_stream_url = default_stream_url

# Task to update the bot's activity every 120 seconds
@tasks.loop(seconds=120)
async def update_activity():
    try:
        title = await get_stream_title(current_stream_url)  # Use current_stream_url instead of default_stream_url
        track_name = f"{title}"

        # Fetch cover image from Spotify
        cover_url = await fetch_cover_image_url(title)

        # Create rich presence without cover image
        activity = discord.Activity(
            type=discord.ActivityType.listening,
            name=track_name
        )

        # Check if the title has changed
        if bot.activity and bot.activity.name == track_name:
            print("The track is already set, skipping update.")
            return

        await bot.change_presence(activity=activity)

        try:
            # Load configuration
            config = configparser.ConfigParser()
            config.read('config.ini')
            channel_id = int(config['spotify']['update_channel_id'])
            channel = bot.get_channel(channel_id)

            # Check if the last message in the channel is the same as the current track
            last_message = None
            async for message in channel.history(limit=1):
                last_message = message
                break

            if last_message and last_message.embeds:
                last_embed = last_message.embeds[0]
                if last_embed.fields and last_embed.fields[0].value == track_name:
                    print("The track is already posted, skipping update.")
                    return

            # Create or update embed message
            embed = discord.Embed(color=0x1DB954)
            embed.set_thumbnail(url=cover_url)
            embed.add_field(name="Now Playing", value=track_name, inline=False)
            new_station_name = next((name for name, url in radio_stations.items() if url == current_stream_url), "Unknown Station")
            current_nickname = bot.user.display_name if bot.user else "Unknown"
            if current_nickname != new_station_name:
                await nickname_change(channel.guild, new_station_name, bot.user)
            embed.set_footer(text=f"{new_station_name}", icon_url="")

            # Post a new message every 30 seconds
            await channel.send(embed=embed)
        except Exception as e:
            print(f"Error updating activity: {e}")
    except Exception as e:
        print(f"Error in update_activity: {e}")

# Function to fetch cover image URL from Spotify
async def fetch_cover_image_url(title):
    try:
        # API call to fetch cover image URL from Spotify
        config = configparser.ConfigParser()
        config.read('config.ini')
        client_id = config.get('spotify', 'client_id')
        client_secret = config.get('spotify', 'client_secret')
        async with aiohttp.ClientSession() as session:
            auth_response = await session.post(
                'https://accounts.spotify.com/api/token',
                data={'grant_type': 'client_credentials'},
                headers={'Authorization': f'Basic {base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()}'}
            )
            auth_data = await auth_response.json()
            access_token = auth_data['access_token']

            async with session.get(
                f"https://api.spotify.com/v1/search?q={title}&type=track",
                headers={'Authorization': f'Bearer {access_token}'}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    if data['tracks']['items']:
                        track_info = data['tracks']['items'][0]
                        album_info = track_info['album']
                        return album_info['images'][0]['url']
                    else:
                        print(f"Track not found: {title}")
                        return 'default_cover_url'
                else:
                    print(f"Failed to fetch cover image, status code: {response.status}")
                    return 'default_cover_url'
    except Exception as e:
        print(f"Error fetching cover image: {e}")
        return 'default_cover_url'

# Command to add a new radio station to the configuration file
@bot.command(name='add', help='Adds a new radio station to the configuration file')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def addstation(ctx, name: str, url: str):
    index = len(radio_stations) + 1
    config.set('radio_stations', f'station{index}_name', name)
    config.set('radio_stations', f'station{index}_url', url)
    with open('config.ini', 'w') as configfile:
        config.write(configfile)
    load_config()
    await ctx.send(f"Added new station: {name}")

# Command to display a menu to remove a radio station
@bot.command(name='remove', help='Displays a menu to remove a radio station')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def remove_station(ctx):
    view = View()
    for index, station_name in enumerate(radio_stations.keys(), start=1):
        button = Button(label=station_name, style=discord.ButtonStyle.red, custom_id=f'remove_{index}')
        button.callback = lambda interaction, idx=index: remove_station_callback(interaction, idx)
        view.add_item(button)
    await ctx.send("Select a station to remove:", view=view)

# Callback function to handle station removal
async def remove_station_callback(interaction, index):
    try:
        station_names = list(radio_stations.keys())
        if 1 <= index <= len(station_names):
            station_name = station_names[index - 1]
            name_key, url_key = f'station{index}_name', f'station{index}_url'
            if config.has_section('radio_stations'):
                if config.has_option('radio_stations', name_key):
                    config.remove_option('radio_stations', name_key)
                if config.has_option('radio_stations', url_key):
                    config.remove_option('radio_stations', url_key)
            with open('config.ini', 'w') as configfile:
                config.write(configfile)
            load_config()
            await interaction.response.send_message(f"Removed station: {station_name}")
        else:
            await interaction.response.send_message("Invalid station number.")
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}")

# Command to display a list of available radio stations with a dropdown menu to play them
@bot.command(name='radio', help='Displays a list of available radio stations with a dropdown menu to play them')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def stations(ctx):
    if not radio_stations:
        await ctx.send("No radio stations available.")
        return

    options = [
        discord.SelectOption(label=station_name, value=str(index))
        for index, station_name in enumerate(radio_stations.keys(), start=1)
    ]

    select = discord.ui.Select(placeholder="Choose a radio station...", options=options)

    async def select_callback(interaction):
        index = int(select.values[0])
        await play_station_callback(interaction, index)

    select.callback = select_callback
    view = discord.ui.View()
    view.add_item(select)

    embed = discord.Embed(title="Available Radio Stations", description="Select a station from the dropdown menu", color=discord.Color.blue())
    await ctx.send(embed=embed, view=view)

# Callback function to handle station playback
async def play_station_callback(interaction, index):
    global current_stream_url  # Add this line to modify the global variable
    if interaction.user.guild.voice_client is None:
        if interaction.user.voice:
            await interaction.user.voice.channel.connect()
        else:
            await interaction.response.send_message("You are not connected to a voice channel.")
            return
    if interaction.guild.voice_client:
        if interaction.guild.voice_client.is_playing():
            interaction.guild.voice_client.stop()
        station_names = list(radio_stations.keys())
        if 1 <= index <= len(station_names):
            station_name = station_names[index - 1]
            url = radio_stations[station_name]
            if current_stream_url != url:  # Only change if the station has changed
                current_stream_url = url  # Update the current stream URL
                async with interaction.channel.typing():
                    title = await get_stream_title(url)
                    if title:
                        player = discord.FFmpegPCMAudio(url, **ffmpeg_options)
                        interaction.guild.voice_client.play(player, after=lambda e: asyncio.create_task(check_and_restart_stream(interaction.guild, url)))  # Create task for coroutine
                        await interaction.response.send_message(f"Now playing: {station_name}")
                        await nickname_change(interaction.guild, station_name, interaction.guild.me)  # Change bot name after switching station
                    else:
                        await interaction.response.send_message("Error fetching stream title.")
            else:
                await interaction.response.send_message(f"Already playing: {station_name}")
        else:
            await interaction.response.send_message("Invalid station number.")
    else:
        await interaction.response.send_message("Error connecting the voice client.")

# Function to check if the stream has stopped and restart it
async def check_and_restart_stream(guild, url):
    if not guild.voice_client.is_playing():
        print("Stream has stopped. Restarting...")
        player = discord.FFmpegPCMAudio(url, **ffmpeg_options)
        guild.voice_client.play(player, after=lambda e: asyncio.create_task(check_and_restart_stream(guild, url)))  # Create task for coroutine

# Command to play a selected radio station by index or a radio stream URL
@bot.command(name='play', help='Plays a selected radio station by index or a radio stream URL')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def play(ctx, arg):
    if ctx.voice_client is None:
        if ctx.message.author.voice:
            await ctx.message.author.voice.channel.connect()
        else:
            await ctx.send("The bot is not in a voice channel and you are not in one either.")
            return
    if ctx.voice_client:
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()
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
        async with ctx.typing():
            title = await get_stream_title(url)
            if title:
                player = discord.FFmpegPCMAudio(url, **ffmpeg_options)
                ctx.voice_client.play(player, after=lambda e: asyncio.create_task(check_and_restart_stream(ctx.guild, url)))  # Create task for coroutine
                await ctx.send(f"Now playing: {station_name if arg.isdigit() else title}")
            else:
                await ctx.send("Error fetching stream title.")
    else:
        await ctx.send("Error connecting the voice client.")

# Command to update the default stream URL in the configuration file
@bot.command(name='setdefault', help='Updates the default stream URL in the configuration file')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def setdefault(ctx, url: str):
    config.set('settings', 'default_stream_url', url)
    with open('config.ini', 'w') as configfile:
        config.write(configfile)
    load_config()
    await ctx.send(f"Default stream URL updated to: {url}")

# Command to restart the bot
@bot.command(name='restart', help='Restarts the bot')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def restart(ctx):
    await ctx.send("Restarting the bot...")
    await bot.close()
    os.execl(sys.executable, sys.executable, *sys.argv)

# Command to reload the configuration file
@bot.command(name='reload', help='Reloads the configuration file')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def reload(ctx):
    try:
        load_config()
        await ctx.send("Configuration reloaded successfully.")
    except Exception as e:
        await ctx.send(f"Error reloading configuration: {str(e)}")
        print(f"Error reloading configuration: {str(e)}")

# Command to show available commands
@bot.command(name='commands', help='Shows available commands')
async def commands_list(ctx):
    if ctx.channel.id != channel_id:
        await ctx.send("You can't use this command here. Please use the designated channel.")
        return
    embed = discord.Embed(title="Available Commands", description="Here are the available commands:", color=discord.Color.blue())
    commands_list = [
        {"name": "join", "description": "Joins a voice channel", "usage": ""},
        {"name": "leave", "description": "Leaves the voice channel", "usage": ""},
        {"name": "play", "description": "Plays a radio station by index", "usage": "<index>"},
        {"name": "stop", "description": "Stops the playback", "usage": ""},
        {"name": "vol", "description": "Adjusts the volume", "usage": "<volume (0-100)>"},
        {"name": "setdefault", "description": "Updates the default stream URL", "usage": "<url>"},
        {"name": "radio", "description": "Shows available radio stations", "usage": ""},
        {"name": "add", "description": "Adds a new radio station", "usage": "<name> <url>"},
        {"name": "remove", "description": "Removes a radio station", "usage": "<index>"},
        {"name": "restart", "description": "Restarts the bot", "usage": ""},
        {"name": "stats", "description": "Shows bot statistics", "usage": ""},
        {"name": "fix", "description": "Reloads the current station", "usage": ""}
    ]
    for cmd in commands_list:
        usage = f"Usage: `!{cmd['name']} {cmd['usage']}`" if cmd['usage'] else ""
        embed.add_field(name=f"!{cmd['name']}", value=f"{cmd['description']}\n{usage}", inline=False)
    await ctx.send(embed=embed)

# Variables to store the current station and title
current_station = "No station playing"
current_title = "No title available"

# Command to show the current station and the currently playing song
@bot.command(name='status', help='Shows the current station and the currently playing song')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def status(ctx):
    embed = discord.Embed(title="Current Status", color=discord.Color.blue())
    embed.add_field(name="Station", value=current_station, inline=False)
    embed.add_field(name="Title", value=current_title, inline=False)
    embed.set_footer(text="Use !help for more commands")
    await ctx.send(embed=embed)

# Callback function to handle station removal (duplicate function, should be removed)
async def remove_station_callback(interaction, index):
    try:
        station_names = list(radio_stations.keys())
        if 1 <= index <= len(station_names):
            station_name = station_names[index - 1]
            name_key, url_key = f'station{index}_name', f'station{index}_url'
            if config.has_section('radio_stations'):
                if config.has_option('radio_stations', name_key):
                    config.remove_option('radio_stations', name_key)
                if config.has_option('radio_stations', url_key):
                    config.remove_option('radio_stations', url_key)
            with open('config.ini', 'w') as configfile:
                config.write(configfile)
            load_config()
            await interaction.response.send_message(f"Removed station: {station_name}")
        else:
            await interaction.response.send_message("Invalid station number.")
    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}")

# Command to adjust the playback volume
@bot.command(name='vol', help='Adjusts the playback volume')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def vol(ctx, volume: int):
    if ctx.voice_client and ctx.voice_client.is_playing():
        if 0 <= volume <= 100:
            ctx.voice_client.source.volume = volume / 100.0
            await ctx.send(f"Volume set to {volume}%")
        else:
            await ctx.send("Volume must be between 0 and 100")
    else:
        await ctx.send("The bot is not playing anything or is not connected to a voice channel.")

# Command to join a voice channel
@bot.command(name='join', help='Joins a voice channel')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def join(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    if ctx.message.author.voice:
        await ctx.message.author.voice.channel.connect()
    else:
        default_channel = bot.get_channel(default_voice_channel_id)
        if default_channel:
            await default_channel.connect()
        else:
            await ctx.send("Default voice channel not found!")

# Command to leave the voice channel
@bot.command(name='leave', help='Leaves the voice channel')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    else:
        await ctx.send("I am not in a voice channel!")

# Command to stop the playback
@bot.command(name='stop', help='Stops the playback')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def stop(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
    else:
        await ctx.send("I am not playing anything!")

# Command to fix the FFmpeg stream
@bot.command(name='fix', help='Fixes the FFmpeg stream by restarting it with the current URL or starts default stream')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def fix_stream(ctx):
    global current_stream_url
    
    if not ctx.voice_client:
        # Connect to voice if not connected
        if ctx.author.voice:
            await ctx.author.voice.channel.connect()
        else:
            default_channel = bot.get_channel(default_voice_channel_id)
            if default_channel:
                await default_channel.connect()
            else:
                await ctx.send("Cannot connect to voice channel!")
                return

    # Stop current playback if any
    if ctx.voice_client.is_playing():
        ctx.voice_client.stop()
    
    await asyncio.sleep(1)  # Wait a moment before restarting
    
    # If no current stream is set, use default
    if not current_stream_url:
        current_stream_url = default_stream_url
        await ctx.send("No current stream found, starting default station.")
    
    # Start playback
    try:
        player = discord.FFmpegPCMAudio(current_stream_url, **ffmpeg_options)
        ctx.voice_client.play(player, after=lambda e: check_and_restart_stream(ctx.guild, current_stream_url))
        
        # Update station name
        station_name = next((name for name, url in radio_stations.items() if url == current_stream_url), "Unknown Station")
        await nickname_change(ctx.guild, station_name, ctx.guild.me)
        
        await ctx.send(f"Stream restarted: {station_name}")
    except Exception as e:
        await ctx.send(f"Error starting stream: {str(e)}")

# Command to show bot statistics
@bot.command(name='stats', help='Shows bot statistics')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def stats(ctx):
    embed = discord.Embed(color=0xFFFFFF)
    embed.add_field(name=":robot: Client", value="┕`🟢 Online!`", inline=True)
    embed.add_field(name="⌛ Ping", value=f"┕`{round(bot.latency * 1000)}ms`", inline=True)
    embed.add_field(name=":file_cabinet: Memory", value=f"┕`{round(psutil.Process().memory_info().rss / 1024 ** 2, 2)}mb`", inline=True)
    embed.add_field(name=":robot: Version", value=f"┕`v{pkg_resources.get_distribution('discord.py').version}`", inline=True)
    embed.add_field(name=":blue_book: Discord.py", value=f"┕`v{discord.__version__}`", inline=True)
    embed.add_field(name=":green_book: Python", value=f"┕`{platform.python_version()}`", inline=True)
    embed.set_footer(text=f"Requested By {ctx.author.name}", icon_url=ctx.author.avatar.url)
    embed.timestamp = ctx.message.created_at
    await ctx.send(embed=embed)

# Event handler for command errors
@bot.event
async def on_command_error(ctx, error):
    print(f"An error occurred: {str(error)}")

    if isinstance(error, commands.CheckFailure):
        # Handle CheckFailure separately to avoid duplicate messages
        await ctx.send("You cannot use this command in this channel or you don't have permission to use this command.")
    else:
        await ctx.send(f"An error occurred: {str(error)}")

# Event handler for bot disconnection
@bot.event
async def on_disconnect():
    print("Bot disconnected. Attempting to reconnect...")

# Event handler for bot reconnection
@bot.event
async def on_resumed():
    print("Bot reconnected successfully.")

@bot.event
async def on_voice_state_update(member, before, after):
    # Check if the bot was moved
    if member.id == bot.user.id:
        # If the bot was moved to a different channel (not disconnected)
        if before.channel is not None and after.channel is not None:
            if before.channel.id != after.channel.id:
                # Continue playing in the new channel
                if member.guild.voice_client and member.guild.voice_client.is_playing():
                    # Keep the current stream playing
                    return
                else:
                    # Restart the stream if it's not playing
                    player = discord.FFmpegPCMAudio(current_stream_url, **ffmpeg_options)
                    member.guild.voice_client.play(player, after=lambda e: asyncio.create_task(check_and_restart_stream(member.guild, current_stream_url)))
        # If the bot was disconnected (after.channel is None)
        elif after.channel is None:
            # Try to reconnect to the default channel
            try:
                default_channel = bot.get_channel(default_voice_channel_id)
                if default_channel:
                    await default_channel.connect()
                    if member.guild.voice_client:
                        player = discord.FFmpegPCMAudio(current_stream_url, **ffmpeg_options)
                        member.guild.voice_client.play(player, after=lambda e: asyncio.create_task(check_and_restart_stream(member.guild, current_stream_url)))
            except Exception as e:
                print(f"Error reconnecting to voice channel: {e}")


# Run the bot with the token
bot.run(token)
