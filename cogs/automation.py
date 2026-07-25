"""
Automation system for welcome messages, auto-roles, and scheduled tasks.
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from typing import Optional, List
from datetime import datetime, timedelta

from utils.embeds import EmbedBuilder
from utils.checks import is_admin, is_moderator
from database.manager import DatabaseManager
from config import Config
from utils.logger import logger


class Automation(commands.Cog):
    """Automation features including welcome, goodbye, and auto-responses."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseManager()
        self.auto_responses_cache = {}
        self.scheduled_tasks.start()
    
    def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.scheduled_tasks.cancel()
    
    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Handle welcome messages when a member joins."""
        
        guild_settings = await self.db.get_guild_settings(member.guild.id)
        
        if not guild_settings.get('welcome_enabled', False):
            return
        
        welcome_channel_id = guild_settings.get('welcome_channel_id')
        if not welcome_channel_id:
            return
        
        channel = member.guild.get_channel(welcome_channel_id)
        if not channel:
            return
        
        # Get welcome message
        welcome_message = guild_settings.get(
            'welcome_message',
            'Welcome {user} to {server}! 🎉'
        )
        
        # Format the message
        message = welcome_message.format(
            user=member.mention,
            user_name=member.display_name,
            user_id=member.id,
            server=member.guild.name,
            member_count=member.guild.member_count,
            joined_at=discord.utils.format_dt(member.joined_at, 'R') if member.joined_at else "Just now"
        )
        
        # Create embed
        embed = EmbedBuilder.create_embed(
            title=f"👋 Welcome to {member.guild.name}!",
            description=message,
            color=Config.EMBED_COLORS['success'],
            thumbnail=member.display_avatar.url,
            fields=[
                {
                    "name": "Account Created",
                    "value": discord.utils.format_dt(member.created_at, 'R'),
                    "inline": True
                },
                {
                    "name": "Member Count",
                    "value": f"You are member #{member.guild.member_count}",
                    "inline": True
                }
            ]
        )
        
        try:
            await channel.send(content=member.mention, embed=embed)
        except discord.Forbidden:
            pass
        
        # Auto-role assignment
        auto_roles = guild_settings.get('auto_roles', [])
        for role_id in auto_roles:
            role = member.guild.get_role(role_id)
            if role and not role.managed:
                try:
                    await member.add_roles(
                        role,
                        reason="Auto-role on join"
                    )
                except discord.Forbidden:
                    pass
    
    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Handle goodbye messages when a member leaves."""
        
        guild_settings = await self.db.get_guild_settings(member.guild.id)
        
        if not guild_settings.get('goodbye_enabled', False):
            return
        
        goodbye_channel_id = guild_settings.get('goodbye_channel_id')
        if not goodbye_channel_id:
            return
        
        channel = member.guild.get_channel(goodbye_channel_id)
        if not channel:
            return
        
        goodbye_message = guild_settings.get(
            'goodbye_message',
            'Goodbye {user}! We\'ll miss you! 👋'
        )
        
        message = goodbye_message.format(
            user=member.display_name,
            user_id=member.id,
            server=member.guild.name,
            member_count=member.guild.member_count,
            joined_at=discord.utils.format_dt(member.joined_at, 'R') if member.joined_at else "Unknown"
        )
        
        embed = EmbedBuilder.create_embed(
            title=f"👋 Goodbye!",
            description=message,
            color=Config.EMBED_COLORS['error'],
            thumbnail=member.display_avatar.url,
            fields=[
                {
                    "name": "Joined Server",
                    "value": discord.utils.format_dt(member.joined_at, 'R') if member.joined_at else "Unknown",
                    "inline": True
                },
                {
                    "name": "Time in Server",
                    "value": self._get_time_in_server(member.joined_at) if member.joined_at else "Unknown",
                    "inline": True
                }
            ]
        )
        
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            pass
    
    def _get_time_in_server(self, joined_at: datetime) -> str:
        """Calculate time spent in server."""
        if not joined_at:
            return "Unknown"
        
        delta = datetime.utcnow() - joined_at
        days = delta.days
        
        if days == 0:
            return "Less than a day"
        elif days == 1:
            return "1 day"
        elif days < 30:
            return f"{days} days"
        elif days < 365:
            months = days // 30
            return f"{months} month(s)"
        else:
            years = days // 365
            months = (days % 365) // 30
            return f"{years} year(s), {months} month(s)"
    
    # Welcome Configuration Commands
    @app_commands.command(name="welcome", description="Configure welcome messages")
    @app_commands.describe(
        enabled="Enable or disable welcome messages",
        channel="Channel for welcome messages",
        message="Custom welcome message (use {user}, {server}, {member_count})"
    )
    @is_admin()
    async def welcome_config(
        self,
        interaction: discord.Interaction,
        enabled: Optional[bool] = None,
        channel: Optional[discord.TextChannel] = None,
        message: Optional[str] = None
    ):
        """Configure welcome message settings."""
        
        updates = []
        
        if enabled is not None:
            await self.db.update_guild_setting(
                interaction.guild_id, 'welcome_enabled', enabled
            )
            updates.append(f"Welcome messages: {'Enabled' if enabled else 'Disabled'}")
        
        if channel:
            await self.db.update_guild_setting(
                interaction.guild_id, 'welcome_channel_id', channel.id
            )
            updates.append(f"Welcome channel: {channel.mention}")
        
        if message:
            await self.db.update_guild_setting(
                interaction.guild_id, 'welcome_message', message
            )
            updates.append(f"Welcome message: {message}")
        
        if not updates:
            embed = EmbedBuilder.error_embed(
                "No Changes",
                "Please specify at least one setting to change."
            )
        else:
            embed = EmbedBuilder.success_embed(
                "Welcome Settings Updated",
                "\n".join(updates)
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="goodbye", description="Configure goodbye messages")
    @app_commands.describe(
        enabled="Enable or disable goodbye messages",
        channel="Channel for goodbye messages",
        message="Custom goodbye message"
    )
    @is_admin()
    async def goodbye_config(
        self,
        interaction: discord.Interaction,
        enabled: Optional[bool] = None,
        channel: Optional[discord.TextChannel] = None,
        message: Optional[str] = None
    ):
        """Configure goodbye message settings."""
        
        updates = []
        
        if enabled is not None:
            await self.db.update_guild_setting(
                interaction.guild_id, 'goodbye_enabled', enabled
            )
            updates.append(f"Goodbye messages: {'Enabled' if enabled else 'Disabled'}")
        
        if channel:
            await self.db.update_guild_setting(
                interaction.guild_id, 'goodbye_channel_id', channel.id
            )
            updates.append(f"Goodbye channel: {channel.mention}")
        
        if message:
            await self.db.update_guild_setting(
                interaction.guild_id, 'goodbye_message', message
            )
            updates.append(f"Goodbye message updated")
        
        if updates:
            embed = EmbedBuilder.success_embed(
                "Goodbye Settings Updated",
                "\n".join(updates)
            )
        else:
            embed = EmbedBuilder.error_embed(
                "No Changes",
                "Please specify at least one setting to change."
            )
        
        await interaction.response.send_message(embed=embed)
    
    # Auto Roles
    @app_commands.command(name="autorole", description="Configure auto-assigned roles")
    @app_commands.describe(
        action="Add or remove auto-role",
        role="The role to auto-assign"
    )
    @is_admin()
    async def autorole(
        self,
        interaction: discord.Interaction,
        action: str,
        role: discord.Role
    ):
        """Add or remove auto-assigned roles."""
        
        guild_settings = await self.db.get_guild_settings(interaction.guild_id)
        auto_roles = guild_settings.get('auto_roles', [])
        
        if action.lower() == 'add':
            if role.id in auto_roles:
                embed = EmbedBuilder.error_embed(
                    "Already Exists",
                    f"{role.mention} is already an auto-role."
                )
            else:
                auto_roles.append(role.id)
                await self.db.update_guild_setting(
                    interaction.guild_id, 'auto_roles', auto_roles
                )
                embed = EmbedBuilder.success_embed(
                    "Auto-Role Added",
                    f"{role.mention} will be automatically assigned to new members."
                )
        
        elif action.lower() == 'remove':
            if role.id not in auto_roles:
                embed = EmbedBuilder.error_embed(
                    "Not Found",
                    f"{role.mention} is not an auto-role."
                )
            else:
                auto_roles.remove(role.id)
                await self.db.update_guild_setting(
                    interaction.guild_id, 'auto_roles', auto_roles
                )
                embed = EmbedBuilder.success_embed(
                    "Auto-Role Removed",
                    f"{role.mention} removed from auto-roles."
                )
        else:
            embed = EmbedBuilder.error_embed(
                "Invalid Action",
                "Use 'add' or 'remove'."
            )
        
        await interaction.response.send_message(embed=embed)
    
    # Auto-Response System
    @app_commands.command(name="autoresponse", description="Manage auto-responses")
    @app_commands.describe(
        action="Add, remove, or list auto-responses",
        trigger="The keyword that triggers the response",
        response="The auto-response message"
    )
    @is_admin()
    async def autoresponse(
        self,
        interaction: discord.Interaction,
        action: str,
        trigger: Optional[str] = None,
        response: Optional[str] = None
    ):
        """Configure automatic responses based on keywords."""
        
        guild_settings = await self.db.get_guild_settings(interaction.guild_id)
        
        if action.lower() == 'list':
            auto_responses = guild_settings.get('auto_responses', {})
            if not auto_responses:
                embed = EmbedBuilder.info_embed(
                    "No Auto-Responses",
                    "There are no auto-responses configured."
                )
            else:
                description = []
                for trigger, response in auto_responses.items():
                    description.append(f"**{trigger}** → {response[:50]}...")
                
                embed = EmbedBuilder.create_embed(
                    title="🤖 Auto-Responses",
                    description="\n".join(description),
                    color=Config.EMBED_COLORS['info']
                )
        
        elif action.lower() == 'add':
            if not trigger or not response:
                embed = EmbedBuilder.error_embed(
                    "Missing Arguments",
                    "Please provide both trigger and response."
                )
                await interaction.response.send_message(embed=embed)
                return
            
            auto_responses = guild_settings.get('auto_responses', {})
            auto_responses[trigger.lower()] = response
            
            await self.db.update_guild_setting(
                interaction.guild_id, 'auto_responses', auto_responses
            )
            
            embed = EmbedBuilder.success_embed(
                "Auto-Response Added",
                f"**Trigger:** {trigger}\n**Response:** {response}"
            )
        
        elif action.lower() == 'remove':
            if not trigger:
                embed = EmbedBuilder.error_embed(
                    "Missing Trigger",
                    "Please provide the trigger to remove."
                )
                await interaction.response.send_message(embed=embed)
                return
            
            auto_responses = guild_settings.get('auto_responses', {})
            if trigger.lower() in auto_responses:
                del auto_responses[trigger.lower()]
                await self.db.update_guild_setting(
                    interaction.guild_id, 'auto_responses', auto_responses
                )
                embed = EmbedBuilder.success_embed(
                    "Auto-Response Removed",
                    f"Removed auto-response for trigger: {trigger}"
                )
            else:
                embed = EmbedBuilder.error_embed(
                    "Not Found",
                    f"No auto-response found for trigger: {trigger}"
                )
        else:
            embed = EmbedBuilder.error_embed(
                "Invalid Action",
                "Use 'add', 'remove', or 'list'."
            )
        
        await interaction.response.send_message(embed=embed)
    
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Check for auto-responses."""
        
        if message.author.bot or not message.guild:
            return
        
        guild_settings = await self.db.get_guild_settings(message.guild.id)
        auto_responses = guild_settings.get('auto_responses', {})
        
        if not auto_responses:
            return
        
        content_lower = message.content.lower()
        
        for trigger, response in auto_responses.items():
            if trigger in content_lower:
                try:
                    await message.channel.send(
                        response.format(
                            user=message.author.mention,
                            user_name=message.author.display_name,
                            channel=message.channel.mention
                        )
                    )
                    break
                except discord.Forbidden:
                    break
    
    # Scheduled Announcements
    @tasks.loop(minutes=1)
    async def scheduled_tasks(self):
        """Check for scheduled announcements."""
        # This is a placeholder - implement based on your needs
        pass
    
    @scheduled_tasks.before_loop
    async def before_scheduled_tasks(self):
        """Wait until bot is ready before starting tasks."""
        await self.bot.wait_until_ready()
    
    @app_commands.command(name="schedule", description="Schedule an announcement")
    @app_commands.describe(
        channel="Channel for the announcement",
        time="Time in minutes from now",
        message="Announcement message"
    )
    @is_admin()
    async def schedule_announcement(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        time: int,
        message: str
    ):
        """Schedule an announcement."""
        
        if time < 1:
            embed = EmbedBuilder.error_embed(
                "Invalid Time",
                "Time must be at least 1 minute."
            )
            await interaction.response.send_message(embed=embed)
            return
        
        # Schedule the message
        self.bot.loop.create_task(
            self._send_scheduled_message(channel, message, time)
        )
        
        embed = EmbedBuilder.success_embed(
            "Announcement Scheduled",
            f"Message will be sent in {channel.mention} in {time} minutes."
        )
        
        await interaction.response.send_message(embed=embed)
    
    async def _send_scheduled_message(
        self,
        channel: discord.TextChannel,
        message: str,
        delay_minutes: int
    ):
        """Send a scheduled message after delay."""
        await asyncio.sleep(delay_minutes * 60)
        
        try:
            await channel.send(message)
        except discord.Forbidden:
            pass


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Automation(bot))