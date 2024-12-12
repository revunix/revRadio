# revRadio Music Bot

A versatile Discord bot for streaming radio stations with advanced stream management, error handling, and user experience features. This bot provides robust radio streaming capabilities with automatic recovery, dynamic station management, and comprehensive command interfaces.

## Features

- **Advanced Stream Management**
  * Resilient stream handling with automatic recovery
  * Improved error detection and restart mechanisms
  * Dynamic stream state tracking

- **Radio Station Management**
  * Play radio streams from URLs or predefined stations
  * Add, remove, and list radio stations dynamically
  * New `!listradio` command to display all configured stations

- **Enhanced User Experience**
  * Informative embed messages for commands
  * Detailed error feedback
  * Interactive station selection
  * Role-based command permissions

- **Technical Capabilities**
  * Discord Rich Presence integration
  * Automatic song title and cover art updates
  * Volume control
  * Stream state preservation across channel moves
  * Spotify cover image integration

## Commands

- `!join`: Joins a voice channel
- `!leave`: Leaves the voice channel
- `!play <url|number>`: Plays a radio stream
- `!stop`: Stops playback
- `!vol <volume>`: Adjusts volume (0-100)
- `!setdefault <url>`: Updates default stream URL
- `!radio`: Interactive station selection menu
- `!listradio`: Lists all configured radio stations
- `!add <name> <url>`: Adds a new radio station
- `!remove`: Removes a radio station
- `!restart`: Restarts the bot
- `!reload`: Reloads configuration
- `!commands`: Displays available commands
- `!status`: Shows current station and title
- `!stats`: Shows bot statistics
- `!fix`: Resolves stream playback issues

## New in v1.2.0 - Stream Resilience and Management Update

- **Improved Stream Handling**
  * More robust async event loop management
  * Enhanced error recovery mechanisms
  * Thread-safe coroutine execution

- **New Features**
  * `!listradio` command to display all stations
  * Comprehensive error logging
  * Informative embed messages
  * Improved configuration management

- **Technical Enhancements**
  * Better async task management
  * More consistent error handling
  * Enhanced voice client state management

## Setup and Installation

(Rest of the setup instructions remain the same as in the previous README)

## Troubleshooting

- Ensure Python 3.8+ and discord.py v2.0+
- Verify FFmpeg installation
- Check bot permissions in Discord
- Use `!fix` for stream interruptions
- Consult error messages in embeds

## Contributing

Contributions welcome! Please submit issues or pull requests on our GitHub repository.
