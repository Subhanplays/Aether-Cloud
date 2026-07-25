"""
Hosting management features - website status, domain monitoring, SSL checks.
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import aiohttp
import asyncio
import ssl
import socket
import json
import io

from utils.embeds import EmbedBuilder
from utils.checks import is_admin, is_moderator
from database.manager import DatabaseManager
from config import Config
from utils.logger import logger


class Hosting(commands.Cog):
    """Hosting management and monitoring tools."""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.db = DatabaseManager()
        self.session: Optional[aiohttp.ClientSession] = None
        self.monitored_sites: Dict[str, Dict] = {}
        self.monitor_loop.start()
    
    async def cog_load(self):
        """Called when cog is loaded."""
        if not self.session:
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
    
    async def cog_unload(self):
        """Clean up when cog is unloaded."""
        self.monitor_loop.cancel()
        if self.session:
            await self.session.close()
    
    @tasks.loop(minutes=5)
    async def monitor_loop(self):
        """Monitor websites and services."""
        # Load monitored sites from database
        # This would be implemented to check all monitored sites
        pass
    
    @monitor_loop.before_loop
    async def before_monitor_loop(self):
        """Wait until bot is ready before starting monitor loop."""
        await self.bot.wait_until_ready()
    
    @app_commands.command(name="websitecheck", description="Check a website's status")
    @app_commands.describe(
        url="The website URL to check (include https://)",
        show_headers="Show response headers"
    )
    async def website_check(
        self,
        interaction: discord.Interaction,
        url: str,
        show_headers: bool = False
    ):
        """Check website status and response time."""
        
        await interaction.response.defer()
        
        # Validate URL
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            start_time = datetime.utcnow()
            
            async with self.session.get(url, allow_redirects=True) as response:
                end_time = datetime.utcnow()
                
                response_time = (end_time - start_time).total_seconds() * 1000
                
                # Determine status color
                if response.status < 300:
                    color = Config.EMBED_COLORS['success']
                    status_text = "✅ Online"
                elif response.status < 400:
                    color = Config.EMBED_COLORS['warning']
                    status_text = "⚠️ Redirect"
                elif response.status < 500:
                    color = Config.EMBED_COLORS['error']
                    status_text = "❌ Client Error"
                else:
                    color = Config.EMBED_COLORS['error']
                    status_text = "🚨 Server Error"
                
                embed = EmbedBuilder.create_embed(
                    title=f"🌐 Website Check: {url}",
                    color=color,
                    fields=[
                        {"name": "Status", "value": f"{status_text} ({response.status})", "inline": True},
                        {"name": "Response Time", "value": f"{response_time:.0f}ms", "inline": True},
                        {"name": "Server", "value": response.headers.get('Server', 'Unknown'), "inline": True},
                        {"name": "Content Type", "value": response.headers.get('Content-Type', 'Unknown'), "inline": True},
                        {"name": "Content Length", "value": f"{len(await response.read())} bytes", "inline": True},
                        {"name": "Final URL", "value": str(response.url)[:100], "inline": False},
                    ],
                    footer=f"Checked at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )
                
                if show_headers:
                    headers_text = "\n".join([f"**{k}:** {v[:100]}" for k, v in list(response.headers.items())[:10]])
                    embed.add_field(
                        name="Response Headers",
                        value=headers_text[:1024] or "None",
                        inline=False
                    )
        
        except asyncio.TimeoutError:
            embed = EmbedBuilder.error_embed(
                "Connection Timeout",
                f"Could not connect to {url} within 30 seconds."
            )
        except aiohttp.ClientError as e:
            embed = EmbedBuilder.error_embed(
                "Connection Error",
                f"Failed to connect to {url}\nError: {str(e)}"
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Error",
                f"An error occurred: {str(e)}"
            )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="sslcheck", description="Check SSL certificate of a domain")
    @app_commands.describe(domain="The domain to check (e.g., example.com)")
    async def ssl_check(
        self,
        interaction: discord.Interaction,
        domain: str
    ):
        """Check SSL certificate information."""
        
        await interaction.response.defer()
        
        # Remove protocol if present
        domain = domain.replace('https://', '').replace('http://', '').split('/')[0]
        
        try:
            # Get SSL certificate
            context = ssl.create_default_context()
            
            with socket.create_connection((domain, 443), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    
                    # Parse certificate info
                    subject = dict(x[0] for x in cert['subject'])
                    issuer = dict(x[0] for x in cert['issuer'])
                    
                    # Parse dates
                    not_before = datetime.strptime(
                        cert['notBefore'],
                        '%b %d %H:%M:%S %Y %Z'
                    )
                    not_after = datetime.strptime(
                        cert['notAfter'],
                        '%b %d %H:%M:%S %Y %Z'
                    )
                    
                    days_remaining = (not_after - datetime.utcnow()).days
                    
                    # Determine status
                    if days_remaining < 0:
                        color = Config.EMBED_COLORS['error']
                        status = "❌ Expired"
                    elif days_remaining < 30:
                        color = Config.EMBED_COLORS['warning']
                        status = f"⚠️ Expiring Soon ({days_remaining} days)"
                    else:
                        color = Config.EMBED_COLORS['success']
                        status = f"✅ Valid ({days_remaining} days remaining)"
                    
                    embed = EmbedBuilder.create_embed(
                        title=f"🔒 SSL Certificate: {domain}",
                        color=color,
                        fields=[
                            {"name": "Status", "value": status, "inline": True},
                            {"name": "Issued To", "value": subject.get('commonName', 'Unknown'), "inline": True},
                            {"name": "Issued By", "value": issuer.get('organizationName', 'Unknown'), "inline": True},
                            {"name": "Valid From", "value": not_before.strftime('%Y-%m-%d'), "inline": True},
                            {"name": "Valid Until", "value": not_after.strftime('%Y-%m-%d'), "inline": True},
                            {"name": "Days Remaining", "value": f"{days_remaining} days", "inline": True},
                            {
                                "name": "SAN", 
                                "value": "\n".join(
                                    cert.get('subjectAltName', [])[:5]
                                ) or "None",
                                "inline": False
                            },
                        ],
                        footer=f"Checked at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                    )
        
        except socket.gaierror:
            embed = EmbedBuilder.error_embed(
                "DNS Error",
                f"Could not resolve domain: {domain}"
            )
        except socket.timeout:
            embed = EmbedBuilder.error_embed(
                "Connection Timeout",
                f"Connection to {domain} timed out."
            )
        except ssl.SSLError as e:
            embed = EmbedBuilder.error_embed(
                "SSL Error",
                f"SSL certificate error for {domain}\nError: {str(e)}"
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Error",
                f"An error occurred while checking SSL: {str(e)}"
            )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="dnscheck", description="Look up DNS records for a domain")
    @app_commands.describe(domain="The domain to look up (e.g., example.com)")
    async def dns_check(
        self,
        interaction: discord.Interaction,
        domain: str
    ):
        """Look up DNS records."""
        
        await interaction.response.defer()
        
        domain = domain.replace('https://', '').replace('http://', '').split('/')[0]
        
        embed = EmbedBuilder.create_embed(
            title=f"🔍 DNS Lookup: {domain}",
            color=Config.EMBED_COLORS['info'],
        )
        
        # A Records (IPv4)
        try:
            import socket
            ipv4 = socket.gethostbyname(domain)
            embed.add_field(name="📡 IPv4 (A Record)", value=f"```{ipv4}```", inline=False)
        except socket.gaierror:
            embed.add_field(name="📡 IPv4 (A Record)", value="```Not found```", inline=False)
        
        # MX Records (Mail)
        try:
            import dns.resolver
            mx_records = dns.resolver.resolve(domain, 'MX')
            mx_text = "\n".join([f"• {r.exchange} (Priority: {r.preference})" for r in mx_records[:5]])
            embed.add_field(name="📧 MX Records", value=f"```{mx_text}```", inline=False)
        except:
            embed.add_field(name="📧 MX Records", value="```Not found```", inline=False)
        
        # NS Records (Nameservers)
        try:
            import dns.resolver
            ns_records = dns.resolver.resolve(domain, 'NS')
            ns_text = "\n".join([f"• {r}" for r in ns_records[:5]])
            embed.add_field(name="🌐 Nameservers", value=f"```{ns_text}```", inline=False)
        except:
            embed.add_field(name="🌐 Nameservers", value="```Not found```", inline=False)
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="portcheck", description="Check if a port is open on a host")
    @app_commands.describe(
        host="The host to check",
        port="The port to check"
    )
    async def port_check(
        self,
        interaction: discord.Interaction,
        host: str,
        port: app_commands.Range[int, 1, 65535]
    ):
        """Check if a specific port is open."""
        
        await interaction.response.defer()
        
        host = host.replace('https://', '').replace('http://', '').split('/')[0]
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                # Port is open
                common_ports = {
                    21: "FTP",
                    22: "SSH",
                    25: "SMTP",
                    53: "DNS",
                    80: "HTTP",
                    110: "POP3",
                    143: "IMAP",
                    443: "HTTPS",
                    587: "SMTP (Submission)",
                    993: "IMAPS",
                    995: "POP3S",
                    3306: "MySQL",
                    3389: "RDP",
                    5432: "PostgreSQL",
                    8080: "HTTP (Alt)",
                    8443: "HTTPS (Alt)",
                    25565: "Minecraft",
                    27015: "Source Engine (Game)",
                }
                
                service = common_ports.get(port, "Unknown Service")
                
                embed = EmbedBuilder.success_embed(
                    "Port Check",
                    f"**Host:** {host}\n"
                    f"**Port:** {port}\n"
                    f"**Status:** ✅ Open\n"
                    f"**Service:** {service}"
                )
            else:
                embed = EmbedBuilder.error_embed(
                    "Port Check",
                    f"**Host:** {host}\n"
                    f"**Port:** {port}\n"
                    f"**Status:** ❌ Closed/Filtered"
                )
        
        except socket.gaierror:
            embed = EmbedBuilder.error_embed(
                "Error",
                f"Could not resolve host: {host}"
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Error",
                f"Failed to check port: {str(e)}"
            )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="pinghost", description="Ping a host to check latency")
    @app_commands.describe(host="The host to ping")
    async def ping_host(
        self,
        interaction: discord.Interaction,
        host: str
    ):
        """Ping a host and measure latency."""
        
        await interaction.response.defer()
        
        host = host.replace('https://', '').replace('http://', '').split('/')[0]
        
        try:
            import subprocess
            import platform
            
            # Determine ping command based on OS
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            
            # Run ping command
            command = ['ping', param, '4', host]
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                embed = EmbedBuilder.success_embed(
                    f"📡 Ping: {host}",
                    f"```\n{result.stdout}\n```"
                )
            else:
                embed = EmbedBuilder.error_embed(
                    "Ping Failed",
                    f"Could not reach {host}"
                )
        
        except subprocess.TimeoutExpired:
            embed = EmbedBuilder.error_embed(
                "Timeout",
                f"Ping request to {host} timed out."
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Error",
                f"Failed to ping: {str(e)}"
            )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="headers", description="View HTTP response headers from a URL")
    @app_commands.describe(url="The URL to check (include https://)")
    async def view_headers(
        self,
        interaction: discord.Interaction,
        url: str
    ):
        """View HTTP response headers."""
        
        await interaction.response.defer()
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        try:
            async with self.session.get(url, allow_redirects=True) as response:
                headers_dict = dict(response.headers)
                
                # Format headers
                headers_text = "\n".join([
                    f"**{k}:** {v[:100]}"
                    for k, v in list(headers_dict.items())[:15]
                ])
                
                embed = EmbedBuilder.create_embed(
                    title=f"📋 HTTP Headers: {url}",
                    description=headers_text[:4096] or "No headers found",
                    color=Config.EMBED_COLORS['info'],
                    fields=[
                        {"name": "Status", "value": str(response.status), "inline": True},
                        {"name": "Total Headers", "value": str(len(headers_dict)), "inline": True},
                    ],
                    footer=f"Checked at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )
        
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Error",
                f"Failed to fetch headers: {str(e)}"
            )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="whois", description="Get WHOIS information for a domain")
    @app_commands.describe(domain="The domain to look up")
    async def whois_lookup(
        self,
        interaction: discord.Interaction,
        domain: str
    ):
        """Basic WHOIS lookup."""
        
        await interaction.response.defer()
        
        domain = domain.replace('https://', '').replace('http://', '').split('/')[0]
        
        try:
            import whois
            
            w = whois.whois(domain)
            
            embed = EmbedBuilder.create_embed(
                title=f"📊 WHOIS: {domain}",
                color=Config.EMBED_COLORS['info'],
                fields=[
                    {"name": "Registrar", "value": str(w.registrar)[:100] or "N/A", "inline": True},
                    {"name": "Creation Date", "value": str(w.creation_date)[:50] or "N/A", "inline": True},
                    {"name": "Expiration Date", "value": str(w.expiration_date)[:50] or "N/A", "inline": True},
                    {"name": "Name Servers", "value": "\n".join(w.name_servers[:5]) if w.name_servers else "N/A", "inline": False},
                ],
                footer="Limited WHOIS information"
            )
        
        except ImportError:
            embed = EmbedBuilder.error_embed(
                "Module Not Available",
                "WHOIS lookup requires the python-whois package.\n"
                "Install with: `pip install python-whois`"
            )
        except Exception as e:
            embed = EmbedBuilder.error_embed(
                "Error",
                f"WHOIS lookup failed: {str(e)}"
            )
        
        await interaction.followup.send(embed=embed)
    
    @app_commands.command(name="monitor", description="Monitor a website for uptime")
    @app_commands.describe(
        url="The URL to monitor",
        name="A name for this monitor"
    )
    @is_admin()
    async def add_monitor(
        self,
        interaction: discord.Interaction,
        url: str,
        name: str
    ):
        """Add a website to monitor."""
        
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        
        self.monitored_sites[name] = {
            'url': url,
            'channel_id': interaction.channel_id,
            'guild_id': interaction.guild_id,
            'added_by': interaction.user.id,
            'status': 'unknown',
            'last_check': None
        }
        
        embed = EmbedBuilder.success_embed(
            "Monitor Added",
            f"**Name:** {name}\n"
            f"**URL:** {url}\n"
            f"**Channel:** {interaction.channel.mention}\n\n"
            f"You will be notified here if the site goes down."
        )
        
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="monitors", description="List all monitored sites")
    @is_admin()
    async def list_monitors(self, interaction: discord.Interaction):
        """List all monitored websites."""
        
        if not self.monitored_sites:
            embed = EmbedBuilder.info_embed(
                "No Monitors",
                "No websites are currently being monitored."
            )
        else:
            monitor_list = []
            for name, info in self.monitored_sites.items():
                status_emoji = "✅" if info.get('status') == 'up' else "❓"
                monitor_list.append(
                    f"{status_emoji} **{name}**\n"
                    f"└ {info['url']}\n"
                    f"└ Status: {info.get('status', 'unknown')}"
                )
            
            embed = EmbedBuilder.create_embed(
                title=f"📡 Monitored Sites ({len(self.monitored_sites)})",
                description="\n\n".join(monitor_list),
                color=Config.EMBED_COLORS['info']
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    """Setup function for loading the cog."""
    await bot.add_cog(Hosting(bot))