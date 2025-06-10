# revRadio - Discord Radio Bot 🎵

A feature-rich Discord bot for streaming radio stations with automatic recovery and management features.

## Features 🚀

- **Multiple Radio Station Support**: Manage and play multiple radio stations
- **Automatic Stream Recovery**: Auto-fixes stream issues every 6 hours
- **Real-time Status Updates**: Shows currently playing track with Spotify cover art
- **Voice Channel Management**: Automatically moves to default channel when alone
- **Station Management**: Easy to add, remove, and list radio stations
- **Volume Control**: Adjustable volume for each stream
- **Detailed Logging**: Comprehensive logging system for troubleshooting
- **Admin Controls**: Secure command access with role-based permissions

## Commands 📝

### Radio Controls
```
!radio    - Show available stations
!play #   - Play station by number
!play URL - Play custom stream URL
!stop     - Stop current playback
!vol 0-100- Adjust volume
!fix      - Fix stream issues
```

### Voice Channel Controls
```
!join     - Join your voice channel
!leave    - Leave voice channel
```

### Station Management
```
!add      - Add new radio station
!remove   - Remove a radio station
!listradio- List all radio stations
```

### System Commands
```
!stats    - Show bot statistics
!about    - Show bot information
!help     - Show command list
```

### Admin Commands
```
!setdefault - Set default stream URL
!restart    - Restart the bot
!reload     - Reload configuration
```

## Installation Options 🔧

### Using Docker (Recommended)

1. Pull the Docker image:
```bash
docker pull ghcr.io/revunix/revradio:latest
```

2. Create a config directory and config.ini:
```bash
mkdir -p /opt/revradio
cd /opt/revradio
nano config.ini
```

3. Run the container:
```bash
docker run -d \
  --name revradio \
  --restart unless-stopped \
  -v /opt/revradio/config.ini:/app/config.ini \
  ghcr.io/revunix/revradio:latest
```

### Manual Installation

1. Clone the repository:
```bash
git clone https://github.com/revunix/revRadio.git
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Install FFmpeg:
```bash
# Ubuntu/Debian
sudo apt-get install ffmpeg

# CentOS
sudo yum install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

## Configuration ⚙️

Create `config.ini` with the following structure:

```ini
[settings]
token = YOUR_DISCORD_BOT_TOKEN
channel_id = COMMAND_CHANNEL_ID
default_voice_channel_id = DEFAULT_VOICE_CHANNEL_ID
default_stream_url = DEFAULT_STREAM_URL
default_volume = 100
allowed_role_ids = ROLE_ID1,ROLE_ID2
client_id = YOUR_CLIENT_ID

[spotify]
client_id = YOUR_SPOTIFY_CLIENT_ID
client_secret = YOUR_SPOTIFY_CLIENT_SECRET
update_channel_id = STATUS_UPDATE_CHANNEL_ID

[radio_stations]
station1_name = Station Name
station1_url = Station URL
```

## Docker Compose Example

```yaml
version: '3.8'
services:
  revradio:
    image: ghcr.io/revunix/revradio:latest
    container_name: revradio
    restart: unless-stopped
    volumes:
      - /opt/revradio/config.ini:/app/config.ini
```

## Requirements 📋

### For Docker
- Docker Engine 20.10+
- Docker Compose (optional)

### For Manual Installation
- Python 3.8+
- FFmpeg
- Required Python packages:
  - discord.py
  - psutil
  - aiohttp
  - configparser

## New Features in Latest Update 🆕

- **Automatic Stream Recovery**: Bot now automatically runs !fix every 6 hours
- **Enhanced Logging System**: Detailed logging with timestamps
- **Improved Help Command**: Categorized help menu with detailed command information
- **Spotify Integration**: Shows album covers for currently playing tracks
- **Status Updates**: Real-time track information in designated channel

## Support & Troubleshooting 💬

### Docker Logs
```bash
docker logs revradio
```

### Container Management
```bash
# Stop the bot
docker stop revradio

# Start the bot
docker start revradio

# Restart the bot
docker restart revradio

# Remove the container
docker rm -f revradio
```

### Manual Logs
Check `discord_radio_bot.log` in the installation directory.

For support, feature requests, or bug reports, please open an issue on GitHub.

## License 📄

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Author ✨

Made with ❤️ by REVUNIX

---

Remember to star ⭐ the repository if you find it useful!
