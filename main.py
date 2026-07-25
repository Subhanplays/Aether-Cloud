"""
Main entry point for the Discord Moderation Bot.
Initializes the bot, loads cogs, and handles startup/shutdown.
"""

import asyncio
import sys
from pathlib import Path

import discord
from discord.ext import commands

from config import Config, Constants
from database.manager import DatabaseManager
from utils.logger import logger


class ModerationBot(commands.Bot):
    """Main bot class with enhanced functionality."""
    
    def __init__(self):
        """Initialize the bot with required intents."""
        
        # Configure intents
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.presences = True
        intents.guilds = True
        intents.moderation = True
        
        super().__init__(
            command_prefix=Config.PREFIX,
            intents=intents,
            case_insensitive=True,
            help_command=None,  # Custom help command
            owner_ids=set(Config.OWNER_IDS),
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="over the server"
            ),
            status=discord.Status.online
        )
        
        self.db = DatabaseManager()
        self._startup_time = None
    
    async def setup_hook(self):
        """Async setup hook called before the bot starts."""
        
        # Initialize database
        try:
            await self.db.initialize()
            logger.info("Database initialized successfully")
        except Exception as e:
            logger.critical(f"Failed to initialize database: {e}")
            sys.exit(1)
        
        # Load all cogs
        await self._load_cogs()
        
        # Sync commands with Discord
        try:
            await self.tree.sync()
            logger.info("Command tree synced successfully")
        except Exception as e:
            logger.error(f"Failed to sync command tree: {e}")
    
    async def _load_cogs(self):
        """Dynamically load all cog modules."""
        cogs_dir = Path("cogs")
        
        if not cogs_dir.exists():
            logger.warning("Cogs directory not found")
            return
        
        loaded_cogs = []
        failed_cogs = []
        
        for cog_file in cogs_dir.glob("*.py"):
            if cog_file.name.startswith("__"):
                continue
            
            cog_name = f"cogs.{cog_file.stem}"
            
            try:
                await self.load_extension(cog_name)
                loaded_cogs.append(cog_name)
                logger.info(f"Loaded cog: {cog_name}")
            except Exception as e:
                failed_cogs.append((cog_name, str(e)))
                logger.error(f"Failed to load cog {cog_name}: {e}")
        
        if loaded_cogs:
            logger.info(f"Successfully loaded {len(loaded_cogs)} cogs")
        
        if failed_cogs:
            logger.warning(f"Failed to load {len(failed_cogs)} cogs")
    
    async def on_ready(self):
        """Called when the bot is ready and connected."""
        self._startup_time = discord.utils.utcnow()
        
        logger.info(f"Bot is ready: {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        logger.info(f"Serving {sum(g.member_count for g in self.guilds)} members")
    
    async def on_guild_join(self, guild: discord.Guild):
        """Called when the bot joins a new guild."""
        logger.info(f"Joined new guild: {guild.name} (ID: {guild.id})")
        
        # Create default settings for the new guild
        await self.db.get_guild_settings(guild.id)
    
    async def on_guild_remove(self, guild: discord.Guild):
        """Called when the bot leaves or is removed from a guild."""
        logger.info(f"Left guild: {guild.name} (ID: {guild.id})")
    
    async def on_command_error(
        self,
        ctx: commands.Context,
        error: commands.CommandError
    ):
        """Global error handler for command errors."""
        
        if isinstance(error, commands.CommandNotFound):
            return
        
        if isinstance(error, commands.MissingPermissions):
            embed = discord.Embed(
                title="❌ Missing Permissions",
                description=f"You need the following permissions: {', '.join(error.missing_permissions)}",
                color=Config.EMBED_COLORS['error']
            )
            await ctx.send(embed=embed, ephemeral=True)
            return
        
        if isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(
                title="❌ Bot Missing Permissions",
                description=f"I need the following permissions: {', '.join(error.missing_permissions)}",
                color=Config.EMBED_COLORS['error']
            )
            await ctx.send(embed=embed, ephemeral=True)
            return
        
        if isinstance(error, commands.CheckFailure):
            embed = discord.Embed(
                title="❌ Access Denied",
                description="You don't have permission to use this command.",
                color=Config.EMBED_COLORS['error']
            )
            await ctx.send(embed=embed, ephemeral=True)
            return
        
        if isinstance(error, commands.CommandOnCooldown):
            embed = discord.Embed(
                title="⏰ Command on Cooldown",
                description=f"Please wait {error.retry_after:.1f} seconds before using this command again.",
                color=Config.EMBED_COLORS['warning']
            )
            await ctx.send(embed=embed, ephemeral=True)
            return
        
        # Log unexpected errors
        logger.error(f"Unexpected error in command {ctx.command}: {error}")
        
        embed = discord.Embed(
            title="❌ Error",
            description="An unexpected error occurred. Please try again later.",
            color=Config.EMBED_COLORS['error']
        )
        await ctx.send(embed=embed, ephemeral=True)
    
    async def close(self):
        """Clean shutdown of the bot."""
        logger.info("Shutting down bot...")
        
        # Close database connection
        if self.db:
            await self.db.close()
        
        await super().close()


async def main():
    """Main entry point for the bot."""
    
    # Validate configuration
    try:
        Config.validate()
    except ValueError as e:
        logger.critical(f"Configuration error: {e}")
        sys.exit(1)
    
    # Create and run bot
    bot = ModerationBot()
    
    try:
        async with bot:
            await bot.start(Config.DISCORD_TOKEN)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot shutdown complete.")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)