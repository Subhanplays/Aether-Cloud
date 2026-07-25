"""
Complete ticket management system with proper interaction handling.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List, Dict
from datetime import datetime
import io
import asyncio

from utils.embeds import EmbedBuilder
from utils.checks import is_admin, is_moderator
from database.manager import DatabaseManager
from config import Config, Constants
from utils.logger import logger


class Tickets(commands.Cog):
    """Complete ticket management system."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseManager()
        # Store active ticket panels
        self.ticket_panels: Dict[int, int] = {}
        # Store ticket cooldowns
        self.ticket_cooldowns: Dict[int, datetime] = {}
    
    @app_commands.command(name="ticketpanel", description="Create a ticket panel")
    @app_commands.describe(
        channel="Channel to send the ticket panel",
        title="Title for the ticket panel"
    )
    @is_admin()
    async def ticket_panel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        title: str = "Support Tickets"
    ):
        """Create a ticket creation panel."""
        
        await interaction.response.defer(ephemeral=True)
        
        embed = EmbedBuilder.create_embed(
            title=f"🎫 {title}",
            description=(
                "**Need help? Create a ticket!**\n\n"
                "Our support team is here to assist you with:\n"
                "🔹 **General Support** - Questions and help\n"
                "🔹 **Report Issue** - Report bugs or problems\n"
                "🔹 **Account Help** - Account related issues\n"
                "🔹 **Billing** - Payment and subscription help\n"
                "🔹 **Other** - Any other inquiries\n\n"
                "**Click the dropdown below to create a ticket.**\n"
                "⚠️ Please do not create duplicate tickets."
            ),
            color=Config.EMBED_COLORS['ticket'],
            footer="We typically respond within 24 hours"
        )
        
        # Create the ticket view
        view = TicketCreationView(self)
        
        await channel.send(embed=embed, view=view)
        self.ticket_panels[channel.id] = channel.id
        
        await interaction.followup.send(
            embed=EmbedBuilder.success_embed(
                "Ticket Panel Created",
                f"Ticket panel has been set up in {channel.mention}\n\n"
                "Users can now create tickets by clicking the dropdown menu."
            ),
            ephemeral=True
        )
    
    @app_commands.command(name="ticketadd", description="Add a user to a ticket")
    @app_commands.describe(
        member="The member to add to the ticket"
    )
    @is_moderator()
    async def ticket_add(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):
        """Add a user to the current ticket."""
        
        # Check if current channel is a ticket
        ticket = await self.db.get_ticket(interaction.guild_id, interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed(
                    "Not a Ticket",
                    "This command can only be used in ticket channels."
                ),
                ephemeral=True
            )
            return
        
        # Add user to channel
        try:
            await interaction.channel.set_permissions(
                member,
                read_messages=True,
                send_messages=True,
                reason=f"Added by {interaction.user}"
            )
            
            await interaction.response.send_message(
                embed=EmbedBuilder.success_embed(
                    "User Added",
                    f"{member.mention} has been added to this ticket."
                )
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed(
                    "Permission Denied",
                    "I don't have permission to modify channel permissions."
                ),
                ephemeral=True
            )
    
    @app_commands.command(name="ticketremove", description="Remove a user from a ticket")
    @app_commands.describe(member="The member to remove from the ticket")
    @is_moderator()
    async def ticket_remove(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):
        """Remove a user from the current ticket."""
        
        ticket = await self.db.get_ticket(interaction.guild_id, interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed(
                    "Not a Ticket",
                    "This command can only be used in ticket channels."
                ),
                ephemeral=True
            )
            return
        
        try:
            await interaction.channel.set_permissions(
                member,
                overwrite=None,
                reason=f"Removed by {interaction.user}"
            )
            
            await interaction.response.send_message(
                embed=EmbedBuilder.success_embed(
                    "User Removed",
                    f"{member.mention} has been removed from this ticket."
                )
            )
        except discord.Forbidden:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed(
                    "Permission Denied",
                    "I don't have permission to modify channel permissions."
                ),
                ephemeral=True
            )
    
    @app_commands.command(name="ticketclose", description="Close the current ticket")
    @is_moderator()
    async def ticket_close(self, interaction: discord.Interaction):
        """Close the current ticket."""
        
        ticket = await self.db.get_ticket(interaction.guild_id, interaction.channel_id)
        
        if not ticket:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed(
                    "Not a Ticket",
                    "This command can only be used in ticket channels."
                ),
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Create transcript
        transcript = await self._create_transcript(interaction.channel)
        
        # Update ticket in database
        await self.db.update_ticket_status(
            interaction.guild_id,
            interaction.channel_id,
            'closed',
            interaction.user.id
        )
        
        # Send transcript to log channel
        settings = await self.db.get_guild_settings(interaction.guild_id)
        log_channel_id = settings.get('ticket_log_channel')
        
        if log_channel_id and transcript:
            log_channel = interaction.guild.get_channel(log_channel_id)
            if log_channel:
                embed = EmbedBuilder.create_embed(
                    title="📋 Ticket Closed",
                    color=Config.EMBED_COLORS['ticket'],
                    fields=[
                        {"name": "Channel", "value": interaction.channel.name, "inline": True},
                        {"name": "Category", "value": ticket.get('category', 'Unknown'), "inline": True},
                        {"name": "Created By", "value": f"<@{ticket.get('user_id')}>", "inline": True},
                        {"name": "Closed By", "value": interaction.user.mention, "inline": True},
                        {"name": "Created At", "value": discord.utils.format_dt(ticket['created_at'], 'R'), "inline": True},
                    ]
                )
                
                # Send transcript file
                file = discord.File(
                    io.StringIO(transcript),
                    filename=f"transcript-{interaction.channel.name}.txt"
                )
                
                await log_channel.send(embed=embed, file=file)
        
        # Notify before deleting
        await interaction.followup.send(
            embed=EmbedBuilder.info_embed(
                "Ticket Closed",
                "This ticket will be deleted in 5 seconds..."
            )
        )
        
        await asyncio.sleep(5)
        
        try:
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        except discord.Forbidden:
            pass
    
    @app_commands.command(name="ticketstats", description="View ticket statistics")
    @is_moderator()
    async def ticket_stats(self, interaction: discord.Interaction):
        """View ticket statistics for the server."""
        
        # This would query the database for stats
        # For now, show basic info
        
        embed = EmbedBuilder.create_embed(
            title="📊 Ticket Statistics",
            color=Config.EMBED_COLORS['ticket'],
            description="Ticket system statistics will be displayed here.",
            fields=[
                {"name": "Total Tickets", "value": "Coming soon", "inline": True},
                {"name": "Open Tickets", "value": "Coming soon", "inline": True},
                {"name": "Closed Today", "value": "Coming soon", "inline": True},
            ]
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _create_transcript(self, channel: discord.TextChannel) -> Optional[str]:
        """Create a transcript of the ticket channel."""
        
        transcript = []
        transcript.append(f"Ticket Transcript - {channel.name}")
        transcript.append(f"Guild: {channel.guild.name}")
        transcript.append(f"Created: {channel.created_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
        transcript.append("=" * 50)
        transcript.append("")
        
        try:
            async for message in channel.history(limit=None, oldest_first=True):
                timestamp = message.created_at.strftime("%Y-%m-%d %H:%M:%S")
                
                # Handle different message types
                if message.author.bot:
                    transcript.append(f"[{timestamp}] BOT: {message.content or '[Embed/Attachment]'}")
                else:
                    transcript.append(f"[{timestamp}] {message.author} ({message.author.id}): {message.content or '[No content]'}")
                
                # Log attachments
                if message.attachments:
                    for attachment in message.attachments:
                        transcript.append(f"  📎 Attachment: {attachment.filename} - {attachment.url}")
                
                # Log embeds
                if message.embeds:
                    for embed in message.embeds:
                        if embed.title:
                            transcript.append(f"  📋 Embed: {embed.title}")
                        if embed.description:
                            transcript.append(f"     {embed.description[:100]}...")
            
        except discord.Forbidden:
            transcript.append("[Error: Could not read all messages]")
        except Exception as e:
            transcript.append(f"[Error creating transcript: {str(e)}]")
        
        return "\n".join(transcript)


class TicketCreationView(discord.ui.View):
    """View for the ticket creation dropdown."""
    
    def __init__(self, cog: Tickets):
        super().__init__(timeout=None)
        self.cog = cog
    
    @discord.ui.select(
        placeholder="Select ticket type...",
        min_values=1,
        max_values=1,
        options=[
            discord.SelectOption(
                label="General Support",
                description="Get help with general questions",
                emoji="🔹",
                value="support"
            ),
            discord.SelectOption(
                label="Report Issue",
                description="Report a bug or problem",
                emoji="🚨",
                value="report"
            ),
            discord.SelectOption(
                label="Account Help",
                description="Help with your account",
                emoji="👤",
                value="account"
            ),
            discord.SelectOption(
                label="Billing & Payments",
                description="Questions about billing",
                emoji="💳",
                value="billing"
            ),
            discord.SelectOption(
                label="Other Inquiry",
                description="Any other questions",
                emoji="❓",
                value="other"
            ),
        ]
    )
    async def select_category(self, interaction: discord.Interaction, select: discord.ui.Select):
        """Handle category selection."""
        
        category = select.values[0]
        
        # Check cooldown
        if interaction.user.id in self.cog.ticket_cooldowns:
            last_ticket = self.cog.ticket_cooldowns[interaction.user.id]
            if (datetime.utcnow() - last_ticket).seconds < 60:
                remaining = 60 - (datetime.utcnow() - last_ticket).seconds
                await interaction.response.send_message(
                    embed=EmbedBuilder.error_embed(
                        "Cooldown",
                        f"Please wait {remaining} seconds before creating another ticket."
                    ),
                    ephemeral=True
                )
                return
        
        # Create the ticket
        await self._create_ticket(interaction, category)
    
    async def _create_ticket(self, interaction: discord.Interaction, category: str):
        """Create a new ticket channel."""
        
        # Defer the response immediately to prevent timeout
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        user = interaction.user
        
        # Find or create ticket category
        ticket_category = discord.utils.get(guild.categories, name="Tickets")
        
        if not ticket_category:
            try:
                ticket_category = await guild.create_category(
                    "Tickets",
                    reason="Ticket system category",
                    position=0
                )
            except discord.Forbidden:
                await interaction.followup.send(
                    embed=EmbedBuilder.error_embed(
                        "Permission Error",
                        "I don't have permission to create categories. Please contact an administrator."
                    ),
                    ephemeral=True
                )
                return
        
        # Generate ticket name
        category_emoji = {
            'support': '🔹',
            'report': '🚨',
            'account': '👤',
            'billing': '💳',
            'other': '❓'
        }
        
        emoji = category_emoji.get(category, '🎫')
        channel_name = f"{emoji}・{user.name.lower().replace(' ', '-')}"
        
        # Make sure channel name isn't too long
        if len(channel_name) > 100:
            channel_name = channel_name[:97] + "..."
        
        # Set up permissions
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                manage_channels=True,
                manage_messages=True,
                embed_links=True,
                attach_files=True,
                read_message_history=True
            ),
            user: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
                read_message_history=True,
                embed_links=True,
                attach_files=True
            )
        }
        
        # Add staff roles
        settings = await self.cog.db.get_guild_settings(guild.id)
        mod_role_ids = settings.get('mod_role_ids', [])
        admin_role_ids = settings.get('admin_role_ids', [])
        
        for role_id in mod_role_ids + admin_role_ids:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    read_message_history=True,
                    manage_messages=True
                )
        
        try:
            # Create the channel
            channel = await guild.create_text_channel(
                name=channel_name,
                category=ticket_category,
                overwrites=overwrites,
                reason=f"Ticket created by {user}",
                topic=f"Ticket created by {user} | Category: {category}"
            )
            
            # Save to database
            await self.cog.db.create_ticket(
                guild.id,
                channel.id,
                user.id,
                category
            )
            
            # Set cooldown
            self.cog.ticket_cooldowns[user.id] = datetime.utcnow()
            
            # Create ticket welcome message
            category_names = {
                'support': 'General Support',
                'report': 'Report Issue',
                'account': 'Account Help',
                'billing': 'Billing & Payments',
                'other': 'Other Inquiry'
            }
            
            embed = EmbedBuilder.create_embed(
                title=f"{emoji} {category_names.get(category, 'Ticket')}",
                description=(
                    f"Welcome {user.mention}!\n\n"
                    f"**Category:** {category_names.get(category, category)}\n"
                    f"**Created:** {discord.utils.format_dt(datetime.utcnow(), 'F')}\n\n"
                    f"Please describe your issue in detail. "
                    f"Our staff team will assist you as soon as possible.\n\n"
                    f"**Tips for faster support:**\n"
                    f"• Be specific about your issue\n"
                    f"• Include any error messages\n"
                    f"• Attach screenshots if relevant"
                ),
                color=Config.EMBED_COLORS['ticket']
            )
            
            # Create ticket control buttons
            view = TicketControlView(self.cog)
            
            await channel.send(
                content=f"{user.mention} | Staff: {' '.join([f'<@&{r}>' for r in mod_role_ids + admin_role_ids])}",
                embed=embed,
                view=view
            )
            
            # Notify the user
            await interaction.followup.send(
                embed=EmbedBuilder.success_embed(
                    "Ticket Created!",
                    f"Your ticket has been created: {channel.mention}\n\n"
                    f"Please go to {channel.mention} to describe your issue."
                ),
                ephemeral=True
            )
            
            # Send notification to staff if there's a notification channel
            staff_channel_id = settings.get('mod_log_channel')
            if staff_channel_id:
                staff_channel = guild.get_channel(staff_channel_id)
                if staff_channel:
                    staff_embed = EmbedBuilder.create_embed(
                        title="🎫 New Ticket Created",
                        description=f"**User:** {user.mention}\n**Category:** {category}\n**Channel:** {channel.mention}",
                        color=Config.EMBED_COLORS['ticket']
                    )
                    await staff_channel.send(embed=staff_embed)
            
        except discord.Forbidden:
            await interaction.followup.send(
                embed=EmbedBuilder.error_embed(
                    "Permission Error",
                    "I don't have permission to create channels. Please contact an administrator."
                ),
                ephemeral=True
            )
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")
            await interaction.followup.send(
                embed=EmbedBuilder.error_embed(
                    "Error",
                    f"An error occurred while creating your ticket. Please try again later.\nError: {str(e)}"
                ),
                ephemeral=True
            )


