import discord
from datetime import datetime, timezone
from typing import List
from fops_bot.models import get_session, Subscription


class ChannelSelectDropdown(discord.ui.Select):
    def __init__(self, interaction: discord.Interaction, on_select_callback):
        options = []
        self.guild = interaction.guild
        self.on_select_callback = on_select_callback
        from discord import Member

        show_channels = False
        channels = []
        if self.guild and isinstance(interaction.user, Member):
            perms = interaction.user.guild_permissions  # type: ignore
            if perms and (perms.manage_guild or perms.manage_channels):
                show_channels = True

        if show_channels and isinstance(interaction.channel, discord.TextChannel):
            category = interaction.channel.category

            # What we're doing here is grabbing just this category of channels!
            if category:
                channels = [ch for ch in category.text_channels]
            else:
                channels = [interaction.channel]
            channels = channels[:24]  # Discord limit on options
            for channel in channels:
                options.append(
                    discord.SelectOption(
                        label=f"#{channel.name}", value=str(channel.id)
                    )
                )
        options.append(discord.SelectOption(label="Private Message (PM)", value="pm"))
        super().__init__(
            placeholder="Select where to receive updates...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="channel_select_dropdown",
        )

    async def callback(self, interaction: discord.Interaction):
        await self.on_select_callback(interaction, self.values[0])


class AddSubscriptionModal(discord.ui.Modal, title="Add Subscription"):
    def __init__(
        self, service_type: str, on_submit_callback, channel_id: str, is_pm: bool
    ):
        super().__init__()
        self.service_type = service_type
        self.on_submit_callback = on_submit_callback
        self.channel_id = channel_id
        self.is_pm = is_pm
        self.search_input = discord.ui.TextInput(
            label="Search/Username", custom_id="search_criteria", required=True
        )
        self.filters_input = discord.ui.TextInput(
            label="Filters (comma-separated, optional)",
            custom_id="filters",
            required=False,
        )
        self.add_item(self.search_input)
        self.add_item(self.filters_input)

    async def on_submit(self, interaction: discord.Interaction):
        search_criteria = self.search_input.value.strip()
        filters = self.filters_input.value.strip() if self.filters_input.value else None
        await self.on_submit_callback(
            interaction,
            self.service_type,
            search_criteria,
            filters,
            self.channel_id,
            self.is_pm,
        )


class ServiceDropdown(discord.ui.Select):
    """
    The services you can add.
    """

    def __init__(self, on_select_callback):
        options = [
            discord.SelectOption(label="FurAffinity", value="FurAffinity"),
            discord.SelectOption(label="e621", value="e621"),
            discord.SelectOption(label="BixiBooru", value="BixiBooru"),
        ]
        super().__init__(
            placeholder="Select a service...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="service_dropdown",
        )
        self.on_select_callback = on_select_callback

    async def callback(self, interaction: discord.Interaction):
        await self.on_select_callback(interaction, self.values[0])


class RemoveDropdown(discord.ui.Select):
    def __init__(self, subscriptions, on_remove_callback):
        options = []
        for sub in subscriptions:
            channel_label = (
                "PM"
                if sub.is_pm
                else f"#{sub.channel_id if sub.channel_id is not None else 'unknown'}"
            )
            options.append(
                discord.SelectOption(
                    label=f"{sub.service_type}: {sub.search_criteria} ({channel_label})",
                    value=str(sub.id) if sub.id is not None else "unknown",
                )
            )
        super().__init__(
            placeholder="Select a subscription to remove...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="remove_dropdown",
        )
        self.on_remove_callback = on_remove_callback

    async def callback(self, interaction: discord.Interaction):
        await self.on_remove_callback(interaction, self.values[0])


