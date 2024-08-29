import discord
import logging

from discord import app_commands
from discord.ext import commands

# Dictionary to store species data
species_data = {
    "fox": {"male": 20, "female": 19},  # Heights in inches
    "wolf": {"male": 32, "female": 30},
    "giraffe": {"male": 216, "female": 192},
}


class AnthroHeightConverter(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="convert_height",
        description="Convert human height to an anthropomorphic height!",
    )
    async def convert_height(self, interaction: discord.Interaction):
        # Send the view with dropdowns and text input
        view = HeightConversionView()
        await interaction.response.send_message(
            "Use the form below, the bot will collect what data it needs:",
            view=view,
            ephemeral=True,
        )


class HeightConversionView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(SpeciesSelect())
        self.add_item(GenderSelect())
        self.add_item(ConvertButton())


class SpeciesSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label=species.capitalize(), value=species)
            for species in species_data.keys()
        ]
        super().__init__(placeholder="Select a species", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()  # No response needed yet; just register the selection


class GenderSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Male", value="male"),
            discord.SelectOption(label="Female", value="female"),
        ]
        super().__init__(placeholder="Select your gender", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()  # No response needed yet; just register the selection


class ConvertButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Convert", style=discord.ButtonStyle.primary)

    async def callback(self, interaction: discord.Interaction):
        species_select = self.view.children[0]  # First view obj (so, species)
        gender_select = self.view.children[1]  # So on

        selected_species = species_select.values[0] if species_select.values else None
        gender_input = gender_select.values[0] if gender_select.values else None

        if not selected_species or not gender_input:
            await interaction.response.send_message(
                "Please select both species and gender.", ephemeral=True
            )
            return

        # If species and gender are selected, show the modal
        modal = HeightInputModal(selected_species, gender_input)
        await interaction.response.send_modal(modal)


class HeightInputModal(discord.ui.Modal, title="Enter Height"):
    height_input = discord.ui.TextInput(
        label="Enter your height (ft'inches)",
        placeholder="e.g., 5'11\"",
        style=discord.TextStyle.short,
    )

    def __init__(self, species: str, gender: str):
        super().__init__()
        self.species = species
        self.gender = gender

    async def on_submit(self, interaction: discord.Interaction):
        user_height_input = self.height_input.value

        # Parse height input
        try:
            feet, inches = map(int, user_height_input.replace('"', "").split("'"))
            user_height_inches = feet * 12 + inches
        except ValueError as e:
            await interaction.response.send_message(
                "Invalid height format. Please use feet'inches\" format, e.g., 5'11\".",
                ephemeral=True,
            )
            logging.error(e)
            return

        # Convert height for selected species
        species_height = species_data[self.species][self.gender]
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
        embed.add_field(name="Gender", value=self.gender.capitalize(), inline=False)
        embed.add_field(
            name=f"{self.species.capitalize()} Equivalent Height",
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
