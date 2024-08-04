# Discord Radio Bot

A simple Discord bot that streams radio stations in voice channels and updates its status with the current song title. This bot can join a voice channel, play a specified radio stream, adjust volume, and provide a custom help command for bot commands. It integrates with Discord Rich Presence to display the currently playing song.

## Features

- **Stream Radio**: Plays a specified radio stream in a voice channel.
- **Volume Control**: Adjusts playback volume with a simple command.
- **Custom Help Command**: Provides a list of available commands with a user-friendly interface.
- **Discord Rich Presence**: Displays the current song title in Discord Rich Presence.
- **Automatic Presence Update**: Updates Rich Presence every 2 minutes with the current song title.
- **Role-based Permissions**: Commands are restricted to users with specific roles.
- **Channel Restriction**: Commands can only be used in a designated control channel.
- **Join and Leave Voice Channels**: Commands to join or leave voice channels.
- **Play and Stop Radio Streams**: Commands to start or stop playback of radio streams.
- **Adjust Playback Volume**: Adjust the volume of the bot's audio playback.
- **Update Default Stream URL**: Change the default stream URL used by the bot.
- **Add and List Radio Stations**: Add new radio stations to the configuration and list available stations.

### Commands

- `!join`: Joins a voice channel.
- `!leave`: Leaves the voice channel.
- `!play <url|number>`: Plays a radio stream from a URL or by selecting a station from the list.
- `!stop`: Stops the playback.
- `!vol <volume>`: Adjusts the playback volume (0-100).
- `!setdefault <url>`: Updates the default stream URL in the configuration.
- `!stations`: Displays a list of available radio stations with indices.
- `!add <name> <url>`: Adds a new radio station to the configuration.
- `!remove <index>` Removes a radio station from the configuration file.
- `!restart`: Restarts the bot.
- `!commands`: Displays the list of available commands.

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

    [radio_stations]
    station1_name = Cool Radio
    station1_url = http://coolradio.example.com/stream
    station2_name = Jazz Station
    station2_url = http://jazzstation.example.com/stream
    ```

4. **Run the Bot**

    Start the bot with:

    ```bash
    python radio.py
    ```

## Rich Presence

The bot uses Discord Rich Presence to show the current song title. Ensure that the `client_id` in your `config.ini` is set correctly for Rich Presence to work.

## Troubleshooting

- **Bot not updating Rich Presence**: Ensure that Discord is running and that you have set the correct `client_id` in `config.ini`.
- **Bot not joining the voice channel**: Verify that the bot has the necessary permissions and that the `default_voice_channel_id` is correct.
- **Error installing dependencies**: Ensure you have Python 3.11 or later and that `ffmpeg` is properly installed.

## Contributing

Feel free to submit issues or pull requests if you have suggestions or improvements.
