import os
import sys
import discord
from discord.ext import commands, tasks
import asyncio
import configparser
import subprocess
import re

# Read configuration file
config = configparser.ConfigParser()
config.read('config.ini')

# Load configuration values
token = config['settings']['token']
channel_id = int(config['settings']['channel_id'])
default_voice_channel_id = int(config['settings']['default_voice_channel_id'])
default_stream_url = config['settings']['default_stream_url']
default_volume_percentage = int(config['settings']['default_volume'])
allowed_role_ids = list(map(int, config['settings']['allowed_role_ids'].split(',')))
client_id = config['settings']['client_id']  # Discord application client ID

# Convert percentage to a decimal value for volume
default_volume = default_volume_percentage / 100.0

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.presences = True  # Ensure this is enabled
bot = commands.Bot(command_prefix="!", intents=intents)

ffmpeg_options = {
    'options': '-vn'
}

async def get_stream_title(url):
    try:
        process = await asyncio.create_subprocess_exec(
            'ffmpeg', '-i', url, '-f', 'ffmetadata', '-',
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        metadata = stderr.decode()

        match = re.search(r'Title\s*:\s*(.*)', metadata)
        if match:
            return match.group(1).strip()
        return 'Unknown Title'
    except Exception as e:
        print(f"Error fetching stream title: {e}")
        return 'Unknown Title'

async def update_discord_activity(title):
    activity = discord.Activity(name=f"{title}", type=discord.ActivityType.listening)
    await bot.change_presence(activity=activity)

@tasks.loop(minutes=2)
async def update_presence():
    if bot.voice_clients and bot.voice_clients[0].is_playing():
        title = await get_stream_title(default_stream_url)
        if title:
            await update_discord_activity(title)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    
    default_channel = bot.get_channel(default_voice_channel_id)
    if default_channel:
        if not default_channel.guild.voice_client:
            await default_channel.connect()
        
        if bot.voice_clients[0]:
            title = await get_stream_title(default_stream_url)
            if title:
                player = discord.FFmpegPCMAudio(default_stream_url, **ffmpeg_options)
                bot.voice_clients[0].play(player, after=lambda e: print(f'Player error: {e}') if e else None)
                await update_discord_activity(title)
                update_presence.start()  # Start the task to update presence every 2 minutes

@bot.command(name='join', help='Joins a voice channel')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def join(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    
    if ctx.message.author.voice:
        channel = ctx.message.author.voice.channel
        await channel.connect()
    else:
        default_channel = bot.get_channel(default_voice_channel_id)
        if default_channel:
            await default_channel.connect()
        else:
            await ctx.send("Default voice channel not found!")

@bot.command(name='leave', help='Leaves the voice channel')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
    else:
        await ctx.send("I am not in a voice channel!")

@bot.command(name='setdefault', help='Updates the default stream URL in the configuration file')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def setdefault(ctx, url: str):
    try:
        # Read the configuration file
        config.read('config.ini')

        # Update the default stream URL
        config.set('settings', 'default_stream_url', url)
        
        # Write the updated configuration to the file
        with open('config.ini', 'w') as configfile:
            config.write(configfile)

        # Update the default_stream_url variable
        global default_stream_url
        default_stream_url = url

        await ctx.send(f"Default stream URL updated to: {url}")

    except Exception as e:
        await ctx.send(f"Error updating the default stream URL: {e}")

@bot.command(name='restart', help='Restarts the bot')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def restart(ctx):
    try:
        await ctx.send("Restarting the bot...")
        
        # Stop all currently playing audio
        for vc in bot.voice_clients:
            if vc.is_playing():
                vc.stop()
            await vc.disconnect()
        
        # Wait a moment to ensure that everything has stopped and disconnected
        await asyncio.sleep(1)
        
        # Restart the bot
        os.execv(sys.executable, [sys.executable] + sys.argv)
        
    except Exception as e:
        await ctx.send(f"Error restarting the bot: {e}")

@bot.command(name='play', help='Plays a radio stream')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def play(ctx, url: str):
    if ctx.voice_client is None:
        if ctx.message.author.voice:
            channel = ctx.message.author.voice.channel
            await channel.connect()
        else:
            await ctx.send("The bot is not in a voice channel and you are not in one either.")
            return

    if ctx.voice_client:
        if ctx.voice_client.is_playing():
            ctx.voice_client.stop()  # Stop the currently playing audio
            await update_discord_activity('Stopped')
        
        async with ctx.typing():
            title = await get_stream_title(url)
            if title:
                player = discord.FFmpegPCMAudio(url, **ffmpeg_options)
                ctx.voice_client.play(player, after=lambda e: print(f'Player error: {e}') if e else None)
                await update_discord_activity(title)
                update_presence.start()  # Start the task to update presence every 2 minutes
    else:
        await ctx.send("Error connecting the voice client.")

@bot.command(name='stop', help='Stops the playback')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def stop(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()
        await update_discord_activity('Stopped')
    else:
        await ctx.send("I am not playing anything!")

@bot.command(name='vol', help='Adjusts the playback volume')
@commands.check(lambda ctx: ctx.channel.id == channel_id and any(role.id in allowed_role_ids for role in ctx.author.roles))
async def vol(ctx, volume: int):
    if ctx.voice_client and ctx.voice_client.is_playing():
        if 0 <= volume <= 100:
            ctx.voice_client.source.volume = volume / 100.0
            await ctx.send(f"Volume set to {volume}%")
            await update_discord_activity(ctx.voice_client.source.title)
        else:
            await ctx.send("Volume must be between 0 and 100")
    else:
        await ctx.send("The bot is not playing anything or is not connected to a voice channel.")

@bot.command(name='commands', help='Displays this help message')
async def commands_list(ctx):
    if ctx.channel.id != channel_id:
        await ctx.send("You cannot use this command in this channel. Please use the designated control channel.")
        return

    commands_list = [
        {
            "name": "join",
            "description": "Joins a voice channel"
        },
        {
            "name": "leave",
            "description": "Leaves the voice channel"
        },
        {
            "name": "play",
            "description": "Plays a radio stream",
            "usage": "<url>"
        },
        {
            "name": "stop",
            "description": "Stops the playback"
        },
        {
            "name": "vol",
            "description": "Adjusts the playback volume",
            "usage": "<volume (0-100)>"
        },
        {
            "name": "commands",
            "description": "Displays this help message"
        }
    ]
    
    help_message = "Here are the available commands:\n"
    for cmd in commands_list:
        help_message += f"**!{cmd['name']}**: {cmd['description']}"
        if 'usage' in cmd:
            help_message += f" (Usage: `!{cmd['name']} {cmd['usage']}`)"
        help_message += "\n"
    
    await ctx.send(help_message)

@bot.event
async def on_command_error(ctx, error):
    print(f"An error occurred: {str(error)}")
    
    if isinstance(error, commands.CheckFailure):
        # Handle CheckFailure separately to avoid duplicate messages
        await ctx.send("You cannot use this command in this channel or you don't have permission to use this command.")
    else:
        await ctx.send(f"An error occurred: {str(error)}")


bot.run(token)
