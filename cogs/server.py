"""
Server management and configuration commands.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List
import json
import io

from utils.embeds import EmbedBuilder
from utils.checks import is_admin, is_owner
from database.manager import DatabaseManager
from config import Config
from utils.logger import logger


class Server(commands.Cog):
    """Server management and configuration."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseManager()
    
    @app_commands.command(name="serverstats", description="View server statistics")
    @is_admin()
    async def serverstats(self, interaction: discord.Interaction):
        """View detailed server statistics."""
        
        guild = interaction.guild
        
        # Get statistics
        total_members = guild.member_count
        humans = len([m for m in guild.members if not m.bot])
        bots = total_members - humans
        online = len([m for m in guild.members if m.status != discord.Status.offline])
        
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        total_roles = len(guild.roles)
        total_emojis = len(guild.emojis)
        
        embed = EmbedBuilder.create_embed(
            title=f"📊 Server Statistics - {guild.name}",
            color=Config.EMBED_COLORS['info'],
            thumbnail=guild.icon.url if guild.icon else None,
            fields=[
                {"name": "📈 Members", "value": f"Total: {total_members}\nHumans: {humans}\nBots: {bots}\nOnline: {online}", "inline": True},
                {"name": "💬 Channels", "value": f"Text: {text_channels}\nVoice: {voice_channels}\nCategories: {categories}", "inline": True},
                {"name": "👑 Roles", "value": str(total_roles), "inline": True},
                {"name": "😀 Emojis", "value": f"{total_emojis}/{guild.emoji_limit}", "inline": True},
                {"name": "🚀 Boost Level", "value": f"Level {guild.premium_tier}", "inline": True},
                {"name": "💎 Boost Count", "value": str(guild.premium_subscription_count), "inline": True},
                {"name": "📅 Created", "value": discord.utils.format_dt(guild.created_at, 'R'), "inline": True},
                {"name": "👑 Owner", "value": guild.owner.mention, "inline": True},
            ]
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="settings", description="View server configuration")
    @is_admin()
    async def settings(self, interaction: discord.Interaction):
        """View current server settings."""
        
        settings = await self.db.get_guild_settings(interaction.guild_id)
        
        # Create a formatted view of settings
        embed = EmbedBuilder.create_embed(
            title=f"⚙️ Server Settings - {interaction.guild.name}",
            color=Config.EMBED_COLORS['info'],
            fields=[
                {
                    "name": "🛡️ Anti-Raid",
                    "value": f"Enabled: {settings.get('anti_raid_enabled', False)}",
                    "inline": True
                },
                {
                    "name": "🛡️ Anti-Nuke",
                    "value": f"Enabled: {settings.get('anti_nuke_enabled', False)}",
                    "inline": True
                },
                {
                    "name": "🤖 Auto-Mod",
                    "value": f"Enabled: {settings.get('auto_mod_enabled', False)}",
                    "inline": True
                },
                {
                    "name": "👋 Welcome",
                    "value": f"Enabled: {settings.get('welcome_enabled', False)}",
                    "inline": True
                },
                {
                    "name": "👋 Goodbye",
                    "value": f"Enabled: {settings.get('goodbye_enabled', False)}",
                    "inline": True
                },
                {
                    "name": "✅ Verification",
                    "value": f"Enabled: {settings.get('verification_enabled', False)}",
                    "inline": True
                },
            ]
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="backup", description="Create a server backup")
    @is_admin()
    async def backup(self, interaction: discord.Interaction):
        """Create a backup of server configuration."""
        
        guild = interaction.guild
        
        # Collect backup data
        backup_data = {
            'name': guild.name,
            'roles': [],
            'channels': [],
            'settings': await self.db.get_guild_settings(guild.id)
        }
        
        # Backup roles
        for role in guild.roles:
            if not role.managed:
                backup_data['roles'].append({
                    'name': role.name,
                    'color': role.color.value,
                    'hoist': role.hoist,
                    'mentionable': role.mentionable,
                    'position': role.position,
                    'permissions': role.permissions.value
                })
        
        # Backup channels
        for channel in guild.channels:
            backup_data['channels'].append({
                'name': channel.name,
                'type': str(channel.type),
                'position': channel.position,
                'category': channel.category.name if channel.category else None
            })
        
        # Save to database
        await self.db.save_backup(guild.id, backup_data)
        
        # Also provide as JSON file
        json_str = json.dumps(backup_data, indent=2, default=str)
        file = discord.File(
            io.StringIO(json_str),
            filename=f"backup_{guild.id}_{discord.utils.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        embed = EmbedBuilder.success_embed(
            "Backup Created",
            "Server configuration has been backed up successfully."
        )
        
        await interaction.response.send_message(embed=embed, file=file)
    
    @app_commands.command(name="restore", description="Restore a server backup")
    @is_admin()
    async def restore(self, interaction: discord.Interaction):
        """Restore server from backup."""
        
        backup = await self.db.get_latest_backup(interaction.guild_id)
        
        if not backup:
            embed = EmbedBuilder.error_embed(
                "No Backup Found",
                "There are no backups available to restore."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        embed = EmbedBuilder.warning_embed(
            "Restore Backup",
            f"Are you sure you want to restore the backup from "
            f"{discord.utils.format_dt(backup['created_at'], 'R')}?\n\n"
            f"This will restore server settings only."
        )
        
        # Confirmation buttons
        class ConfirmRestore(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=30)
                self.value = None
            
            @discord.ui.button(label="Restore", style=discord.ButtonStyle.danger)
            async def confirm(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.value = True
                self.stop()
            
            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
            async def cancel(self, button_interaction: discord.Interaction, button: discord.ui.Button):
                self.value = False
                self.stop()
        
        view = ConfirmRestore()
        await interaction.response.send_message(embed=embed, view=view)
        
        await view.wait()
        
        if view.value:
            # Restore settings
            backup_data = backup.get('data', {})
            settings = backup_data.get('settings', {})
            
            for key, value in settings.items():
                if key not in ['_id', 'guild_id', 'created_at']:
                    await self.db.update_guild_setting(
                        interaction.guild_id, key, value
                    )
            
            await interaction.edit_original_response(
                embed=EmbedBuilder.success_embed(
                    "Settings Restored",
                    "Server settings have been restored from backup."
                ),
                view=None
            )
        else:
            await interaction.edit_original_response(
                embed=EmbedBuilder.info_embed(
                    "Cancelled",
                    "Backup restore cancelled."
                ),
                view=None
            )
    
    @app_commands.command(name="exportconfig", description="Export server configuration")
    @is_admin()
    async def export_config(self, interaction: discord.Interaction):
        """Export server configuration as JSON."""
        
        settings = await self.db.get_guild_settings(interaction.guild_id)
        
        # Remove internal fields
        settings.pop('_id', None)
        settings.pop('guild_id', None)
        
        json_str = json.dumps(settings, indent=2, default=str)
        file = discord.File(
            io.StringIO(json_str),
            filename=f"config_{interaction.guild_id}.json"
        )
        
        embed = EmbedBuilder.success_embed(
            "Configuration Exported",
            "Server configuration has been exported."
        )
        
        await interaction.response.send_message(embed=embed, file=file)


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Server(bot))