"""
Configuration management for the Discord Moderation Bot.
Handles all environment variables and global settings.
"""

import os
from typing import List, Optional
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()


class Config:
    """Main configuration class for the bot."""
    
    # Bot Configuration
    DISCORD_TOKEN: str = os.getenv('DISCORD_TOKEN', '')
    MONGODB_URI: str = os.getenv('MONGODB_URI', 'mongodb://localhost:27017')
    DATABASE_NAME: str = os.getenv('DATABASE_NAME', 'discord_moderation_bot')
    
    # Owner Configuration
    OWNER_IDS: List[int] = [
        int(id_) for id_ in os.getenv('OWNER_IDS', '').split(',') if id_
    ]
    
    # Bot Settings
    PREFIX: str = os.getenv('PREFIX', '!')
    LOG_LEVEL: str = os.getenv('LOG_LEVEL', 'INFO')
    
    # Color Scheme
    EMBED_COLORS = {
        'default': 0x5865F2,      # Discord Blurple
        'success': 0x57F287,      # Green
        'error': 0xED4245,        # Red
        'warning': 0xFEE75C,      # Yellow
        'info': 0x5865F2,         # Blurple
        'moderation': 0xFEE75C,   # Yellow
        'security': 0xED4245,     # Red
        'logging': 0xEB459E,      # Pink
        'ticket': 0x5865F2,       # Blurple
        'automation': 0x57F287,   # Green
    }
    
    # Moderation Settings
    DEFAULT_WARN_THRESHOLDS = {
        3: 'mute',
        5: 'kick',
        7: 'ban'
    }
    
    # Anti-Spam Settings
    SPAM_THRESHOLD = 5
    SPAM_INTERVAL = 5  # seconds
    DUPLICATE_MESSAGE_THRESHOLD = 3
    MENTION_SPAM_THRESHOLD = 10
    
    # Verification Settings
    MIN_ACCOUNT_AGE = 7 * 24 * 60 * 60  # 7 days in seconds
    VERIFICATION_TIMEOUT = 300  # 5 minutes
    
    # Ticket Settings
    TICKET_CATEGORIES = [
        'Support',
        'Report',
        'Appeal',
        'Partnership'
    ]
    
    # Anti-Raid Settings
    RAID_JOIN_THRESHOLD = 10  # joins per minute
    RAID_ACCOUNT_AGE = 7 * 24 * 60 * 60  # 7 days
    
    # Auto-Moderation Settings
    MAX_MENTIONS = 5
    MAX_EMOJIS = 10
    MAX_ATTACHMENTS = 5
    INVITE_PATTERNS = [
        'discord.gg/',
        'discord.com/invite/',
        'discordapp.com/invite/'
    ]
    
    # Database Collections
    COLLECTIONS = {
        'guilds': 'guild_settings',
        'warnings': 'warnings',
        'tickets': 'tickets',
        'verification': 'verification',
        'moderation_logs': 'moderation_logs',
        'security_logs': 'security_logs',
        'automation': 'automation',
        'custom_commands': 'custom_commands',
        'role_configs': 'role_configs',
        'backups': 'backups'
    }
    
    @classmethod
    def validate(cls) -> bool:
        """Validate required configuration."""
        if not cls.DISCORD_TOKEN:
            raise ValueError("DISCORD_TOKEN is required in .env file")
        if not cls.MONGODB_URI:
            raise ValueError("MONGODB_URI is required in .env file")
        return True


# Constants
class Constants:
    """Bot-wide constants."""
    
    # Discord Limits
    MAX_EMBED_DESCRIPTION = 4096
    MAX_EMBED_FIELDS = 25
    MAX_MESSAGE_LENGTH = 2000
    
    # Time Constants
    SECOND = 1
    MINUTE = 60
    HOUR = 3600
    DAY = 86400
    WEEK = 604800
    MONTH = 2592000
    
    # Permission Levels
    PERMISSION_OWNER = 5
    PERMISSION_ADMIN = 4
    PERMISSION_MODERATOR = 3
    PERMISSION_HELPER = 2
    PERMISSION_MEMBER = 1
    PERMISSION_BLOCKED = 0
    
    # Emoji Constants
    EMOJI = {
        'success': '✅',
        'error': '❌',
        'warning': '⚠️',
        'info': 'ℹ️',
        'loading': '🔄',
        'lock': '🔒',
        'unlock': '🔓',
        'shield': '🛡️',
        'ban': '🔨',
        'kick': '👢',
        'mute': '🔇',
        'warn': '⚠️',
        'ticket': '🎫',
        'settings': '⚙️',
        'user': '👤',
        'server': '🖥️',
        'role': '👑',
        'channel': '💬',
        'time': '⏰',
        'search': '🔍',
        'trash': '🗑️',
        'edit': '✏️',
        'check': '☑️',
        'cross': '✖️',
        'plus': '➕',
        'minus': '➖',
    }