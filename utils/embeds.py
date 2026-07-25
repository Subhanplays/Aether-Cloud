"""
Professional embed creation utilities.
"""

import discord
from typing import Optional, List, Union
from datetime import datetime
from config import Config


class EmbedBuilder:
    """Builder class for creating professional Discord embeds."""
    
    @staticmethod
    def create_embed(
        title: Optional[str] = None,
        description: Optional[str] = None,
        color: Optional[int] = None,
        timestamp: Optional[datetime] = None,
        fields: Optional[List[dict]] = None,
        author: Optional[discord.Member] = None,
        footer: Optional[str] = None,
        thumbnail: Optional[str] = None,
        image: Optional[str] = None,
        url: Optional[str] = None
    ) -> discord.Embed:
        """Create a professional embed with consistent styling."""
        
        embed = discord.Embed(
            title=title,
            description=description,
            color=color or Config.EMBED_COLORS['default'],
            timestamp=timestamp or datetime.utcnow(),
            url=url
        )
        
        if author:
            embed.set_author(
                name=author.display_name,
                icon_url=author.display_avatar.url
            )
        
        if footer:
            embed.set_footer(text=footer)
        
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        
        if image:
            embed.set_image(url=image)
        
        if fields:
            for field in fields:
                embed.add_field(
                    name=field.get('name', ''),
                    value=field.get('value', ''),
                    inline=field.get('inline', True)
                )
        
        return embed
    
    @staticmethod
    def success_embed(
        title: str = "Success",
        description: Optional[str] = None,
        **kwargs
    ) -> discord.Embed:
        """Create a success embed."""
        return EmbedBuilder.create_embed(
            title=f"✅ {title}",
            description=description,
            color=Config.EMBED_COLORS['success'],
            **kwargs
        )
    
    @staticmethod
    def error_embed(
        title: str = "Error",
        description: Optional[str] = None,
        **kwargs
    ) -> discord.Embed:
        """Create an error embed."""
        return EmbedBuilder.create_embed(
            title=f"❌ {title}",
            description=description,
            color=Config.EMBED_COLORS['error'],
            **kwargs
        )
    
    @staticmethod
    def warning_embed(
        title: str = "Warning",
        description: Optional[str] = None,
        **kwargs
    ) -> discord.Embed:
        """Create a warning embed."""
        return EmbedBuilder.create_embed(
            title=f"⚠️ {title}",
            description=description,
            color=Config.EMBED_COLORS['warning'],
            **kwargs
        )
    
    @staticmethod
    def moderation_embed(
        action: str,
        moderator: discord.Member,
        target: discord.Member,
        reason: Optional[str] = None,
        duration: Optional[str] = None,
        **kwargs
    ) -> discord.Embed:
        """Create a moderation action embed."""
        fields = [
            {"name": "Moderator", "value": moderator.mention, "inline": True},
            {"name": "Target", "value": target.mention, "inline": True},
        ]
        
        if reason:
            fields.append({"name": "Reason", "value": reason, "inline": False})
        
        if duration:
            fields.append({"name": "Duration", "value": duration, "inline": True})
        
        embed = EmbedBuilder.create_embed(
            title=f"🛡️ {action}",
            color=Config.EMBED_COLORS['moderation'],
            fields=fields,
            author=moderator,
            **kwargs
        )
        
        return embed
    
    @staticmethod
    def user_info_embed(member: discord.Member, **kwargs) -> discord.Embed:
        """Create a user info embed."""
        fields = [
            {"name": "Username", "value": str(member), "inline": True},
            {"name": "User ID", "value": member.id, "inline": True},
            {"name": "Nickname", "value": member.nick or "None", "inline": True},
            {
                "name": "Account Created",
                "value": discord.utils.format_dt(member.created_at, 'R'),
                "inline": True
            },
            {
                "name": "Joined Server",
                "value": discord.utils.format_dt(member.joined_at, 'R') if member.joined_at else "Unknown",
                "inline": True
            },
            {
                "name": "Roles",
                "value": ", ".join([r.mention for r in member.roles[1:]]) or "None",
                "inline": False
            },
        ]
        
        embed = EmbedBuilder.create_embed(
            title=f"👤 User Info - {member.display_name}",
            color=Config.EMBED_COLORS['info'],
            fields=fields,
            thumbnail=member.display_avatar.url,
            **kwargs
        )
        
        return embed