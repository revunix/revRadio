# Discord Radio Bot

A simple Discord bot that streams radio stations in voice channels and updates its status with the current song title. This bot can join a voice channel, play a specified radio stream, adjust volume, and provide a custom help command for bot commands. It integrates with Discord Rich Presence to display the currently playing song and features automatic recovery from disconnections.

## Features

- **Stream Radio**: Plays a specified radio stream in a voice channel.
- **Volume Control**: Adjusts playback volume with a simple command.
- **Custom Help Command**: Provides a list of available commands with a user-friendly interface.
- **Discord Rich Presence**: Displays the current song title in Discord Rich Presence.
- **Automatic Presence Update**: Updates Rich Presence every 120 seconds with the current song title.
- **Role-based Permissions**: Commands are restricted to users with specific roles.
- **Channel Restriction**: Commands can only be used in a designated control channel.
- **Join and Leave Voice Channels**: Commands to join or leave voice channels.
- **Play and Stop Radio Streams**: Commands to start or stop playback of radio streams.
- **Adjust Playback Volume**: Adjust the volume of the bot's audio playback.
- **Update Default Stream URL**: Change the default stream URL used by the bot.
- **Add and List Radio Stations**: Add new radio stations to the configuration and list available stations.
- **Fetch Cover Image**: Fetches cover images from Spotify for the currently playing track.
- **Auto-Reconnect**: Automatically reconnects and resumes playback when disconnected.
- **Stream State Management**: Maintains stream state across channel moves and reconnections.
- **Enhanced Error Handling**: Better error feedback and recovery mechanisms.
- **Automatic Stream Recovery**: Recovers stream playback when moved between channels.
- **Dynamic Nickname Updates**: Updates bot nickname to reflect current station.

## Commands

- `!join`: Joins a voice channel.
- `!leave`: Leaves the voice channel.
- `!play <url|number>`: Plays a radio stream from a URL or by selecting a station from the list.
- `!stop`: Stops the playback.
- `!vol <volume>`: Adjusts the playback volume (0-100).
- `!setdefault <url>`: Updates the default stream URL in the configuration.
- `!radio`: Shows an interactive menu of available radio stations.
- `!add <name> <url>`: Adds a new radio station to the configuration.
- `!remove`: Shows an interactive menu to remove radio stations.
- `!restart`: Restarts the bot.
- `!reload`: Reloads the configuration file.
- `!commands`: Displays the list of available commands.
- `!status`: Shows the current station and playing title.
- `!stats`: Shows bot statistics.
- `!fix`: Fixes stream playback issues by restarting the current stream.

## Setup

1. **Clone the Repository**
    ```bash
    git clone https://github.com/revunix/discord-radio-bot.git
    cd discord-radio-bot
    ```

2. **Install Dependencies**
    Ensure you have Python 3.11 or later installed. Install the required Python packages:
    ```bash
    pip install -r requirements.txt
    ```
    **Note:** Ensure you have `ffmpeg` installed and accessible in your system's PATH. You can download it from [FFmpeg's official site](https://ffmpeg.org/download.html).

3. **Configure the Bot**
    Create a `config.ini` file in the root directory with the following structure:
    ```ini
    [settings]
    token = YOUR_BOT_TOKEN
    channel_id = YOUR_CONTROL_CHANNEL_ID
    default_voice_channel_id = YOUR_DEFAULT_VOICE_CHANNEL_ID
    default_stream_url = YOUR_DEFAULT_STREAM_URL
    default_volume = YOUR_DEFAULT_VOLUME (0-100)
    allowed_role_ids = ROLE_ID1,ROLE_ID2
    client_id = YOUR_DISCORD_APPLICATION_CLIENT_ID

    [spotify]
    client_id = YOUR_SPOTIFY_CLIENT_ID
    client_secret = YOUR_SPOTIFY_CLIENT_SECRET
    update_channel_id = YOUR_UPDATE_CHANNEL_ID

    [radio_stations]
    station1_name = Cool Radio
    station1_url = http://coolradio.example.com/stream
    station2_name = Jazz Station
    station2_url = http://jazzstation.example.com/stream
    ```

4. **Run the Bot**
    Start the bot with:
    ```bash
    python app.py
    ```

## Docker Setup

To run the bot using Docker, follow these steps:

1. **Build the Docker Image**
    In the root directory of your project, build the Docker image:
    ```bash
    docker build -t radiobot .
    ```

2. **Run the Docker Container**
    Start the container in detached mode:
    ```bash
    docker run -d --name radiobot radiobot:latest
    ```

This will create and run a Docker container with your bot, including FFmpeg for streaming.

## Rich Presence and Status Updates

The bot uses Discord Rich Presence to show the current song title and updates its status every 120 seconds. It also maintains a dedicated update channel where it posts currently playing tracks with cover art from Spotify.

## New Features in v1.1.1

- **Auto-Reconnect**: Bot now automatically reconnects when disconnected
- **Stream Recovery**: Maintains playback state when moved between channels
- **Enhanced Stability**: Better error handling and recovery mechanisms
- **Interactive Menus**: New dropdown and button interfaces for station selection
- **Improved Status Updates**: More reliable song title and cover art updates

## Troubleshooting

- **Bot not updating Rich Presence**: Ensure that Discord is running and that you have set the correct `client_id` in `config.ini`.
- **Bot not joining the voice channel**: Verify that the bot has the necessary permissions and that the `default_voice_channel_id` is correct.
- **Stream interruptions**: Use the `!fix` command to restart the current stream if you experience playback issues.
- **Error installing dependencies**: Ensure you have Python 3.11 or later and that `ffmpeg` is properly installed.
- **Bot disconnecting**: The bot will now automatically attempt to reconnect and resume playback.

## Contributing

Feel free to submit issues or pull requests if you have suggestions or improvements.
