"""
Comprehensive logging system for all server events.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from datetime import datetime

from utils.embeds import EmbedBuilder
from utils.checks import is_admin
from database.manager import DatabaseManager
from config import Config
from utils.logger import logger


class Logging(commands.Cog):
    """Comprehensive logging system."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseManager()
    
    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Log deleted messages."""
        
        if message.author.bot:
            return
        
        settings = await self.db.get_guild_settings(message.guild.id)
        log_channel_id = settings.get('message_log_channel')
        
        if not log_channel_id:
            return
        
        log_channel = message.guild.get_channel(log_channel_id)
        if not log_channel:
            return
        
        embed = EmbedBuilder.create_embed(
            title="🗑️ Message Deleted",
            color=Config.EMBED_COLORS['logging'],
            fields=[
                {"name": "Author", "value": message.author.mention, "inline": True},
                {"name": "Channel", "value": message.channel.mention, "inline": True},
                {"name": "Author ID", "value": message.author.id, "inline": True},
            ],
            footer=f"Message ID: {message.id}"
        )
        
        if message.content:
            embed.add_field(
                name="Content",
                value=message.content[:1024] or "*No content*",
                inline=False
            )
        
        if message.attachments:
            embed.add_field(
                name="Attachments",
                value="\n".join([a.url for a in message.attachments[:3]]),
                inline=False
            )
            if message.attachments:
                embed.set_image(url=message.attachments[0].url)
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass
    
    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Log edited messages."""
        
        if before.author.bot or before.content == after.content:
            return
        
        settings = await self.db.get_guild_settings(before.guild.id)
        log_channel_id = settings.get('message_log_channel')
        
        if not log_channel_id:
            return
        
        log_channel = before.guild.get_channel(log_channel_id)
        if not log_channel:
            return
        
        embed = EmbedBuilder.create_embed(
            title="✏️ Message Edited",
            color=Config.EMBED_COLORS['logging'],
            fields=[
                {"name": "Author", "value": before.author.mention, "inline": True},
                {"name": "Channel", "value": before.channel.mention, "inline": True},
                {
                    "name": "Jump to Message",
                    "value": f"[Click Here]({after.jump_url})",
                    "inline": True
                },
                {"name": "Before", "value": before.content[:1024] or "*No content*", "inline": False},
                {"name": "After", "value": after.content[:1024] or "*No content*", "inline": False},
            ],
            footer=f"Message ID: {after.id}"
        )
        
        try:
            await log_channel.send(embed=embed)
        except discord.Forbidden:
            pass
    
    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Log member changes."""
        
        settings = await self.db.get_guild_settings(before.guild.id)
        log_channel_id = settings.get('member_log_channel')
        
        if not log_channel_id:
            return
        
        log_channel = before.guild.get_channel(log_channel_id)
        if not log_channel:
            return
        
        # Nickname change
        if before.nick != after.nick:
            embed = EmbedBuilder.create_embed(
                title="📝 Nickname Changed",
                color=Config.EMBED_COLORS['logging'],
                fields=[
                    {"name": "User", "value": after.mention, "inline": True},
                    {"name": "Before", "value": before.nick or "*None*", "inline": True},
                    {"name": "After", "value": after.nick or "*None*", "inline": True},
                ],
                thumbnail=after.display_avatar.url
            )
            await log_channel.send(embed=embed)
        
        # Role changes
        if before.roles != after.roles:
            added_roles = set(after.roles) - set(before.roles)
            removed_roles = set(before.roles) - set(after.roles)
            
            if added_roles:
                embed = EmbedBuilder.create_embed(
                    title="✅ Roles Added",
                    color=Config.EMBED_COLORS['success'],
                    fields=[
                        {"name": "User", "value": after.mention, "inline": True},
                        {"name": "Roles", "value": ", ".join([r.mention for r in added_roles]), "inline": False},
                    ],
                    thumbnail=after.display_avatar.url
                )
                await log_channel.send(embed=embed)
            
            if removed_roles:
                embed = EmbedBuilder.create_embed(
                    title="❌ Roles Removed",
                    color=Config.EMBED_COLORS['error'],
                    fields=[
                        {"name": "User", "value": after.mention, "inline": True},
                        {"name": "Roles", "value": ", ".join([r.mention for r in removed_roles]), "inline": False},
                    ],
                    thumbnail=after.display_avatar.url
                )
                await log_channel.send(embed=embed)
    
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState
    ):
        """Log voice channel activity."""
        
        settings = await self.db.get_guild_settings(member.guild.id)
        log_channel_id = settings.get('voice_log_channel')
        
        if not log_channel_id:
            return
        
        log_channel = member.guild.get_channel(log_channel_id)
        if not log_channel:
            return
        
        # Joined voice channel
        if before.channel is None and after.channel is not None:
            embed = EmbedBuilder.create_embed(
                title="🎤 Joined Voice Channel",
                color=Config.EMBED_COLORS['success'],
                fields=[
                    {"name": "User", "value": member.mention, "inline": True},
                    {"name": "Channel", "value": after.channel.mention, "inline": True},
                ]
            )
            await log_channel.send(embed=embed)
        
        # Left voice channel
        elif before.channel is not None and after.channel is None:
            embed = EmbedBuilder.create_embed(
                title="🔇 Left Voice Channel",
                color=Config.EMBED_COLORS['error'],
                fields=[
                    {"name": "User", "value": member.mention, "inline": True},
                    {"name": "Channel", "value": before.channel.mention, "inline": True},
                ]
            )
            await log_channel.send(embed=embed)
        
        # Moved voice channels
        elif before.channel != after.channel:
            embed = EmbedBuilder.create_embed(
                title="🔀 Moved Voice Channel",
                color=Config.EMBED_COLORS['info'],
                fields=[
                    {"name": "User", "value": member.mention, "inline": True},
                    {"name": "From", "value": before.channel.mention, "inline": True},
                    {"name": "To", "value": after.channel.mention, "inline": True},
                ]
            )
            await log_channel.send(embed=embed)
    
    @app_commands.command(name="setlog", description="Set a logging channel")
    @app_commands.describe(
        log_type="Type of logs to set channel for",
        channel="Channel to send logs to"
    )
    @is_admin()
    async def set_log(
        self,
        interaction: discord.Interaction,
        log_type: str,
        channel: discord.TextChannel
    ):
        """Configure logging channels."""
        
        log_types = {
            'mod': 'mod_log_channel',
            'security': 'security_log_channel',
            'message': 'message_log_channel',
            'member': 'member_log_channel',
            'voice': 'voice_log_channel',
            'ticket': 'ticket_log_channel',
            'verification': 'verification_log_channel'
        }
        
        if log_type.lower() not in log_types:
            embed = EmbedBuilder.error_embed(
                "Invalid Log Type",
                f"Valid types: {', '.join(log_types.keys())}"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        setting_key = log_types[log_type.lower()]
        await self.db.update_guild_setting(
            interaction.guild_id,
            setting_key,
            channel.id
        )
        
        embed = EmbedBuilder.success_embed(
            "Log Channel Set",
            f"{log_type.title()} logs will be sent to {channel.mention}."
        )
        
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Logging(bot))