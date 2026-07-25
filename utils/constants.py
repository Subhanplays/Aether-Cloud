"""
Constants and enumerations used throughout the bot.
"""

from enum import Enum
from typing import Dict, Any


class ModActionType(Enum):
    """Types of moderation actions."""
    WARN = "warn"
    MUTE = "mute"
    KICK = "kick"
    BAN = "ban"
    SOFTBAN = "softban"
    TIMEOUT = "timeout"
    UNMUTE = "unmute"
    UNBAN = "unban"
    CLEAR = "clear"


class LogType(Enum):
    """Types of logging events."""
    MESSAGE_DELETE = "message_delete"
    MESSAGE_EDIT = "message_edit"
    MEMBER_JOIN = "member_join"
    MEMBER_LEAVE = "member_leave"
    NICKNAME_CHANGE = "nickname_change"
    USERNAME_CHANGE = "username_change"
    ROLE_ADD = "role_add"
    ROLE_REMOVE = "role_remove"
    CHANNEL_CREATE = "channel_create"
    CHANNEL_DELETE = "channel_delete"
    CHANNEL_UPDATE = "channel_update"
    VOICE_JOIN = "voice_join"
    VOICE_LEAVE = "voice_leave"
    MOD_ACTION = "mod_action"
    SECURITY_ALERT = "security_alert"
    VERIFICATION = "verification"
    TICKET_CREATE = "ticket_create"
    TICKET_CLOSE = "ticket_close"


class PermissionLevel(Enum):
    """Permission levels for command access."""
    OWNER = 5
    ADMINISTRATOR = 4
    MODERATOR = 3
    HELPER = 2
    MEMBER = 1
    BLOCKED = 0


# Default guild settings
DEFAULT_GUILD_SETTINGS: Dict[str, Any] = {
    "prefix": "!",
    "mod_log_channel": None,
    "security_log_channel": None,
    "message_log_channel": None,
    "member_log_channel": None,
    "voice_log_channel": None,
    "ticket_log_channel": None,
    "verification_log_channel": None,
    "mod_role_ids": [],
    "admin_role_ids": [],
    "muted_role_id": None,
    "auto_mod_enabled": False,
    "spam_protection": False,
    "invite_blocking": False,
    "link_blocking": False,
    "bad_word_filter": False,
    "mention_spam_protection": False,
    "anti_raid_enabled": False,
    "anti_nuke_enabled": False,
    "verification_enabled": False,
    "verification_role_id": None,
    "welcome_enabled": False,
    "welcome_channel_id": None,
    "welcome_message": "Welcome {user} to {server}!",
    "goodbye_enabled": False,
    "goodbye_channel_id": None,
    "goodbye_message": "Goodbye {user}!",
    "auto_roles": [],
}