"""
Command check decorators for permission validation.
"""

import discord
from discord.ext import commands
from typing import Optional
from config import Config
from database.manager import DatabaseManager


def is_owner():
    """Check if user is bot owner."""
    async def predicate(ctx: commands.Context) -> bool:
        return ctx.author.id in Config.OWNER_IDS
    return commands.check(predicate)


def has_permission_level(level: int):
    """Check if user has required permission level."""
    async def predicate(ctx: commands.Context) -> bool:
        db = DatabaseManager()
        guild_settings = await db.get_guild_settings(ctx.guild.id)
        
        from utils.permissions import PermissionManager
        user_level = await PermissionManager.get_permission_level(
            ctx.author, guild_settings
        )
        
        return user_level >= level
    
    return commands.check(predicate)


def is_moderator():
    """Check if user is moderator or higher."""
    return has_permission_level(3)


def is_admin():
    """Check if user is admin or higher."""
    return has_permission_level(4)


def has_moderation_perms():
    """Check if user has basic moderation permissions."""
    async def predicate(ctx: commands.Context) -> bool:
        perms = ctx.author.guild_permissions
        return any([
            perms.kick_members,
            perms.ban_members,
            perms.manage_messages,
            perms.moderate_members
        ])
    return commands.check(predicate)