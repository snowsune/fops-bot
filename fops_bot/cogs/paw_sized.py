import discord
import logging
import re
import random
from discord.ext import commands
from discord import app_commands
import pint

paw_data = {
    # Everybody's paw sizes! Done in inches.
    "**Vixi** Paws": {
        "length_digigrade": 2.9,
        "length_plantigrade": 2.9,
    },
    "**Shaezie** Paws": {
        "length_digigrade": 3.1,
        "length_plantigrade": 3.1,
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
        Does what the previous one did, but using Pint.
        """

        try:
            # Create a Pint unit registry
            ureg = pint.UnitRegistry()

            # Clean up the input string
            length_str = length_str.strip()

            # Handle exact num'num" pattern
            feet_inches_pattern = r"(\d+(?:\.\d+)?)'(\d+(?:\.\d+)?)\""
            feet_inches_match = re.search(feet_inches_pattern, length_str)
            if feet_inches_match:
                feet = float(feet_inches_match.group(1))
                inches = float(feet_inches_match.group(2))
                return feet * 12 + inches

            # Try and parse with Pint
            try:
                quantity = ureg.Quantity(length_str)
                return quantity.to(ureg.inches).magnitude
            except pint.UndefinedUnitError:
                # If Pint can't parse it, try treating it as plain inches
                try:
                    number = float(length_str)
                    return number
                except ValueError:
                    raise ValueError(f"Could not parse length: {length_str}")

        except Exception as e:
            raise ValueError(f"Could not parse length '{length_str}': {str(e)}")

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

            if length_inches <= 0.5:
                raise ValueError("Has to be a reasonable length!")

            if length_inches > 63360:
                raise ValueError("That's too big to be reasonable.")

            # Convert to centimeters for display
            length_cm = length_inches * 2.54

            # Get 5 random people
            random_people = self.get_random_people(5)

            # Build the response
            response_lines = [f'{length_inches:.1f}" ({length_cm:.1f}cm) is about']

            for person in random_people:
                paw_length = paw_data[person]["length_digigrade"]
                paw_count = length_inches / paw_length
                response_lines.append(f'`{paw_count:.1f}` {person} ({paw_length:.1f}")')

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
