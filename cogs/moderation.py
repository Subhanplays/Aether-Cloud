"""
Advanced moderation system with comprehensive command set.
Includes warning system, punishment tracking, and moderator tools.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, Union
from datetime import timedelta

from utils.embeds import EmbedBuilder
from utils.checks import is_moderator, is_admin
from utils.permissions import PermissionManager
from utils.helpers import parse_duration, format_duration
from database.manager import DatabaseManager
from config import Config
from utils.logger import logger


class Moderation(commands.Cog):
    """Advanced moderation commands and features."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseManager()
    
    # Warn Commands
    @app_commands.command(name="warn", description="Warn a member")
    @app_commands.describe(
        member="The member to warn",
        reason="Reason for the warning",
        severity="Warning severity (1-5)"
    )
    @is_moderator()
    async def warn(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str,
        severity: app_commands.Range[int, 1, 5] = 1
    ):
        """Warn a member."""
        
        # Check moderation permissions
        if not PermissionManager.can_moderate(interaction.user, member):
            embed = EmbedBuilder.error_embed(
                "Permission Denied",
                "You cannot moderate this member due to role hierarchy."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Add warning to database
        warning_count = await self.db.add_warning(
            interaction.guild_id,
            member.id,
            interaction.user.id,
            reason,
            severity
        )
        
        # Log the moderation action
        await self.db.log_moderation_action(
            interaction.guild_id,
            interaction.user.id,
            member.id,
            "warn",
            reason=reason,
            details={"severity": severity, "total_warnings": warning_count}
        )
        
        # Create embed response
        embed = EmbedBuilder.moderation_embed(
            "Member Warned",
            interaction.user,
            member,
            reason=reason,
        )
        embed.add_field(
            name="Warning Count",
            value=f"{warning_count} total warnings",
            inline=True
        )
        embed.add_field(
            name="Severity",
            value=f"{'🔴' * severity}{'⚪' * (5 - severity)}",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Try to DM the warned member
        try:
            dm_embed = EmbedBuilder.warning_embed(
                f"You have been warned in {interaction.guild.name}",
                f"**Reason:** {reason}\n**Severity:** {severity}/5\n"
                f"**Total Warnings:** {warning_count}"
            )
            await member.send(embed=dm_embed)
        except discord.Forbidden:
            pass
    
    @app_commands.command(name="warnings", description="View warnings for a member")
    @app_commands.describe(member="The member to check warnings for")
    @is_moderator()
    async def warnings(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):
        """View warnings for a member."""
        
        warnings = await self.db.get_warnings(interaction.guild_id, member.id)
        
        if not warnings:
            embed = EmbedBuilder.info_embed(
                "No Warnings",
                f"{member.mention} has no warnings."
            )
            await interaction.response.send_message(embed=embed)
            return
        
        embed = EmbedBuilder.create_embed(
            title=f"⚠️ Warnings for {member.display_name}",
            description=f"Total warnings: {len(warnings)}",
            color=Config.EMBED_COLORS['warning'],
            thumbnail=member.display_avatar.url
        )
        
        for i, warning in enumerate(warnings[:10], 1):
            moderator = interaction.guild.get_member(warning['moderator_id'])
            mod_name = moderator.mention if moderator else f"ID: {warning['moderator_id']}"
            
            embed.add_field(
                name=f"Warning #{i}",
                value=f"**Moderator:** {mod_name}\n"
                      f"**Reason:** {warning['reason']}\n"
                      f"**Severity:** {warning.get('severity', 1)}/5\n"
                      f"**Date:** {discord.utils.format_dt(warning['timestamp'], 'R')}",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="clearwarnings", description="Clear all warnings for a member")
    @app_commands.describe(member="The member to clear warnings for")
    @is_admin()
    async def clear_warnings(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):
        """Clear all warnings for a member."""
        
        count = await self.db.clear_warnings(interaction.guild_id, member.id)
        
        embed = EmbedBuilder.success_embed(
            "Warnings Cleared",
            f"Cleared {count} warnings for {member.mention}."
        )
        
        await interaction.response.send_message(embed=embed)
    
    # Ban Commands
    @app_commands.command(name="ban", description="Ban a member from the server")
    @app_commands.describe(
        member="The member to ban",
        reason="Reason for the ban",
        delete_messages="Delete messages from the past X days (0-7)"
    )
    @is_moderator()
    async def ban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided",
        delete_messages: app_commands.Range[int, 0, 7] = 0
    ):
        """Ban a member from the server."""
        
        if not PermissionManager.can_moderate(interaction.user, member):
            embed = EmbedBuilder.error_embed(
                "Permission Denied",
                "You cannot ban this member due to role hierarchy."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Confirmation embed
        confirm_embed = EmbedBuilder.warning_embed(
            "Confirm Ban",
            f"Are you sure you want to ban {member.mention}?\n"
            f"**Reason:** {reason}"
        )
        
        # Create confirmation view
        class ConfirmBan(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.value = None
            
            @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
            async def confirm(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.value = True
                self.stop()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.value = False
                self.stop()
        
        view = ConfirmBan()
        await interaction.response.send_message(embed=confirm_embed, view=view)
        
        await view.wait()
        
        if view.value is None:
            await interaction.edit_original_response(
                embed=EmbedBuilder.error_embed("Timeout", "Ban cancelled due to timeout."),
                view=None
            )
            return
        
        if not view.value:
            await interaction.edit_original_response(
                embed=EmbedBuilder.info_embed("Cancelled", "Ban has been cancelled."),
                view=None
            )
            return
        
        # Execute ban
        try:
            await member.ban(
                reason=f"Banned by {interaction.user}: {reason}",
                delete_message_days=delete_messages
            )
            
            embed = EmbedBuilder.moderation_embed(
                "Member Banned",
                interaction.user,
                member,
                reason=reason,
            )
            embed.add_field(
                name="Message Deletion",
                value=f"{delete_messages} days of messages deleted",
                inline=True
            )
            
            await interaction.edit_original_response(embed=embed, view=None)
            
            # Log the action
            await self.db.log_moderation_action(
                interaction.guild_id,
                interaction.user.id,
                member.id,
                "ban",
                reason=reason,
                details={"delete_message_days": delete_messages}
            )
            
        except discord.Forbidden:
            await interaction.edit_original_response(
                embed=EmbedBuilder.error_embed(
                    "Failed",
                    "I don't have permission to ban this member."
                ),
                view=None
            )
    
    @app_commands.command(name="unban", description="Unban a user from the server")
    @app_commands.describe(
        user_id="The ID of the user to unban",
        reason="Reason for the unban"
    )
    @is_moderator()
    async def unban(
        self,
        interaction: discord.Interaction,
        user_id: str,
        reason: str = "No reason provided"
    ):
        """Unban a user from the server."""
        
        try:
            user = await self.bot.fetch_user(int(user_id))
        except (ValueError, discord.NotFound):
            embed = EmbedBuilder.error_embed(
                "Invalid User",
                "Please provide a valid user ID."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            await interaction.guild.unban(
                user,
                reason=f"Unbanned by {interaction.user}: {reason}"
            )
            
            embed = EmbedBuilder.success_embed(
                "Member Unbanned",
                f"Successfully unbanned {user.mention} ({user.id}).\n**Reason:** {reason}"
            )
            
            await interaction.response.send_message(embed=embed)
            
        except discord.NotFound:
            embed = EmbedBuilder.error_embed(
                "Not Found",
                "This user is not in the ban list."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except discord.Forbidden:
            embed = EmbedBuilder.error_embed(
                "Permission Denied",
                "I don't have permission to unban members."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Timeout Commands
    @app_commands.command(name="timeout", description="Timeout a member")
    @app_commands.describe(
        member="The member to timeout",
        duration="Duration (e.g., 1h, 30m, 1d)",
        reason="Reason for the timeout"
    )
    @is_moderator()
    async def timeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: str,
        reason: str = "No reason provided"
    ):
        """Timeout a member."""
        
        if not PermissionManager.can_moderate(interaction.user, member):
            embed = EmbedBuilder.error_embed(
                "Permission Denied",
                "You cannot timeout this member."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        seconds = parse_duration(duration)
        if not seconds:
            embed = EmbedBuilder.error_embed(
                "Invalid Duration",
                "Please use a valid duration format (e.g., 1h, 30m, 1d)."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if seconds > 2419200:  # 28 days max
            embed = EmbedBuilder.error_embed(
                "Duration Too Long",
                "Timeout cannot be longer than 28 days."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            until = discord.utils.utcnow() + timedelta(seconds=seconds)
            await member.timeout(until, reason=f"Timeout by {interaction.user}: {reason}")
            
            duration_str = format_duration(seconds)
            embed = EmbedBuilder.moderation_embed(
                "Member Timed Out",
                interaction.user,
                member,
                reason=reason,
                duration=duration_str
            )
            
            await interaction.response.send_message(embed=embed)
            
            # Try to notify the member
            try:
                notify_embed = EmbedBuilder.warning_embed(
                    f"You have been timed out in {interaction.guild.name}",
                    f"**Duration:** {duration_str}\n**Reason:** {reason}"
                )
                await member.send(embed=notify_embed)
            except discord.Forbidden:
                pass
            
        except discord.Forbidden:
            embed = EmbedBuilder.error_embed(
                "Permission Denied",
                "I don't have permission to timeout this member."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="untimeout", description="Remove timeout from a member")
    @app_commands.describe(
        member="The member to remove timeout from",
        reason="Reason for removing timeout"
    )
    @is_moderator()
    async def untimeout(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided"
    ):
        """Remove timeout from a member."""
        
        if not member.is_timed_out():
            embed = EmbedBuilder.error_embed(
                "Not Timed Out",
                f"{member.mention} is not currently timed out."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            await member.timeout(None, reason=f"Timeout removed by {interaction.user}: {reason}")
            
            embed = EmbedBuilder.success_embed(
                "Timeout Removed",
                f"Successfully removed timeout from {member.mention}.\n**Reason:** {reason}"
            )
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            embed = EmbedBuilder.error_embed(
                "Permission Denied",
                "I don't have permission to remove the timeout."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Channel Management
    @app_commands.command(name="purge", description="Purge messages from a channel")
    @app_commands.describe(
        amount="Number of messages to purge (1-1000)",
        user="Filter by specific user (optional)",
        contains="Filter by message content (optional)"
    )
    @is_moderator()
    async def purge(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1, 1000],
        user: Optional[discord.Member] = None,
        contains: Optional[str] = None
    ):
        """Purge messages from the channel."""
        
        await interaction.response.defer(ephemeral=True)
        
        def check(msg):
            conditions = []
            if user:
                conditions.append(msg.author.id == user.id)
            if contains:
                conditions.append(contains.lower() in msg.content.lower())
            return all(conditions)
        
        try:
            if user or contains:
                # Filtered purge
                deleted = await interaction.channel.purge(
                    limit=amount,
                    check=check,
                    before=interaction.created_at
                )
            else:
                # Bulk purge
                deleted = await interaction.channel.purge(
                    limit=amount,
                    bulk=True,
                    before=interaction.created_at
                )
            
            embed = EmbedBuilder.success_embed(
                "Messages Purged",
                f"Successfully deleted {len(deleted)} messages."
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            # Log the action
            await self.db.log_moderation_action(
                interaction.guild_id,
                interaction.user.id,
                0,
                "purge",
                details={
                    "amount": len(deleted),
                    "channel_id": interaction.channel_id,
                    "filtered_by_user": user.id if user else None,
                    "filtered_by_content": contains
                }
            )
            
        except discord.Forbidden:
            embed = EmbedBuilder.error_embed(
                "Permission Denied",
                "I don't have permission to delete messages in this channel."
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except discord.HTTPException as e:
            embed = EmbedBuilder.error_embed(
                "Error",
                f"Failed to purge messages: {str(e)}"
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="lock", description="Lock a channel")
    @app_commands.describe(
        channel="The channel to lock (defaults to current)",
        reason="Reason for locking the channel"
    )
    @is_moderator()
    async def lock(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        reason: str = "No reason provided"
    ):
        """Lock a channel to prevent members from sending messages."""
        
        channel = channel or interaction.channel
        
        try:
            # Get the default role
            default_role = interaction.guild.default_role
            
            # Deny send messages permission
            overwrite = channel.overwrites_for(default_role)
            overwrite.send_messages = False
            
            await channel.set_permissions(
                default_role,
                overwrite=overwrite,
                reason=f"Channel locked by {interaction.user}: {reason}"
            )
            
            embed = EmbedBuilder.success_embed(
                "Channel Locked",
                f"🔒 {channel.mention} has been locked.\n**Reason:** {reason}"
            )
            
            await interaction.response.send_message(embed=embed)
            
            # Notify in the locked channel
            if channel != interaction.channel:
                await channel.send(embed=embed)
            
        except discord.Forbidden:
            embed = EmbedBuilder.error_embed(
                "Permission Denied",
                "I don't have permission to manage this channel."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="unlock", description="Unlock a channel")
    @app_commands.describe(
        channel="The channel to unlock (defaults to current)",
        reason="Reason for unlocking the channel"
    )
    @is_moderator()
    async def unlock(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        reason: str = "No reason provided"
    ):
        """Unlock a previously locked channel."""
        
        channel = channel or interaction.channel
        
        try:
            default_role = interaction.guild.default_role
            overwrite = channel.overwrites_for(default_role)
            overwrite.send_messages = None  # Reset to default
            
            await channel.set_permissions(
                default_role,
                overwrite=overwrite,
                reason=f"Channel unlocked by {interaction.user}: {reason}"
            )
            
            embed = EmbedBuilder.success_embed(
                "Channel Unlocked",
                f"🔓 {channel.mention} has been unlocked.\n**Reason:** {reason}"
            )
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            embed = EmbedBuilder.error_embed(
                "Permission Denied",
                "I don't have permission to manage this channel."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="slowmode", description="Set slowmode for a channel")
    @app_commands.describe(
        seconds="Slowmode delay in seconds (0 to disable)",
        channel="The channel to set slowmode for (defaults to current)"
    )
    @is_moderator()
    async def slowmode(
        self,
        interaction: discord.Interaction,
        seconds: app_commands.Range[int, 0, 21600],
        channel: Optional[discord.TextChannel] = None
    ):
        """Set slowmode for a channel."""
        
        channel = channel or interaction.channel
        
        try:
            await channel.edit(
                slowmode_delay=seconds,
                reason=f"Slowmode set by {interaction.user}"
            )
            
            if seconds == 0:
                embed = EmbedBuilder.success_embed(
                    "Slowmode Disabled",
                    f"Slowmode has been disabled in {channel.mention}."
                )
            else:
                embed = EmbedBuilder.success_embed(
                    "Slowmode Set",
                    f"Slowmode set to {seconds} seconds in {channel.mention}."
                )
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            embed = EmbedBuilder.error_embed(
                "Permission Denied",
                "I don't have permission to manage this channel."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    # Bulk Moderation
    @app_commands.command(name="softban", description="Softban a member (ban and immediately unban)")
    @app_commands.describe(
        member="The member to softban",
        reason="Reason for the softban"
    )
    @is_moderator()
    async def softban(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        reason: str = "No reason provided"
    ):
        """Softban a member to delete their messages and rejoin."""
        
        if not PermissionManager.can_moderate(interaction.user, member):
            embed = EmbedBuilder.error_embed(
                "Permission Denied",
                "You cannot softban this member."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            # Ban
            await member.ban(
                reason=f"Softban by {interaction.user}: {reason}",
                delete_message_days=7
            )
            
            # Immediately unban
            await interaction.guild.unban(
                member,
                reason=f"Softban unban by {interaction.user}: {reason}"
            )
            
            embed = EmbedBuilder.moderation_embed(
                "Member Softbanned",
                interaction.user,
                member,
                reason=reason,
            )
            embed.add_field(
                name="Note",
                value="Their messages from the past 7 days have been deleted.",
                inline=False
            )
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            embed = EmbedBuilder.error_embed(
                "Permission Denied",
                "I don't have permission to softban this member."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Moderation(bot))