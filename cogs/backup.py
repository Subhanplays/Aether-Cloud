"""
Server backup, sync, and restore system.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import json
import io
import asyncio
from datetime import datetime

from utils.embeds import EmbedBuilder
from utils.checks import is_admin, is_owner
from database.manager import DatabaseManager
from config import Config
from utils.logger import logger


class Backup(commands.Cog):
    """Backup and restore system for server configurations."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseManager()
    
    @app_commands.command(name="fullbackup", description="Create a full server backup")
    @is_admin()
    async def full_backup(self, interaction: discord.Interaction):
        """Create a complete backup of the server."""
        
        await interaction.response.defer(ephemeral=True)
        
        guild = interaction.guild
        
        backup_data = {
            'name': guild.name,
            'id': guild.id,
            'backup_date': datetime.utcnow().isoformat(),
            'backup_by': str(interaction.user),
            'roles': [],
            'channels': [],
            'categories': [],
            'settings': {},
            'emojis': [],
        }
        
        # Backup roles
        for role in reversed(guild.roles):
            if not role.managed and role.name != '@everyone':
                backup_data['roles'].append({
                    'name': role.name,
                    'color': role.color.value,
                    'hoist': role.hoist,
                    'mentionable': role.mentionable,
                    'position': role.position,
                    'permissions': role.permissions.value
                })
        
        # Backup categories
        for category in guild.categories:
            backup_data['categories'].append({
                'name': category.name,
                'position': category.position,
                'overwrites': self._serialize_overwrites(category.overwrites)
            })
        
        # Backup channels
        for channel in guild.channels:
            channel_data = {
                'name': channel.name,
                'type': str(channel.type),
                'position': channel.position,
                'category': channel.category.name if channel.category else None,
                'topic': getattr(channel, 'topic', None),
                'slowmode_delay': getattr(channel, 'slowmode_delay', 0),
                'nsfw': getattr(channel, 'nsfw', False),
                'overwrites': self._serialize_overwrites(channel.overwrites)
            }
            backup_data['channels'].append(channel_data)
        
        # Backup emojis
        for emoji in guild.emojis:
            backup_data['emojis'].append({
                'name': emoji.name,
                'animated': emoji.animated,
                'url': str(emoji.url)
            })
        
        # Backup settings
        backup_data['settings'] = await self.db.get_guild_settings(guild.id)
        
        # Save to database
        await self.db.save_backup(guild.id, backup_data)
        
        # Create JSON file
        json_str = json.dumps(backup_data, indent=2, default=str)
        file = discord.File(
            io.StringIO(json_str),
            filename=f"full_backup_{guild.name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        )
        
        embed = EmbedBuilder.success_embed(
            "✅ Full Backup Created",
            f"**Server:** {guild.name}\n"
            f"**Roles:** {len(backup_data['roles'])}\n"
            f"**Channels:** {len(backup_data['channels'])}\n"
            f"**Categories:** {len(backup_data['categories'])}\n"
            f"**Emojis:** {len(backup_data['emojis'])}\n\n"
            f"Backup file is attached below."
        )
        
        await interaction.followup.send(
            embed=embed,
            file=file,
            ephemeral=True
        )
    
    def _serialize_overwrites(self, overwrites) -> list:
        """Serialize permission overwrites."""
        result = []
        for target, overwrite in overwrites.items():
            if isinstance(target, discord.Role):
                result.append({
                    'type': 'role',
                    'id': target.id,
                    'name': target.name,
                    'allow': overwrite.pair()[0].value,
                    'deny': overwrite.pair()[1].value
                })
            elif isinstance(target, discord.Member):
                result.append({
                    'type': 'member',
                    'id': target.id,
                    'name': str(target),
                    'allow': overwrite.pair()[0].value,
                    'deny': overwrite.pair()[1].value
                })
        return result
    
    @app_commands.command(name="backuproles", description="Backup only server roles")
    @is_admin()
    async def backup_roles(self, interaction: discord.Interaction):
        """Create a backup of server roles."""
        
        guild = interaction.guild
        
        roles_data = []
        for role in reversed(guild.roles):
            if not role.managed and role.name != '@everyone':
                roles_data.append({
                    'name': role.name,
                    'color': role.color.value,
                    'hoist': role.hoist,
                    'mentionable': role.mentionable,
                    'position': role.position,
                    'permissions': role.permissions.value
                })
        
        json_str = json.dumps(roles_data, indent=2)
        file = discord.File(
            io.StringIO(json_str),
            filename=f"roles_backup_{guild.name}_{datetime.utcnow().strftime('%Y%m%d')}.json"
        )
        
        embed = EmbedBuilder.success_embed(
            "👑 Roles Backup",
            f"Backed up {len(roles_data)} roles."
        )
        
        await interaction.response.send_message(
            embed=embed,
            file=file,
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Backup(bot))