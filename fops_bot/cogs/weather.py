# 2023, Fops Bot
# MIT License


import discord
import logging
import asyncio
import pytz
import os
import python_weather


from typing import Literal, Optional
from discord import app_commands
from discord.ext import commands, tasks

from datetime import datetime, timedelta, time, timezone

from utilities.common import seconds_until

cler = "🟩"
caut = "🟨"
warn = "🟥"


async def getweather():
    # declare the client. the measuring unit used defaults to the metric system (celcius, km/h, etc.)
    async with python_weather.Client(unit=python_weather.IMPERIAL) as client:
        # fetch a weather forecast from a city
        weather = await client.get("Concord, New Hampshire")

        # returns the current day's forecast temperature (int)
        # print(weather.current.temperature)

        forecast = next(weather.forecasts)

        showTempWarning = False
        tempWarning = "WARNING: Low temperature can reduce tire flex and adversely affecting handling and grip, very low temperature brings a snow and ice risk.\n"
        showRainWarning = False
        rainWarning = "WARNING: Rain can reduce handling and grip, accelerate corrosion and lower visibility.\n"

        data = f"""\tJoes Weather Forecast for {forecast.date}\t\n"""
        for hourly in forecast.hourly:
            warnings = []

            # First, check if its early enough to even care
            if hourly.time.hour < 4:  # less than 4AM
                logging.debug(f"Skipping {hourly}")
                continue  # Skip to next forecast

            # Check temperature
            if hourly.temperature < 40 or hourly.temperature > 105:
                warnings.append(warn)
                showTempWarning = True
                logging.info(f"Temperature ({hourly.temperature}) was out of range")
            else:
                warnings.append(cler)

            # Check for rain
            rainList = ["rain", "snow", "sleet", "fog", "hail"]
            if any(item in hourly.description for item in rainList):
                warnings.append(warn)
                showRainWarning = True
                logging.info(f"Rain detected in {hourly.description}")
            else:
                warnings.append(cler)

            data += f"{hourly.time.strftime('%I %p')} Temperature {hourly.temperature:3}f, {hourly.description:22}\t"

            for warning in warnings:
                data += warning
            data += "\n"

        data += f"\nVisibility {weather.current.visibility} miles\n"

        data += "\n"
        # if showRainWarning:
        #     data += rainWarning
        # if showTempWarning:
        #     data += tempWarning

        data += f"\nVersion {os.environ.get('GIT_COMMIT')}"

        return data


class WeatherCog(commands.Cog, name="WeatherCog"):
    def __init__(self, bot):
        self.bot = bot

        # timezone
        self.localtz = pytz.timezone("US/Eastern")

        # Tasks
        self.weather_alert.start()

    @tasks.loop(minutes=1)
    async def weather_alert(self):
        logging.info("Scheduling weather alert")

        try:
            wait = seconds_until(8, 00)  # Wait here till 8am
            logging.info(f"Waiting {wait:.2f} seconds before running")
            await asyncio.sleep(wait)
            logging.info("Running now!")

            logging.info("Getting alert channel")
            alert_channel = self.bot.get_channel(
                int(os.environ.get("WEATHER_CHAN_ID", ""))
            )

            logging.info("Getting weather")
            data = await getweather()

            # How many attempts we get
            tries = 3
            success = False

            while tries > 0:
                await asyncio.sleep(5)  # Wait so we dont spam too quickly
                try:
                    last = await alert_channel.fetch_message(
                        alert_channel.last_message_id
                    )
                except:
                    last = None
                now = datetime.now(timezone.utc)

                tries -= 1

                if (last != None) and (last.created_at > now - timedelta(minutes=2)):
                    logging.info("Message published successfully")
                    success = True
                    break
                else:
                    logging.warn(
                        f"Last weather reading is out of date, sending.. {tries} left"
                    )
                    await alert_channel.send(f"```\n{data}\n```")

            if success != True:
                logging.error("Did not send succesfully...")

            logging.info("Done")
        except Exception as e:
            logging.error(f"Error!! {e}")
        await asyncio.sleep(60)  # So we dont spam

    @app_commands.command(name="weather")
    async def version(self, ctx: discord.Interaction):
        """
        Shows you the weather
        """

        data = await getweather()

        await ctx.response.send_message(f"```\n{data}\n```")


async def setup(bot):
    await bot.add_cog(WeatherCog(bot))
