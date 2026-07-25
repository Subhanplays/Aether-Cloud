"""
Role management system with self-assignable roles and reaction roles.
"""

import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional, List
from datetime import datetime, timedelta

from utils.embeds import EmbedBuilder
from utils.checks import is_admin, is_moderator
from database.manager import DatabaseManager
from config import Config
from utils.logger import logger


class Roles(commands.Cog):
    """Role management commands and features."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseManager()
        self.temp_roles = {}
    
    @app_commands.command(name="role", description="Add or remove a role from a member")
    @app_commands.describe(
        member="The member to manage",
        role="The role to add/remove",
        action="Add or remove the role"
    )
    @is_moderator()
    async def role(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
        action: str
    ):
        """Add or remove a role from a member."""
        
        # Check role hierarchy
        if role >= interaction.user.top_role and not interaction.user.guild_permissions.administrator:
            embed = EmbedBuilder.error_embed(
                "Permission Denied",
                "You cannot manage this role due to hierarchy."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if action.lower() == 'add':
            if role in member.roles:
                embed = EmbedBuilder.error_embed(
                    "Already Has Role",
                    f"{member.mention} already has {role.mention}."
                )
            else:
                try:
                    await member.add_roles(role, reason=f"Role added by {interaction.user}")
                    embed = EmbedBuilder.success_embed(
                        "Role Added",
                        f"Added {role.mention} to {member.mention}."
                    )
                except discord.Forbidden:
                    embed = EmbedBuilder.error_embed(
                        "Permission Denied",
                        "I don't have permission to add this role."
                    )
        
        elif action.lower() == 'remove':
            if role not in member.roles:
                embed = EmbedBuilder.error_embed(
                    "Doesn't Have Role",
                    f"{member.mention} doesn't have {role.mention}."
                )
            else:
                try:
                    await member.remove_roles(role, reason=f"Role removed by {interaction.user}")
                    embed = EmbedBuilder.success_embed(
                        "Role Removed",
                        f"Removed {role.mention} from {member.mention}."
                    )
                except discord.Forbidden:
                    embed = EmbedBuilder.error_embed(
                        "Permission Denied",
                        "I don't have permission to remove this role."
                    )
        else:
            embed = EmbedBuilder.error_embed(
                "Invalid Action",
                "Use 'add' or 'remove'."
            )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="temprole", description="Temporarily assign a role")
    @app_commands.describe(
        member="The member to assign the role to",
        role="The role to assign",
        duration="Duration (e.g., 1h, 30m, 1d)",
        reason="Reason for the temporary role"
    )
    @is_moderator()
    async def temprole(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        role: discord.Role,
        duration: str,
        reason: str = "No reason provided"
    ):
        """Temporarily assign a role to a member."""
        
        from utils.helpers import parse_duration, format_duration
        
        seconds = parse_duration(duration)
        if not seconds:
            embed = EmbedBuilder.error_embed(
                "Invalid Duration",
                "Please use a valid duration format (e.g., 1h, 30m, 1d)."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            await member.add_roles(role, reason=f"Temp role by {interaction.user}: {reason}")
            
            # Schedule role removal
            self.bot.loop.create_task(
                self._remove_role_after(member, role, seconds)
            )
            
            duration_str = format_duration(seconds)
            embed = EmbedBuilder.success_embed(
                "Temporary Role Assigned",
                f"Added {role.mention} to {member.mention} for {duration_str}.\n"
                f"**Reason:** {reason}"
            )
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            embed = EmbedBuilder.error_embed(
                "Permission Denied",
                "I don't have permission to manage this role."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def _remove_role_after(
        self,
        member: discord.Member,
        role: discord.Role,
        delay: int
    ):
        """Remove a role after a delay."""
        await asyncio.sleep(delay)
        
        try:
            if role in member.roles:
                await member.remove_roles(role, reason="Temporary role expired")
                
                # Notify member
                try:
                    embed = EmbedBuilder.info_embed(
                        "Role Expired",
                        f"Your temporary role {role.name} in {member.guild.name} has expired."
                    )
                    await member.send(embed=embed)
                except discord.Forbidden:
                    pass
        except discord.Forbidden:
            pass
    
    @app_commands.command(name="massrole", description="Mass add or remove a role")
    @app_commands.describe(
        role="The role to manage",
        action="Add or remove the role",
        members="List of members (mention or ID separated by spaces)"
    )
    @is_admin()
    async def massrole(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        action: str,
        members: str
    ):
        """Mass add or remove a role from multiple members."""
        
        await interaction.response.defer()
        
        # Parse members
        member_list = []
        for item in members.split():
            # Try to find by mention
            if item.startswith('<@') and item.endswith('>'):
                member_id = item.strip('<@!>')
                try:
                    member = interaction.guild.get_member(int(member_id))
                    if member:
                        member_list.append(member)
                except ValueError:
                    pass
            # Try to find by ID
            else:
                try:
                    member = interaction.guild.get_member(int(item))
                    if member:
                        member_list.append(member)
                except ValueError:
                    pass
        
        if not member_list:
            embed = EmbedBuilder.error_embed(
                "No Members Found",
                "Please provide valid member mentions or IDs."
            )
            await interaction.followup.send(embed=embed)
            return
        
        success = []
        failed = []
        
        for member in member_list:
            try:
                if action.lower() == 'add':
                    await member.add_roles(role)
                else:
                    await member.remove_roles(role)
                success.append(member.mention)
            except discord.Forbidden:
                failed.append(member.mention)
        
        embed = EmbedBuilder.create_embed(
            title="📊 Mass Role Update",
            color=Config.EMBED_COLORS['info'],
            fields=[
                {
                    "name": f"✅ Success ({len(success)})",
                    "value": ", ".join(success[:10]) + (f"\n...and {len(success)-10} more" if len(success) > 10 else ""),
                    "inline": False
                }
            ]
        )
        
        if failed:
            embed.add_field(
                name=f"❌ Failed ({len(failed)})",
                value=", ".join(failed[:5]),
                inline=False
            )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="roleinfo", description="Get information about a role")
    @app_commands.describe(role="The role to get info about")
    async def roleinfo(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        """Get detailed information about a role."""
        
        # Count members with this role
        member_count = len(role.members)
        
        # Get role permissions
        permissions = []
        for perm, value in role.permissions:
            if value:
                permissions.append(f"✅ {perm.replace('_', ' ').title()}")
        
        embed = EmbedBuilder.create_embed(
            title=f"👑 Role: {role.name}",
            color=role.color if role.color.value else Config.EMBED_COLORS['info'],
            fields=[
                {"name": "ID", "value": role.id, "inline": True},
                {"name": "Color", "value": f"#{role.color.value:06x}" if role.color.value else "Default", "inline": True},
                {"name": "Members", "value": str(member_count), "inline": True},
                {"name": "Position", "value": str(role.position), "inline": True},
                {"name": "Hoisted", "value": "Yes" if role.hoist else "No", "inline": True},
                {"name": "Mentionable", "value": "Yes" if role.mentionable else "No", "inline": True},
                {"name": "Managed", "value": "Yes" if role.managed else "No", "inline": True},
                {
                    "name": "Created",
                    "value": discord.utils.format_dt(role.created_at, 'R'),
                    "inline": True
                },
                {
                    "name": "Key Permissions",
                    "value": "\n".join(permissions[:10]) if permissions else "None",
                    "inline": False
                }
            ]
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="createrole", description="Create a new role")
    @app_commands.describe(
        name="Name of the role",
        color="Hex color code (e.g., #FF0000)",
        hoist="Show role separately in member list",
        mentionable="Allow everyone to mention this role"
    )
    @is_admin()
    async def createrole(
        self,
        interaction: discord.Interaction,
        name: str,
        color: Optional[str] = None,
        hoist: bool = False,
        mentionable: bool = False
    ):
        """Create a new role."""
        
        try:
            # Parse color
            role_color = discord.Color.default()
            if color:
                color = color.lstrip('#')
                role_color = discord.Color(int(color, 16))
            
            # Create role
            role = await interaction.guild.create_role(
                name=name,
                color=role_color,
                hoist=hoist,
                mentionable=mentionable,
                reason=f"Created by {interaction.user}"
            )
            
            embed = EmbedBuilder.success_embed(
                "Role Created",
                f"Created role {role.mention}\n"
                f"**ID:** {role.id}\n"
                f"**Color:** #{role.color.value:06x}"
            )
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            embed = EmbedBuilder.error_embed(
                "Permission Denied",
                "I don't have permission to create roles."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Error",
                f"Failed to create role: {str(e)}"
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @app_commands.command(name="deleterole", description="Delete a role")
    @app_commands.describe(role="The role to delete")
    @is_admin()
    async def deleterole(
        self,
        interaction: discord.Interaction,
        role: discord.Role
    ):
        """Delete a role."""
        
        if role.managed:
            embed = EmbedBuilder.error_embed(
                "Cannot Delete",
                "This role is managed by an integration and cannot be deleted."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        try:
            role_name = role.name
            await role.delete(reason=f"Deleted by {interaction.user}")
            
            embed = EmbedBuilder.success_embed(
                "Role Deleted",
                f"Successfully deleted role: **{role_name}**"
            )
            
            await interaction.response.send_message(embed=embed)
            
        except discord.Forbidden:
            embed = EmbedBuilder.error_embed(
                "Permission Denied",
                "I don't have permission to delete this role."
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Roles(bot))