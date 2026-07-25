"""
Security system including anti-raid, anti-nuke, and auto-moderation.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Dict, List
from collections import defaultdict
import asyncio
from datetime import datetime, timedelta

from utils.embeds import EmbedBuilder
from utils.checks import is_admin
from database.manager import DatabaseManager
from config import Config
from utils.logger import logger


class Security(commands.Cog):
    """Security and protection systems."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseManager()
        
        # Rate limiting caches
        self.join_cache: Dict[int, List[datetime]] = defaultdict(list)
        self.message_cache: Dict[int, List[datetime]] = defaultdict(list)
        self.mention_cache: Dict[int, List[datetime]] = defaultdict(list)
        
        # Cooldown tracking
        self.raid_lock: Dict[int, bool] = {}
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Monitor member joins for potential raids."""
        
        if not member.guild:
            return
        
        guild_settings = await self.db.get_guild_settings(member.guild.id)
        
        if not guild_settings.get('anti_raid_enabled', False):
            return
        
        guild_id = member.guild.id
        now = datetime.utcnow()
        
        # Clean old entries
        self.join_cache[guild_id] = [
            t for t in self.join_cache[guild_id]
            if now - t < timedelta(minutes=1)
        ]
        
        # Add new join
        self.join_cache[guild_id].append(now)
        
        # Check for raid
        join_count = len(self.join_cache[guild_id])
        
        if join_count >= Config.RAID_JOIN_THRESHOLD:
            await self._handle_raid(member.guild)
        
        # Check for new account
        account_age = (now - member.created_at).total_seconds()
        if account_age < Config.RAID_ACCOUNT_AGE:
            await self._handle_suspicious_account(member)
    
    async def _handle_raid(self, guild: discord.Guild):
        """Handle detected raid."""
        
        if self.raid_lock.get(guild.id, False):
            return
        
        self.raid_lock[guild.id] = True
        
        logger.warning(f"Raid detected in {guild.name} (ID: {guild.id})")
        
        try:
            # Lock all text channels
            for channel in guild.text_channels:
                try:
                    overwrite = channel.overwrites_for(guild.default_role)
                    overwrite.send_messages = False
                    await channel.set_permissions(
                        guild.default_role,
                        overwrite=overwrite,
                        reason="Anti-raid: Channel locked"
                    )
                except:
                    pass
            
            # Enable slowmode on all channels
            for channel in guild.text_channels:
                try:
                    await channel.edit(
                        slowmode_delay=30,
                        reason="Anti-raid: Slowmode enabled"
                    )
                except:
                    pass
            
            # Log security event
            await self.db.log_security_event(
                guild.id,
                "raid_detected",
                {
                    "action": "channels_locked",
                    "join_count": len(self.join_cache[guild.id])
                }
            )
            
            # Notify staff
            guild_settings = await self.db.get_guild_settings(guild.id)
            log_channel_id = guild_settings.get('security_log_channel')
            
            if log_channel_id:
                log_channel = guild.get_channel(log_channel_id)
                if log_channel:
                    embed = EmbedBuilder.create_embed(
                        title="🚨 RAID DETECTED",
                        description="Emergency security measures activated!",
                        color=Config.EMBED_COLORS['security'],
                        fields=[
                            {"name": "Action", "value": "All channels locked", "inline": True},
                            {"name": "Slowmode", "value": "30 seconds", "inline": True},
                            {"name": "Join Rate", "value": f"{len(self.join_cache[guild.id])} per minute", "inline": True},
                        ]
                    )
                    await log_channel.send(embed=embed)
            
            # Unlock after 5 minutes
            await asyncio.sleep(300)
            self.raid_lock[guild.id] = False
            
        except Exception as e:
            logger.error(f"Error handling raid: {e}")
            self.raid_lock[guild.id] = False
    
    async def _handle_suspicious_account(self, member: discord.Member):
        """Handle newly created accounts."""
        
        try:
            await member.timeout(
                timedelta(minutes=30),
                reason="Anti-raid: New account detected"
            )
            
            logger.info(f"Suspicious account detected: {member} ({member.id})")
            
        except discord.Forbidden:
            pass
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Monitor messages for spam and auto-moderation."""
        
        if not message.guild or message.author.bot:
            return
        
        guild_settings = await self.db.get_guild_settings(message.guild.id)
        
        if not guild_settings.get('auto_mod_enabled', False):
            return
        
        # Check for spam
        if guild_settings.get('spam_protection', False):
            await self._check_spam(message)
        
        # Check for invite links
        if guild_settings.get('invite_blocking', False):
            await self._check_invites(message)
        
        # Check for mention spam
        if guild_settings.get('mention_spam_protection', False):
            await self._check_mention_spam(message)
    
    async def _check_spam(self, message: discord.Message):
        """Check for spam messages."""
        
        guild_id = message.guild.id
        author_id = message.author.id
        now = datetime.utcnow()
        
        key = f"{guild_id}:{author_id}"
        
        # Clean old entries
        self.message_cache[key] = [
            t for t in self.message_cache[key]
            if now - t < timedelta(seconds=Config.SPAM_INTERVAL)
        ]
        
        # Add new message
        self.message_cache[key].append(now)
        
        # Check threshold
        if len(self.message_cache[key]) >= Config.SPAM_THRESHOLD:
            await self._handle_spam(message.author, message.channel)
    
    async def _handle_spam(self, member: discord.Member, channel: discord.TextChannel):
        """Handle spam detection."""
        
        try:
            # Timeout the member
            await member.timeout(
                timedelta(minutes=10),
                reason="Auto-mod: Spam detected"
            )
            
            # Delete spam messages
            async for msg in channel.history(limit=20):
                if msg.author.id == member.id:
                    await msg.delete()
            
            # Log the action
            await self.db.log_security_event(
                member.guild.id,
                "spam_detected",
                {
                    "user_id": member.id,
                    "channel_id": channel.id,
                    "action": "timeout"
                }
            )
            
            logger.info(f"Spam detected from {member} in {channel.guild.name}")
            
        except discord.Forbidden:
            pass
    
    async def _check_invites(self, message: discord.Message):
        """Check for Discord invite links."""
        
        from utils.helpers import is_valid_invite
        
        if is_valid_invite(message.content):
            # Check if user has permission to post invites
            if not message.author.guild_permissions.manage_guild:
                try:
                    await message.delete()
                    
                    embed = EmbedBuilder.warning_embed(
                        "Invite Link Removed",
                        f"{message.author.mention}, invite links are not allowed here."
                    )
                    
                    warning_msg = await message.channel.send(
                        embed=embed,
                        delete_after=10
                    )
                    
                except discord.Forbidden:
                    pass
    
    async def _check_mention_spam(self, message: discord.Message):
        """Check for mention spam."""
        
        if len(message.mentions) > Config.MAX_MENTIONS:
            try:
                await message.delete()
                await message.author.timeout(
                    timedelta(minutes=5),
                    reason="Auto-mod: Mention spam"
                )
                
            except discord.Forbidden:
                pass
    
    @commands.Cog.listener()
    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel):
        """Monitor channel deletions for anti-nuke."""
        
        guild_settings = await self.db.get_guild_settings(channel.guild.id)
        
        if not guild_settings.get('anti_nuke_enabled', False):
            return
        
        # Log the deletion
        await self.db.log_security_event(
            channel.guild.id,
            "channel_deleted",
            {
                "channel_id": channel.id,
                "channel_name": channel.name,
                "channel_type": str(channel.type)
            }
        )
        
        logger.warning(f"Channel deleted in {channel.guild.name}: {channel.name}")
    
    @app_commands.command(name="antiraid", description="Configure anti-raid settings")
    @app_commands.describe(
        enabled="Enable or disable anti-raid protection",
        threshold="Number of joins per minute to trigger anti-raid"
    )
    @is_admin()
    async def antiraid(
        self,
        interaction: discord.Interaction,
        enabled: bool,
        threshold: Optional[app_commands.Range[int, 3, 50]] = None
    ):
        """Configure anti-raid protection."""
        
        await self.db.update_guild_setting(
            interaction.guild_id,
            'anti_raid_enabled',
            enabled
        )
        
        if threshold:
            await self.db.update_guild_setting(
                interaction.guild_id,
                'raid_threshold',
                threshold
            )
        
        status = "enabled" if enabled else "disabled"
        embed = EmbedBuilder.success_embed(
            "Anti-Raid Settings Updated",
            f"Anti-raid protection has been {status}.\n"
            f"Threshold: {threshold or Config.RAID_JOIN_THRESHOLD} joins/minute"
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="antinuke", description="Configure anti-nuke settings")
    @app_commands.describe(enabled="Enable or disable anti-nuke protection")
    @is_admin()
    async def antinuke(
        self,
        interaction: discord.Interaction,
        enabled: bool
    ):
        """Configure anti-nuke protection."""
        
        await self.db.update_guild_setting(
            interaction.guild_id,
            'anti_nuke_enabled',
            enabled
        )
        
        status = "enabled" if enabled else "disabled"
        embed = EmbedBuilder.success_embed(
            "Anti-Nuke Settings Updated",
            f"Anti-nuke protection has been {status}."
        )
        
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Security(bot))