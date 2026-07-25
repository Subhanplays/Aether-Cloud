"""
Verification system for new members.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
from datetime import datetime, timedelta

from utils.embeds import EmbedBuilder
from utils.checks import is_admin
from database.manager import DatabaseManager
from config import Config
from utils.logger import logger


class Verification(commands.Cog):
    """Verification system for member screening."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseManager()
    
    @app_commands.command(name="verify", description="Verify yourself in the server")
    async def verify(self, interaction: discord.Interaction):
        """Verify yourself as a legitimate member."""
        
        # Check if already verified
        is_verified = await self.db.is_verified(
            interaction.guild_id,
            interaction.user.id
        )
        
        if is_verified:
            embed = EmbedBuilder.info_embed(
                "Already Verified",
                "You are already verified in this server."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Check account age
        settings = await self.db.get_guild_settings(interaction.guild_id)
        min_age = settings.get('min_account_age', Config.MIN_ACCOUNT_AGE)
        
        account_age = (datetime.utcnow() - interaction.user.created_at).total_seconds()
        
        if account_age < min_age:
            days_required = int(min_age / 86400)
            days_old = int(account_age / 86400)
            
            embed = EmbedBuilder.error_embed(
                "Account Too New",
                f"Your account must be at least {days_required} days old to verify.\n"
                f"Your account is {days_old} days old.\n\n"
                f"Please try again later."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Mark as verified
        await self.db.set_verified(interaction.guild_id, interaction.user.id)
        
        # Assign verification role
        verification_role_id = settings.get('verification_role_id')
        if verification_role_id:
            role = interaction.guild.get_role(verification_role_id)
            if role:
                try:
                    await interaction.user.add_roles(
                        role,
                        reason="Member verified"
                    )
                except discord.Forbidden:
                    pass
        
        embed = EmbedBuilder.success_embed(
            "✅ Verified!",
            "You have been successfully verified and now have full access to the server!"
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="verificationpanel", description="Create a verification panel")
    @app_commands.describe(channel="Channel to send the verification panel")
    @is_admin()
    async def verification_panel(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel
    ):
        """Create a verification panel with button."""
        
        embed = EmbedBuilder.create_embed(
            title="✅ Server Verification",
            description=(
                "Welcome to the server! To gain full access, please verify yourself.\n\n"
                "**Requirements:**\n"
                "• Account must be at least 7 days old\n"
                "• Click the button below to verify\n\n"
                "This helps us keep the server safe from bots and spam accounts."
            ),
            color=Config.EMBED_COLORS['success']
        )
        
        class VerifyButton(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=None)
            
            @discord.ui.button(
                label="Verify Me",
                style=discord.ButtonStyle.success,
                emoji="✅",
                custom_id="verify_button"
            )
            async def verify_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                # Run the verify command
                verify_cog = button_interaction.client.get_cog("Verification")
                if verify_cog:
                    await verify_cog.verify(button_interaction)
        
        await channel.send(embed=embed, view=VerifyButton())
        
        embed = EmbedBuilder.success_embed(
            "Panel Created",
            f"Verification panel has been created in {channel.mention}"
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="verificationconfig", description="Configure verification settings")
    @app_commands.describe(
        enabled="Enable or disable verification",
        role="Role to assign upon verification",
        min_age_days="Minimum account age in days"
    )
    @is_admin()
    async def verification_config(
        self,
        interaction: discord.Interaction,
        enabled: Optional[bool] = None,
        role: Optional[discord.Role] = None,
        min_age_days: Optional[int] = None
    ):
        """Configure verification system."""
        
        updates = []
        
        if enabled is not None:
            await self.db.update_guild_setting(
                interaction.guild_id,
                'verification_enabled',
                enabled
            )
            updates.append(f"Verification: {'Enabled' if enabled else 'Disabled'}")
        
        if role:
            await self.db.update_guild_setting(
                interaction.guild_id,
                'verification_role_id',
                role.id
            )
            updates.append(f"Verification role: {role.mention}")
        
        if min_age_days is not None:
            seconds = min_age_days * 86400
            await self.db.update_guild_setting(
                interaction.guild_id,
                'min_account_age',
                seconds
            )
            updates.append(f"Minimum account age: {min_age_days} days")
        
        if updates:
            embed = EmbedBuilder.success_embed(
                "Verification Settings Updated",
                "\n".join(updates)
            )
        else:
            embed = EmbedBuilder.error_embed(
                "No Changes",
                "Please specify at least one setting to change."
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="verifyuser", description="Manually verify a user")
    @app_commands.describe(member="The member to verify")
    @is_moderator()
    async def verify_user(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):
        """Manually verify a member."""
        
        await self.db.set_verified(interaction.guild_id, member.id)
        
        # Assign verification role
        settings = await self.db.get_guild_settings(interaction.guild_id)
        verification_role_id = settings.get('verification_role_id')
        
        if verification_role_id:
            role = interaction.guild.get_role(verification_role_id)
            if role:
                try:
                    await member.add_roles(role, reason=f"Manually verified by {interaction.user}")
                except discord.Forbidden:
                    pass
        
        embed = EmbedBuilder.success_embed(
            "User Verified",
            f"{member.mention} has been manually verified."
        )
        
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Verification(bot))