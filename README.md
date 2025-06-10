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

## 📢 Update Highlights – June 2025

### 🎵 Now Playing Push Improvements
- **Banlist for Push Messages:**  
  You can now define forbidden titles in your `config.ini` under `[push]` with the `banned_titles` key.  
  Any track title containing one of these (case-insensitive, supports substrings/wildcards) will not be pushed as "Now Playing".
- **Example in `config.ini`:**
  ```ini
  [push]
  banned_titles = ANTENNE NRW,Radio XY,Werbung,Unknown,Live-Stream
  ```
- The bot checks for these substrings before posting any now playing notification.

### 🛠️ Refined Configuration Loading
- The banlist is automatically loaded with all other config options on startup.
- No need for manual reloading or code changes when updating the banlist; just edit your `config.ini` and restart the bot.

### 🖼️ Improved !play Command
- The `!play` command now provides a rich embed:
  - Shows the current track title and station in a visually appealing card.
  - Displays a cover image if available.
  - Shows who requested the track.
  - Error and info messages are now sent as colored embeds for clarity.

### 🧹 Code Cleanup
- Removed outdated tasks and legacy update logic.
- The new `monitor_track` task handles push updates, using the banlist and providing improved error handling and logging.

---

## ✨ New Features & Enhancements

- **Automatic Stream Recovery:**  
  The bot now automatically triggers `!fix` every 6 hours to recover from possible stream issues.

- **Enhanced Logging System:**  
  Detailed logging with timestamps for easier debugging and monitoring.

- **Improved Help Command:**  
  The `!help` command now displays a categorized help menu with detailed descriptions for each command.

- **Spotify Integration:**  
  Album covers for currently playing tracks are displayed (when available), enriching the listening experience.

- **Status Updates:**  
  Real-time track information is shown in the designated update channel for maximum transparency.

---

**Upgrade Steps:**
1. Add or update your `[push]` section in `config.ini` with the `banned_titles` line.
2. Restart your bot after editing `config.ini` for changes to take effect.
3. Enjoy cleaner, more relevant now playing notifications and a more beautiful `!play` experience!

---

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
channel_id = 123456789012345678
default_voice_channel_id = 223344556677889900
default_stream_url = https://stream.example.com/stream
default_volume = 50
allowed_role_ids = 1000001,1000002
client_id = YOUR_CLIENT_ID

[push]
banned_titles = ANTENNE NRW,Radio XY,Werbung,Unknown,Live-Stream,Test-Stream

[spotify]
client_id = YOUR_SPOTIFY_CLIENT_ID
client_secret = YOUR_SPOTIFY_CLIENT_SECRET
update_channel_id = 112233445566778899

[radio_stations]
station1_name = Antenne.NRW
station1_url = https://stream.antenne.nrw/antenne-nrw/stream/mp3
station2_name = Antenne 80s Hits
station2_url = https://stream.antenne.nrw/antenne-nrw-80er-hits/stream/mp3
station3_name = Antenne 80s ROCK
station3_url = https://stream.antenne.nrw/antenne-nrw-80er-rock/stream/mp3
station4_name = Antenne 80s Disco Hits
station4_url = https://stream.antenne.nrw/antenne-nrw-80er-disco-hits/stream/mp3
station5_name = Antenne 80s New Wave
station5_url = https://stream.antenne.nrw/antenne-nrw-80er-new-wave/stream/mp3
station6_name = Antenne 90s Eurodance
station6_url = https://stream.antenne.nrw/antenne-nrw-90er-eurodance/stream/mp3
station7_name = Antenne 90s Hits
station7_url = https://stream.antenne.nrw/antenne-nrw-90er-hits/stream/mp3
station8_name = Antenne 90s ROCK
station8_url = https://stream.antenne.nrw/antenne-nrw-90er-rock/stream/mp3
station9_name = Antenne 2000er Hits
station9_url = https://stream.antenne.nrw/antenne-nrw-2000er-hits/stream/mp3
station10_name = Q-DANCE
station10_url = https://22323.live.streamtheworld.com/Q_DANCE.mp3
station11_name = Chillout Lounge
station11_url = https://streams.ilovemusic.de/iloveradio24.mp3
station12_name = Rock Antenne
station12_url = https://stream.rockantenne.de/rockantenne/stream/mp3
station13_name = Jazz FM
station13_url = https://jazzfm.ice.infomaniak.ch/jazzfm-high.mp3
station14_name = 80s80s Radio
station14_url = https://streams.80s80s.de/80s80s/mp3-192/streams.80s80s.de/
station15_name = Energy Hamburg
station15_url = https://cdn.nrjaudio.fm/adwz1/de/33046/mp3_128.mp3?origine=web
station16_name = Hit Radio FFH
station16_url = https://streams.ffh.de/radioffh/mp3/hq
station17_name = BBC Radio 1
station17_url = http://bbcmedia.ic.llnwd.net/stream/bbcmedia_radio1_mf_q
station18_name = NDR 2
station18_url = http://ndr-ndr2-niedersachsen.cast.addradio.de/ndr/ndr2/niedersachsen/mp3/128/stream.mp3
station19_name = Radio Paradise
station19_url = http://stream.radioparadise.com/mp3-192
station20_name = Sunshine Live
station20_url = https://stream.sunshine-live.de/live/mp3-192/stream.sunshine-live.de/
station21_name = Klassik Radio
station21_url = http://klassikr.streamabc.net/klr-mp3-128/klr/klr-mp3-128/klr.mp3
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
