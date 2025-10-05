import discord
import logging
import re
import random
from discord.ext import commands
from discord import app_commands

paw_data = {
    # Everybody's paw sizes! Done in inches.
    "**Vixi** Paws": {
        "length_digigrade": 2.9,
        "length_plantigrade": 2.9,
    },
    "**Luci** Hooves": {
        "length_digigrade": 6.0,
        "length_plantigrade": 6.0,
    },
    "**Kyte** Paws": {
        "length_digigrade": 0.7,
        "length_plantigrade": 0.7,
    },
    "**Tibran** Paws": {
        "length_digigrade": 7.0,
        "length_plantigrade": 13.0,
    },
    "**Randal** Paws": {
        "length_digigrade": 4.0,
        "length_plantigrade": 5.0,
    },
    "**Yuni** Paws": {
        "length_digigrade": 6.0,
        "length_plantigrade": 7.0,
    },
    "**LC** Paws": {
        "length_digigrade": 4.5,
        "length_plantigrade": 4.5,
    },
    "**Maxene** Paws": {
        "length_digigrade": 10.0,
        "length_plantigrade": 10.0,
    },
    "**Alex Mitch** Paws": {
        "length_digigrade": 5.0,
        "length_plantigrade": 6.0,
    },
    "**Tirga** Paws": {
        "length_digigrade": 16.0,
        "length_plantigrade": 16.0,
    },
}


class PawSizedCog(commands.Cog, name="PawSizedCog"):
    def __init__(self, bot):
        self.bot = bot
        self.logger = logging.getLogger(__name__)

    def parse_length_to_inches(self, length_str: str) -> float:
        """
        Parse various length formats and convert to inches.
        Supports: 20 inches, 20", 2'3", 15cm, 4m, 4 meters, etc.
        """
        length_str = length_str.strip().lower()

        # Remove any non-alphanumeric characters
        length_str = re.sub(r"[^a-zA-Z0-9\s]", "", length_str)

        # Remove any extra whitespace and normalize
        length_str = re.sub(r"\s+", " ", length_str)

        # Pattern for feet and inches: 2'3", 2' 3", 2ft 3in, etc.
        feet_inches_pattern = r"(\d+)\s*[''']?\s*(\d+)\s*[\"']?"
        feet_inches_match = re.search(feet_inches_pattern, length_str)
        if feet_inches_match:
            feet = float(feet_inches_match.group(1))
            inches = float(feet_inches_match.group(2))
            return feet * 12 + inches

        # Pattern for just feet: 2', 2ft, 2 feet, etc.
        feet_pattern = r"(\d+(?:\.\d+)?)\s*(?:[''']|ft|feet?)\b"
        feet_match = re.search(feet_pattern, length_str)
        if feet_match:
            feet = float(feet_match.group(1))
            return feet * 12

        # Pattern for inches: 20", 20 inches, 20in, etc.
        inches_pattern = r"(\d+(?:\.\d+)?)\s*(?:[\"']|inches?|in)\b"
        inches_match = re.search(inches_pattern, length_str)
        if inches_match:
            return float(inches_match.group(1))

        # Pattern for centimeters: 15cm, 15 centimeters, etc.
        cm_pattern = r"(\d+(?:\.\d+)?)\s*(?:cm|centimeters?|centimetres?)\b"
        cm_match = re.search(cm_pattern, length_str)
        if cm_match:
            cm = float(cm_match.group(1))
            return cm / 2.54  # Convert cm to inches

        # Pattern for meters: 4m, 4 meters, 4 metres, etc.
        meters_pattern = r"(\d+(?:\.\d+)?)\s*(?:m|meters?|metres?)\b"
        meters_match = re.search(meters_pattern, length_str)
        if meters_match:
            meters = float(meters_match.group(1))
            return meters * 39.3701  # Convert meters to inches

        # Pattern for just a number (assume inches if no unit)
        number_pattern = r"(\d+(?:\.\d+)?)\s*$"
        number_match = re.search(number_pattern, length_str)
        if number_match:
            return float(number_match.group(1))

        raise ValueError(f"Could not parse length: {length_str}")

    def get_random_people(self, count: int = 5) -> list[str]:
        """Get a random selection of people from the paw data."""
        people = list(paw_data.keys())
        return random.sample(people, min(count, len(people)))

    @app_commands.command(name="paw_sized")
    @app_commands.describe(
        length='Length in various formats: 20 inches, 20", 2\'3", 15cm, 4m, 4 meters, etc.'
    )
    async def paw_sized(self, interaction: discord.Interaction, length: str):
        """
        Convert a length and show how many of each person's paws it equals.

        Examples:
        - /paw_sized 20 inches
        - /paw_sized 2'3\"
        - /paw_sized 15cm
        - /paw_sized 4m
        """
        try:
            # Parse the length to inches
            length_inches = self.parse_length_to_inches(length)

            # Convert to centimeters for display
            length_cm = length_inches * 2.54

            # Get 5 random people
            random_people = self.get_random_people(5)

            # Build the response
            response_lines = [f'{length_inches:.1f}" ({length_cm:.1f}cm) is about']

            for person in random_people:
                paw_length = paw_data[person]["length_digigrade"]
                paw_count = length_inches / paw_length
                response_lines.append(f"`{paw_count:.1f}` {person}")

            response = "\n".join(response_lines)

            await interaction.response.send_message(response)

        except ValueError as e:
            await interaction.response.send_message(
                f"❌ Error parsing length: {e}\n\n"
                "Supported formats:\n"
                '• `20 inches` or `20"`\n'
                "• `2'3\"` (feet and inches)\n"
                "• `15cm` or `15 centimeters`\n"
                "• `4m` or `4 meters`\n"
                "• Just a number (assumes inches)",
                ephemeral=True,
            )
        except Exception as e:
            self.logger.error(f"Error in paw_sized command: {e}")
            await interaction.response.send_message(
                "❌ An error occurred while processing your request.", ephemeral=True
            )


async def setup(bot):
    await bot.add_cog(PawSizedCog(bot))