class ManageFollowingView(discord.ui.View):
    def __init__(self, subscriptions: List[Subscription]):
        super().__init__(timeout=180)
        self.subscriptions = subscriptions
        self.adding = False
        self.removing = False

    @discord.ui.button(
        label="Add", style=discord.ButtonStyle.green, custom_id="add_following"
    )
    async def add_callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.adding:
            await interaction.response.send_message(
                "Already adding a subscription.", ephemeral=True
            )
            return
        self.adding = True
        dropdown = ServiceDropdown(lambda i, s: self.on_service_selected(i, s))
        view = discord.ui.View()
        view.add_item(dropdown)
        await interaction.response.send_message(
            "Select a service to follow:", view=view, ephemeral=True
        )

    async def on_service_selected(
        self, interaction: discord.Interaction, service_type: str
    ):
        # Show channel select dropdown
        dropdown = ChannelSelectDropdown(
            interaction, lambda i, v: self.on_channel_selected(i, v, service_type)
        )
        view = discord.ui.View()
        view.add_item(dropdown)
        await interaction.response.send_message(
            "Select where to receive updates:", view=view, ephemeral=True
        )

    async def on_channel_selected(
        self, interaction: discord.Interaction, value: str, service_type: str
    ):
        # value is channel_id or 'pm'
        is_pm = value == "pm"
        channel_id = str(interaction.user.id) if is_pm else value
        modal = AddSubscriptionModal(
            service_type, self.on_add_submit, channel_id=channel_id, is_pm=is_pm
        )
        await interaction.response.send_modal(modal)

    async def on_add_submit(
        self,
        interaction: discord.Interaction,
        service_type: str,
        search_criteria: str,
        filters: str,
        channel_id: str,
        is_pm: bool,
    ):
        user_id = interaction.user.id
        guild_id = interaction.guild.id if interaction.guild else None
        if not guild_id and not is_pm:
            await interaction.response.send_message(
                "This command must be used in a guild for channel subscriptions.",
                ephemeral=True,
            )
            return
        # Prevent duplicate
        with get_session() as session:
            duplicate = (
                session.query(Subscription)
                .filter(
                    Subscription.service_type == service_type,
                    Subscription.guild_id == (guild_id if not is_pm else None),
                    Subscription.channel_id == int(channel_id),
                    Subscription.search_criteria.ilike(search_criteria.strip().lower()),
                    Subscription.is_pm == is_pm,
                )
                .first()
            )
            if duplicate:
                await interaction.response.send_message(
                    "Already subscribed to this feed in this location.", ephemeral=True
                )
                return
            sub = Subscription(
                service_type=service_type,
                user_id=user_id,
                subscribed_at=datetime.now(timezone.utc),
                guild_id=(guild_id if not is_pm else None),
                channel_id=int(channel_id),
                search_criteria=search_criteria.strip().lower(),
                last_reported_id=None,
                filters=filters,
                is_pm=is_pm,
            )
            session.add(sub)
            session.commit()
        where = "your DMs" if is_pm else f"<#{channel_id}>"
        await interaction.response.send_message(
            f"Added subscription for `{service_type}`: `{search_criteria}` in {where}.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Remove", style=discord.ButtonStyle.red, custom_id="remove_following"
    )
    async def remove_callback(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.removing:
            await interaction.response.send_message(
                "Already removing a subscription.", ephemeral=True
            )
            return
        self.removing = True
        if not self.subscriptions:
            await interaction.response.send_message(
                "No subscriptions to remove.", ephemeral=True
            )
            return
        dropdown = RemoveDropdown(self.subscriptions, self.on_remove_selected)
        view = discord.ui.View()
        view.add_item(dropdown)
        await interaction.response.send_message(
            "Select a subscription to remove:", view=view, ephemeral=True
        )

    async def on_remove_selected(self, interaction: discord.Interaction, sub_id: str):
        if sub_id == "unknown":
            await interaction.response.send_message(
                "Invalid subscription selected.", ephemeral=True
            )
            return
        with get_session() as session:
            sub = session.query(Subscription).filter_by(id=int(sub_id)).first()
            if not sub:
                await interaction.response.send_message(
                    "Subscription not found.", ephemeral=True
                )
                return
            session.delete(sub)
            session.commit()
        await interaction.response.send_message("Subscription removed.", ephemeral=True)
