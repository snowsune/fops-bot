import discord

from discord import app_commands
from discord.ext import commands


# Dictionary to store species data
species_data = {
    "fox": {"male": 20, "female": 19},  # Heights in inches
    "wolf": {"male": 32, "female": 30},
    # Add more species here...
}


class AnthroHeightConverter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="convert_height",
        description="Convert human height to an anthropomorphic animal height.",
    )
    async def convert_height(self, ctx: discord.Interaction):
        # Show a modal to collect user input
        modal = HeightConversionModal()
        await ctx.response.send_modal(modal)


class HeightConversionModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="Height Conversion")

        # Text input for height
        self.height_input = discord.ui.TextInput(
            label="Enter your height (ft/inches)",
            placeholder="5'11\"",
        )
        self.add_item(self.height_input)

        # Text input for gender
        self.gender_input = discord.ui.TextInput(
            label="Enter your gender (male/female)",
            placeholder="male",
        )
        self.add_item(self.gender_input)

        # Dropdown (select) for species
        self.species_select = discord.ui.Select(
            placeholder="Select a species",
            options=[
                discord.SelectOption(label=species.capitalize(), value=species)
                for species in species_data.keys()
            ],
        )
        self.add_item(self.species_select)

    async def callback(self, interaction: discord.Interaction):
        user_height_input = self.height_input.value
        gender_input = self.gender_input.value.lower()
        selected_species = self.species_select.values[0]

        # Parse height input
        try:
            feet, inches = map(int, user_height_input.split("'"))
            user_height_inches = feet * 12 + inches
        except ValueError:
            await interaction.response.send_message(
                "Invalid height format. Please use feet'inches\" format, e.g., 5'11\".",
                ephemeral=True,
            )
            return

        # Convert height for selected species
        species_height = species_data[selected_species][gender_input]
        anthro_height = self.convert_height(user_height_inches, species_height)

        # Create embed with conversion results
        embed = discord.Embed(
            title="Anthropomorphic Height Conversion", color=discord.Color.blue()
        )
        embed.add_field(
            name="User Height",
            value=f"{feet}'{inches}\" ({user_height_inches} inches)",
            inline=False,
        )
        embed.add_field(name="Gender", value=gender_input.capitalize(), inline=False)
        embed.add_field(
            name=f"{selected_species.capitalize()} Equivalent Height",
            value=f"{anthro_height:.2f} inches",
            inline=False,
        )

        await interaction.response.send_message(embed=embed)

    def convert_height(self, user_height_inches, species_height_inches):
        # Convert human height to the species height using the ratio
        human_average_height = 66  # Average human height in inches
        anthro_height = (
            user_height_inches / human_average_height
        ) * species_height_inches
        return anthro_height


async def setup(bot):
    await bot.add_cog(AnthroHeightConverter(bot))
