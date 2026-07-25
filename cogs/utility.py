"""
Utility commands for the bot.
Provides information commands and helpful utilities.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional
import platform
import psutil

from utils.embeds import EmbedBuilder
from config import Config
from database.manager import DatabaseManager


class Utility(commands.Cog):
    """Utility and information commands."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseManager()
    
    @app_commands.command(name="userinfo", description="Get information about a user")
    @app_commands.describe(member="The member to get info about")
    async def userinfo(
        self,
        interaction: discord.Interaction,
        member: Optional[discord.Member] = None
    ):
        """Get detailed information about a member."""
        
        member = member or interaction.user
        
        embed = EmbedBuilder.user_info_embed(member)
        
        # Add additional fields
        embed.add_field(
            name="Status",
            value=str(member.status).title(),
            inline=True
        )
        
        if member.activity:
            activity_type = member.activity.type.name.title()
            embed.add_field(
                name=f"{activity_type}",
                value=member.activity.name,
                inline=True
            )
        
        embed.add_field(
            name="Bot",
            value="Yes" if member.bot else "No",
            inline=True
        )
        
        # Get warning count
        warnings = await self.db.get_warnings(interaction.guild_id, member.id)
        if warnings:
            embed.add_field(
                name="Warnings",
                value=f"{len(warnings)} warning(s)",
                inline=True
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="serverinfo", description="Get information about the server")
    async def serverinfo(self, interaction: discord.Interaction):
        """Get detailed information about the server."""
        
        guild = interaction.guild
        
        # Count members
        total_members = guild.member_count
        humans = len([m for m in guild.members if not m.bot])
        bots = total_members - humans
        
        # Count channels
        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        
        # Server features
        features = "\n".join([f"• {f.replace('_', ' ').title()}" for f in guild.features]) or "None"
        
        embed = EmbedBuilder.create_embed(
            title=f"📊 {guild.name} Server Information",
            color=Config.EMBED_COLORS['info'],
            thumbnail=guild.icon.url if guild.icon else None,
            fields=[
                {"name": "Server ID", "value": guild.id, "inline": True},
                {"name": "Owner", "value": guild.owner.mention, "inline": True},
                {
                    "name": "Created",
                    "value": discord.utils.format_dt(guild.created_at, 'R'),
                    "inline": True
                },
                {"name": "Members", "value": f"👤 {humans}\n🤖 {bots}\n**Total:** {total_members}", "inline": True},
                {
                    "name": "Channels",
                    "value": f"💬 Text: {text_channels}\n🔊 Voice: {voice_channels}\n📁 Categories: {categories}",
                    "inline": True
                },
                {"name": "Roles", "value": len(guild.roles), "inline": True},
                {"name": "Emojis", "value": len(guild.emojis), "inline": True},
                {"name": "Boost Level", "value": f"Level {guild.premium_tier}", "inline": True},
                {"name": "Boost Count", "value": guild.premium_subscription_count, "inline": True},
                {"name": "Verification Level", "value": str(guild.verification_level).title(), "inline": True},
                {"name": "Features", "value": features[:1024], "inline": False},
            ]
        )
        
        if guild.banner:
            embed.set_image(url=guild.banner.url)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="roleinfo", description="Get information about a role")
    @app_commands.describe(role="The role to get info about")
    async def roleinfo(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        """Get detailed information about a role."""
        
        embed = EmbedBuilder.create_embed(
            title=f"👑 Role Information - {role.name}",
            color=role.color if role.color.value else Config.EMBED_COLORS['info'],
            fields=[
                {"name": "Role ID", "value": role.id, "inline": True},
                {"name": "Color", "value": f"#{role.color.value:06x}" if role.color.value else "None", "inline": True},
                {"name": "Position", "value": role.position, "inline": True},
                {"name": "Members", "value": len(role.members), "inline": True},
                {"name": "Mentionable", "value": "Yes" if role.mentionable else "No", "inline": True},
                {"name": "Hoisted", "value": "Yes" if role.hoist else "No", "inline": True},
                {"name": "Managed", "value": "Yes" if role.managed else "No", "inline": True},
                {
                    "name": "Created",
                    "value": discord.utils.format_dt(role.created_at, 'R'),
                    "inline": True
                },
            ]
        )
        
        # Add permissions if they're not too many
        permissions = [perm.replace('_', ' ').title() for perm, value in role.permissions if value]
        if permissions:
            perm_text = ", ".join(permissions[:10])
            if len(permissions) > 10:
                perm_text += f"\n*...and {len(permissions) - 10} more*"
            embed.add_field(name="Key Permissions", value=perm_text, inline=False)
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="channelinfo", description="Get information about a channel")
    @app_commands.describe(channel="The channel to get info about")
    async def channelinfo(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None
    ):
        """Get detailed information about a channel."""
        
        channel = channel or interaction.channel
        
        embed = EmbedBuilder.create_embed(
            title=f"💬 Channel Information - #{channel.name}",
            color=Config.EMBED_COLORS['info'],
            fields=[
                {"name": "Channel ID", "value": channel.id, "inline": True},
                {"name": "Type", "value": str(channel.type).title(), "inline": True},
                {"name": "Position", "value": channel.position, "inline": True},
                {
                    "name": "Created",
                    "value": discord.utils.format_dt(channel.created_at, 'R'),
                    "inline": True
                },
                {"name": "Category", "value": channel.category.name if channel.category else "None", "inline": True},
                {"name": "Slowmode", "value": f"{channel.slowmode_delay}s" if channel.slowmode_delay else "Off", "inline": True},
                {"name": "NSFW", "value": "Yes" if channel.nsfw else "No", "inline": True},
                {"name": "Topic", "value": channel.topic or "None", "inline": False},
            ]
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="avatar", description="Get a user's avatar")
    @app_commands.describe(member="The member to get the avatar of")
    async def avatar(
        self,
        interaction: discord.Interaction,
        member: Optional[discord.Member] = None
    ):
        """Get a user's avatar in different sizes."""
        
        member = member or interaction.user
        
        embed = EmbedBuilder.create_embed(
            title=f"🖼️ Avatar - {member.display_name}",
            color=Config.EMBED_COLORS['default'],
            image=member.display_avatar.url,
            fields=[
                {
                    "name": "Links",
                    "value": f"[128px]({member.display_avatar.with_size(128).url}) | "
                            f"[256px]({member.display_avatar.with_size(256).url}) | "
                            f"[512px]({member.display_avatar.with_size(512).url}) | "
                            f"[1024px]({member.display_avatar.with_size(1024).url})",
                    "inline": False
                }
            ]
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="botinfo", description="Get information about the bot")
    async def botinfo(self, interaction: discord.Interaction):
        """Get detailed information about the bot."""
        
        # Calculate uptime
        uptime = discord.utils.utcnow() - self.bot._startup_time
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        
        uptime_str = f"{days}d {hours}h {minutes}m {seconds}s"
        
        # System stats
        cpu_usage = psutil.cpu_percent()
        memory = psutil.virtual_memory()
        memory_usage = memory.percent
        
        embed = EmbedBuilder.create_embed(
            title="🤖 Bot Information",
            color=Config.EMBED_COLORS['info'],
            thumbnail=self.bot.user.display_avatar.url,
            fields=[
                {"name": "Bot Name", "value": str(self.bot.user), "inline": True},
                {"name": "Bot ID", "value": self.bot.user.id, "inline": True},
                {"name": "Developer", "value": "Your Name", "inline": True},
                {"name": "Python Version", "value": platform.python_version(), "inline": True},
                {"name": "discord.py Version", "value": discord.__version__, "inline": True},
                {"name": "Uptime", "value": uptime_str, "inline": True},
                {"name": "Servers", "value": len(self.bot.guilds), "inline": True},
                {"name": "Users", "value": sum(g.member_count for g in self.bot.guilds), "inline": True},
                {"name": "Commands", "value": len(self.bot.tree.get_commands()), "inline": True},
                {"name": "CPU Usage", "value": f"{cpu_usage}%", "inline": True},
                {"name": "Memory Usage", "value": f"{memory_usage}%", "inline": True},
                {"name": "Latency", "value": f"{round(self.bot.latency * 1000)}ms", "inline": True},
            ]
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: discord.Interaction):
        """Check bot latency."""
        
        # Calculate latency
        ws_latency = round(self.bot.latency * 1000)
        
        embed = EmbedBuilder.create_embed(
            title="🏓 Pong!",
            color=Config.EMBED_COLORS['success'] if ws_latency < 200 else Config.EMBED_COLORS['warning'],
            fields=[
                {"name": "WebSocket Latency", "value": f"{ws_latency}ms", "inline": True},
            ]
        )
        
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Utility(bot))