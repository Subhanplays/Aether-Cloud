"""
Utility helper functions.
"""

import discord
import re
from typing import Optional, Union, List
from datetime import datetime, timedelta
from config import Constants


def parse_duration(duration_str: str) -> Optional[int]:
    """Parse a duration string into seconds."""
    
    time_units = {
        's': 1,
        'm': 60,
        'h': 3600,
        'd': 86400,
        'w': 604800,
        'mo': 2592000,
        'y': 31536000
    }
    
    pattern = r'(\d+)\s*(s|m|h|d|w|mo|y)'
    matches = re.findall(pattern, duration_str.lower())
    
    if not matches:
        return None
    
    total_seconds = 0
    for value, unit in matches:
        total_seconds += int(value) * time_units.get(unit, 0)
    
    return total_seconds


def format_duration(seconds: int) -> str:
    """Format seconds into a readable duration string."""
    
    if seconds < 60:
        return f"{seconds}s"
    
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    
    hours = minutes // 60
    if hours < 24:
        return f"{hours}h"
    
    days = hours // 24
    if days < 7:
        return f"{days}d"
    
    weeks = days // 7
    return f"{weeks}w"


def clean_text(text: str) -> str:
    """Clean text from Discord mentions and markdown."""
    # Remove mentions
    text = re.sub(r'<@!?\d+>', '', text)
    text = re.sub(r'<#\d+>', '', text)
    text = re.sub(r'<@&\d+>', '', text)
    
    # Remove markdown
    text = text.replace('*', '').replace('_', '').replace('`', '')
    text = text.replace('~', '').replace('|', '')
    
    return text.strip()


def get_user_string(user: discord.User) -> str:
    """Get a standardized user string."""
    return f"{user} ({user.id})"


def chunk_list(lst: List, chunk_size: int) -> List[List]:
    """Split a list into chunks."""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def is_valid_invite(text: str) -> bool:
    """Check if text contains a Discord invite."""
    invite_patterns = Config.INVITE_PATTERNS if hasattr(Config, 'INVITE_PATTERNS') else [
        'discord.gg/',
        'discord.com/invite/',
        'discordapp.com/invite/'
    ]
    
    for pattern in invite_patterns:
        if pattern in text.lower():
            return True
    
    return False