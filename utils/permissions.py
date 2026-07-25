"""
Permission management utilities.
"""

import discord
from typing import List, Optional, Union
from database.manager import DatabaseManager


class PermissionManager:
    """Manages user permissions and role hierarchy."""
    
    @staticmethod
    async def get_permission_level(
        member: discord.Member,
        guild_settings: dict
    ) -> int:
        """Get the permission level of a member."""
        
        # Server owner has highest permissions
        if member.guild.owner_id == member.id:
            return 5
        
        # Check for owner IDs from config
        from config import Config
        if member.id in Config.OWNER_IDS:
            return 5
        
        # Check admin roles
        admin_role_ids = guild_settings.get('admin_role_ids', [])
        if any(role.id in admin_role_ids for role in member.roles):
            return 4
        
        # Check moderator roles
        mod_role_ids = guild_settings.get('mod_role_ids', [])
        if any(role.id in mod_role_ids for role in member.roles):
            return 3
        
        # Check helper roles
        helper_role_ids = guild_settings.get('helper_role_ids', [])
        if any(role.id in helper_role_ids for role in member.roles):
            return 2
        
        return 1
    
    @staticmethod
    def can_moderate(
        moderator: discord.Member,
        target: discord.Member
    ) -> bool:
        """Check if moderator can moderate the target."""
        # Server owner can moderate everyone
        if moderator.guild.owner_id == moderator.id:
            return True
        
        # Cannot moderate yourself
        if moderator.id == target.id:
            return False
        
        # Cannot moderate server owner
        if target.guild.owner_id == target.id:
            return False
        
        # Check role hierarchy
        return moderator.top_role > target.top_role
    
    @staticmethod
    def has_role_permissions(
        member: discord.Member,
        required_perms: List[str]
    ) -> bool:
        """Check if member has specific permissions."""
        if member.guild.owner_id == member.id:
            return True
        
        member_perms = member.guild_permissions
        
        for perm in required_perms:
            if not getattr(member_perms, perm, False):
                return False
        
        return True