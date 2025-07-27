"""
Constants and configuration values for the YouTube Summary Bot.
"""

# API Configuration
DEFAULT_CHUNK_SIZE = 4000
DEFAULT_MAX_TOKENS = 1500
DEFAULT_TEMPERATURE = 0.3

# File Paths (Legacy - to be removed)
LEGACY_DATA_DIR = "data"
LEGACY_TRANSCRIPTS_DIR = f"{LEGACY_DATA_DIR}/transcripts"
LEGACY_SUMMARIES_DIR = f"{LEGACY_DATA_DIR}/summaries"
LEGACY_CONFIG_FILE = f"{LEGACY_DATA_DIR}/config.json"
LEGACY_SUMMARIES_FILE = f"{LEGACY_DATA_DIR}/summaries.json"
LEGACY_CHANNELS_FILE = f"{LEGACY_DATA_DIR}/tracked_channels.json"

# YouTube API Configuration
YOUTUBE_VIDEO_ID_LENGTH = 11
YOUTUBE_RSS_BASE_URL = "https://www.youtube.com/feeds/videos.xml"
YOUTUBE_OEMBED_URL = "https://www.youtube.com/oembed"

# Discord Configuration
DISCORD_EMBED_COLOR = 0x00ff00
DISCORD_MAX_MESSAGE_LENGTH = 2000

# OpenAI Configuration
OPENAI_MODEL = "gpt-3.5-turbo-0125"
OPENAI_MAX_RETRIES = 3
OPENAI_RETRY_DELAY = 1  # seconds

# Timezone Configuration
DEFAULT_TIMEZONE = "Europe/Amsterdam"  # CEST

# Scheduling Configuration
DAILY_REPORT_HOUR = 18  # 6 PM
DAILY_REPORT_MINUTE = 0

# HTTP Configuration
REQUEST_TIMEOUT = 30  # seconds
MAX_CONCURRENT_REQUESTS = 5

# Error Messages
ERROR_INVALID_YOUTUBE_URL = "Invalid YouTube URL"
ERROR_TRANSCRIPT_NOT_FOUND = "Transcript not available"
ERROR_OPENAI_API_ERROR = "OpenAI API error"
ERROR_DISCORD_WEBHOOK_ERROR = "Discord webhook error"
ERROR_CONFIG_NOT_FOUND = "Configuration not found"
ERROR_AUTHENTICATION_FAILED = "Authentication failed"

# Success Messages
SUCCESS_VIDEO_PROCESSED = "Video processed successfully"
SUCCESS_CONFIG_SAVED = "Configuration saved successfully"
SUCCESS_CHANNEL_ADDED = "Channel added successfully"
SUCCESS_CHANNEL_REMOVED = "Channel removed successfully"