class TicketControlView(discord.ui.View):
    """View for ticket control buttons."""
    
    def __init__(self, cog: Tickets):
        super().__init__(timeout=None)
        self.cog = cog
    
    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.danger,
        emoji="🔒",
        custom_id="close_ticket"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close the ticket."""
        
        # Check if user has permission
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed(
                    "Permission Denied",
                    "Only staff members can close tickets."
                ),
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        # Get ticket info
        ticket = await self.cog.db.get_ticket(interaction.guild_id, interaction.channel_id)
        
        if ticket:
            # Create transcript
            transcript = await self.cog._create_transcript(interaction.channel)
            
            # Update database
            await self.cog.db.update_ticket_status(
                interaction.guild_id,
                interaction.channel_id,
                'closed',
                interaction.user.id
            )
            
            # Send transcript to log
            settings = await self.cog.db.get_guild_settings(interaction.guild_id)
            log_channel_id = settings.get('ticket_log_channel')
            
            if log_channel_id and transcript:
                log_channel = interaction.guild.get_channel(log_channel_id)
                if log_channel:
                    embed = EmbedBuilder.create_embed(
                        title="📋 Ticket Closed",
                        color=Config.EMBED_COLORS['ticket'],
                        fields=[
                            {"name": "Channel", "value": interaction.channel.name, "inline": True},
                            {"name": "Category", "value": ticket.get('category', 'Unknown'), "inline": True},
                            {"name": "Created By", "value": f"<@{ticket.get('user_id')}>", "inline": True},
                            {"name": "Closed By", "value": interaction.user.mention, "inline": True},
                        ]
                    )
                    
                    file = discord.File(
                        io.StringIO(transcript),
                        filename=f"transcript-{interaction.channel.name}.txt"
                    )
                    
                    await log_channel.send(embed=embed, file=file)
        
        await interaction.followup.send(
            embed=EmbedBuilder.info_embed(
                "Ticket Closing",
                "This ticket will be closed in 5 seconds..."
            )
        )
        
        await asyncio.sleep(5)
        
        try:
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        except discord.Forbidden:
            pass
    
    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.primary,
        emoji="✋",
        custom_id="claim_ticket"
    )
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Claim the ticket."""
        
        if not interaction.user.guild_permissions.manage_channels:
            await interaction.response.send_message(
                embed=EmbedBuilder.error_embed(
                    "Permission Denied",
                    "Only staff members can claim tickets."
                ),
                ephemeral=True
            )
            return
        
        await interaction.response.send_message(
            embed=EmbedBuilder.success_embed(
                "Ticket Claimed",
                f"This ticket has been claimed by {interaction.user.mention}."
            )
        )
    
    @discord.ui.button(
        label="Transcript",
        style=discord.ButtonStyle.secondary,
        emoji="📝",
        custom_id="transcript_ticket"
    )
    async def save_transcript(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Save the ticket transcript."""
        
        await interaction.response.defer(ephemeral=True)
        
        transcript = await self.cog._create_transcript(interaction.channel)
        
        if transcript:
            file = discord.File(
                io.StringIO(transcript),
                filename=f"transcript-{interaction.channel.name}.txt"
            )
            
            await interaction.followup.send(
                content="Here's the current transcript:",
                file=file,
                ephemeral=True
            )


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Tickets(bot))