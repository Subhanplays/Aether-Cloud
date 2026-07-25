"""
Owner-only commands for bot management and control.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List
import sys
import os
import asyncio

from utils.embeds import EmbedBuilder
from utils.checks import is_owner
from database.manager import DatabaseManager
from config import Config
from utils.logger import logger


class Owner(commands.Cog):
    """Owner-only bot management commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseManager()
    
    @app_commands.command(name="reload", description="Reload a cog")
    @app_commands.describe(cog="The cog to reload")
    @is_owner()
    async def reload(self, interaction: discord.Interaction, cog: str):
        """Reload a specific cog."""
        
        try:
            cog_path = f"cogs.{cog}"
            await self.bot.reload_extension(cog_path)
            
            embed = EmbedBuilder.success_embed(
                "Cog Reloaded",
                f"Successfully reloaded `{cog}` cog."
            )
            
        except commands.ExtensionNotLoaded:
            try:
                await self.bot.load_extension(cog_path)
                embed = EmbedBuilder.success_embed(
                    "Cog Loaded",
                    f"Successfully loaded `{cog}` cog."
                )
            except Exception as e:
                embed = EmbedBuilder.error_embed(
                    "Failed to Load",
                    f"Error: {str(e)}"
                )
        except commands.ExtensionNotFound:
            embed = EmbedBuilder.error_embed(
                "Cog Not Found",
                f"Cog `{cog}` not found."
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Error",
                f"Failed to reload: {str(e)}"
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="unload", description="Unload a cog")
    @app_commands.describe(cog="The cog to unload")
    @is_owner()
    async def unload(self, interaction: discord.Interaction, cog: str):
        """Unload a specific cog."""
        
        try:
            await self.bot.unload_extension(f"cogs.{cog}")
            embed = EmbedBuilder.success_embed(
                "Cog Unloaded",
                f"Successfully unloaded `{cog}` cog."
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Error",
                f"Failed to unload: {str(e)}"
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="load", description="Load a cog")
    @app_commands.describe(cog="The cog to load")
    @is_owner()
    async def load(self, interaction: discord.Interaction, cog: str):
        """Load a specific cog."""
        
        try:
            await self.bot.load_extension(f"cogs.{cog}")
            embed = EmbedBuilder.success_embed(
                "Cog Loaded",
                f"Successfully loaded `{cog}` cog."
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Error",
                f"Failed to load: {str(e)}"
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="cogs", description="List all loaded cogs")
    @is_owner()
    async def cogs_list(self, interaction: discord.Interaction):
        """List all loaded cogs."""
        
        cogs = list(self.bot.cogs.keys())
        
        if not cogs:
            embed = EmbedBuilder.info_embed(
                "No Cogs",
                "No cogs are currently loaded."
            )
        else:
            embed = EmbedBuilder.create_embed(
                title="📦 Loaded Cogs",
                description="\n".join([f"• {cog}" for cog in cogs]),
                color=Config.EMBED_COLORS['info']
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="shutdown", description="Shutdown the bot")
    @is_owner()
    async def shutdown(self, interaction: discord.Interaction):
        """Shutdown the bot."""
        
        embed = EmbedBuilder.warning_embed(
            "Shutting Down",
            "Bot is shutting down..."
        )
        
        await interaction.response.send_message(embed=embed)
        logger.info(f"Bot shutdown initiated by {interaction.user}")
        
        await self.bot.close()
    
    @app_commands.command(name="restart", description="Restart the bot")
    @is_owner()
    async def restart(self, interaction: discord.Interaction):
        """Restart the bot."""
        
        embed = EmbedBuilder.warning_embed(
            "Restarting",
            "Bot is restarting..."
        )
        
        await interaction.response.send_message(embed=embed)
        logger.info(f"Bot restart initiated by {interaction.user}")
        
        # Restart by spawning a new process
        os.execv(sys.executable, ['python'] + sys.argv)
    
    @app_commands.command(name="sync", description="Sync slash commands")
    @is_owner()
    async def sync(self, interaction: discord.Interaction):
        """Sync slash commands with Discord."""
        
        await interaction.response.defer(ephemeral=True)
        
        try:
            synced = await self.bot.tree.sync()
            
            embed = EmbedBuilder.success_embed(
                "Commands Synced",
                f"Successfully synced {len(synced)} commands."
            )
            
            logger.info(f"Synced {len(synced)} commands")
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Sync Failed",
                f"Error: {str(e)}"
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="guilds", description="List all guilds the bot is in")
    @is_owner()
    async def guilds_list(self, interaction: discord.Interaction):
        """List all guilds the bot is connected to."""
        
        guilds = self.bot.guilds
        
        if not guilds:
            embed = EmbedBuilder.info_embed("No Guilds", "Bot is not in any guilds.")
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Split guilds into chunks of 10
        guild_list = [
            f"**{guild.name}** (ID: {guild.id})\n"
            f"Members: {guild.member_count} | Owner: {guild.owner}\n"
            for guild in guilds[:20]
        ]
        
        embed = EmbedBuilder.create_embed(
            title=f"🌐 Bot Guilds ({len(guilds)})",
            description="\n".join(guild_list),
            color=Config.EMBED_COLORS['info'],
            footer=f"Showing {min(20, len(guilds))} of {len(guilds)} guilds"
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="eval", description="Evaluate Python code")
    @app_commands.describe(code="Python code to evaluate")
    @is_owner()
    async def eval_code(self, interaction: discord.Interaction, code: str):
        """Evaluate Python code (owner only)."""
        
        # Remove code blocks if present
        if code.startswith('```') and code.endswith('```'):
            code = code[3:-3]
        if code.startswith('python'):
            code = code[6:]
        
        try:
            # Create evaluation environment
            env = {
                'bot': self.bot,
                'interaction': interaction,
                'guild': interaction.guild,
                'channel': interaction.channel,
                'author': interaction.user,
                'discord': discord,
                'db': self.db
            }
            
            # Execute the code
            result = eval(code, env)
            
            if result is not None:
                embed = EmbedBuilder.success_embed(
                    "Eval Result",
                    f"```py\n{result}\n```"
                )
            else:
                embed = EmbedBuilder.success_embed(
                    "Eval Complete",
                    "Code executed successfully (no output)."
                )
            
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Eval Error",
                f"```py\n{type(e).__name__}: {str(e)}\n```"
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="leaveguild", description="Leave a guild")
    @app_commands.describe(guild_id="ID of the guild to leave")
    @is_owner()
    async def leave_guild(self, interaction: discord.Interaction, guild_id: str):
        """Force the bot to leave a guild."""
        
        try:
            guild = self.bot.get_guild(int(guild_id))
            
            if not guild:
                embed = EmbedBuilder.error_embed(
                    "Guild Not Found",
                    "I'm not in a guild with that ID."
                )
            else:
                guild_name = guild.name
                await guild.leave()
                embed = EmbedBuilder.success_embed(
                    "Left Guild",
                    f"Successfully left **{guild_name}** (ID: {guild_id})."
                )
        except ValueError:
            embed = EmbedBuilder.error_embed(
                "Invalid ID",
                "Please provide a valid guild ID."
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Error",
                f"Failed to leave guild: {str(e)}"
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="announce", description="Send announcement to all guilds")
    @app_commands.describe(message="Announcement message")
    @is_owner()
    async def announce(self, interaction: discord.Interaction, message: str):
        """Send an announcement to all guilds the bot is in."""
        
        await interaction.response.defer(ephemeral=True)
        
        success = 0
        failed = 0
        
        for guild in self.bot.guilds:
            # Find a suitable channel
            channel = None
            
            # Try system channel first
            if guild.system_channel:
                channel = guild.system_channel
            else:
                # Find first text channel with send permissions
                for ch in guild.text_channels:
                    if ch.permissions_for(guild.me).send_messages:
                        channel = ch
                        break
            
            if channel:
                try:
                    embed = EmbedBuilder.info_embed(
                        "📢 Bot Announcement",
                        message
                    )
                    await channel.send(embed=embed)
                    success += 1
                except discord.Forbidden:
                    failed += 1
        
        embed = EmbedBuilder.success_embed(
            "Announcement Sent",
            f"Sent to {success} guilds. Failed: {failed} guilds."
        )
        
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Owner(bot))