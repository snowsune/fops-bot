# Services cog
# Functions to interact with various services!


import os
import imp
import discord
import logging
import requests


from typing import Literal, Optional
from discord import app_commands
from discord.ext import commands, tasks

pf = imp.load_source(
    "scrape_pfsense_dhcp", "fops_bot/scripts/pfsense_arp/pfsense-dhcp.py"
)


class servicesCog(commands.Cog, name="Bconsole"):
    def __init__(self, bot):
        # Bot instance
        self.bot = bot

        # Alert chan
        self.alert_channel = self.bot.get_channel(
            int(os.environ.get("SERVICE_CHAN_ID", ""))
        )

        # Setup for arp watcher
        self.previousArpData = []
        url = os.environ.get("PFSENSE_URL", "")
        self.pfurl = url.rstrip("/") + "/status_dhcp_leases.php"
        self.pfuser = os.environ.get("PFSENSE_USER", "")
        self.pfpassword = os.environ.get("PFSENSE_PASSWORD", "")

    @commands.Cog.listener()
    async def on_ready(self):
        self.watch_arp.start()

    def sizeof_fmt(self, num):
        for unit in ("Bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB"):
            if abs(num) < 1024.0:
                return f"{num:3.1f} {unit}"
            num /= 1024.0
        return f"{num} Bytes"

    @app_commands.command(name="service")
    @app_commands.choices(
        service=[
            app_commands.Choice(name="Nextcloud", value="nc"),
        ]
    )
    async def serviceCommand(
        self, ctx: discord.Interaction, service: app_commands.Choice[str]
    ):
        logging.info(
            f"Processing request for {ctx.user.name}, request is {service.value}"
        )
        if service.value == "nc":
            await ctx.response.defer()  # This might take a bit

            try:
                nc_api = "https://nextcloud.kitsunehosting.net/ocs/v2.php/apps/serverinfo/api/v1/info?format=json"
                resp = requests.get(
                    nc_api, headers={"NC-Token": os.environ.get("NCTOKEN")}
                )
                data = resp.json()
            except Exception as e:
                await ctx.followup.send(
                    f"Ohno! There was an error reaching NC...\n```{e}```"
                )
                return

            embed = discord.Embed(
                title="Nextcloud Stats",
                color=0x76FF26,
            )

            embed.add_field(
                name="Version",
                value=data["ocs"]["data"]["nextcloud"]["system"]["version"],
                inline=False,
            )

            embed.add_field(
                name="Total Files",
                value=data["ocs"]["data"]["nextcloud"]["storage"]["num_files"],
                inline=False,
            )

            embed.add_field(
                name="Database Size",
                value=self.sizeof_fmt(
                    int(data["ocs"]["data"]["server"]["database"]["size"])
                ),
                inline=False,
            )

            embed.add_field(
                name="Users (5m)",
                value=data["ocs"]["data"]["activeUsers"]["last5minutes"],
                inline=True,
            )

            embed.add_field(
                name="Users (1hr)",
                value=data["ocs"]["data"]["activeUsers"]["last1hour"],
                inline=True,
            )

            embed.add_field(
                name="Users (24hr)",
                value=data["ocs"]["data"]["activeUsers"]["last24hours"],
                inline=True,
            )

            embed.set_footer(text=f"Bot Version {self.bot.version}")

            await ctx.followup.send(embed=embed)
        else:
            await ctx.response.send_message("Sorry! Couldn't find that service.")

    @tasks.loop(seconds=40)
    async def watch_arp(self):
        # Runs every 120 seconds
        current = pf.scrape_pfsense_dhcp(self.pfurl, self.pfuser, self.pfpassword)

        # Strip unused keys from dict
        for key_to_strip in ["Start", "End", "Online"]:
            for e, element in enumerate(current):
                current[e].pop(key_to_strip)

        logging.debug("Checking ARP table.")

        # Check if data is valid before spamming everyone
        if len(self.previousArpData) > 0:
            _l = []
            # Check for changed hosts
            for element in current:
                if element not in self.previousArpData:
                    _l.append(element)

            # Iter all the hosts that have changed
            for host in _l:
                logging.info(host)
                _msg = f"New host in ARP table: `{host['Hostname']}` ip: `{host['IP address']}`"

                if len(host["Description"]) > 2:
                    _msg += f", desc: `{host['Description']}`"

                await self.alert_channel.send(_msg)

        # Record the previous data as the current
        self.previousArpData = current


async def setup(bot):
    await bot.add_cog(servicesCog(bot))
