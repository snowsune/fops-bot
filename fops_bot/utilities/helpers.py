import discord
import logging

from utilities.database import (
    get_feature_data,
    set_feature_state,
    is_feature_enabled,
)


async def set_feature_state_helper(
    ctx: discord.Interaction,
    feature_name: str,
    enable: bool,
    channels: list[discord.TextChannel],
    multi_channel: bool = False,
):
    guild_id = ctx.guild.id

    # Just to auto-populate if needed
    is_feature_enabled(guild_id, feature_name, enable)

    # Get the raw data
    raw_feature_data = get_feature_data(guild_id, feature_name)

    # Check if the existing data is None
    current_channels = (
        raw_feature_data.get("feature_variables", "").split(",")
        if raw_feature_data.get("feature_variables") != None
        else []
    )

    # Filter out any empty strings from the channel list
    current_channels = [ch for ch in current_channels if ch.strip() != ""]

    # Handle enabling the feature
    if enable:
        if multi_channel:
            # Append the new channels if they're not already in the list
            new_channel_ids = [
                str(channel.id)
                for channel in channels
                if str(channel.id) not in current_channels
                and str(channel.id).strip() != ""  # Filters out empties
            ]
            updated_channels = current_channels + new_channel_ids
        else:
            # For single-channel features, just take the last one
            updated_channels = [str(channels[0].id)]
        set_feature_state(guild_id, feature_name, True, ",".join(updated_channels))
        await ctx.response.send_message(
            f"{', '.join([f'<#{ch_id}>' for ch_id in updated_channels])} enabled for {feature_name}.",
            ephemeral=True,
        )

    # Handle disabling the feature (removing channels)
    else:
        if multi_channel:
            # Remove the specified channel from the list
            updated_channels = [
                ch_id
                for ch_id in current_channels
                if ch_id not in [str(channel.id) for channel in channels]
            ]

            # All done
            if len(updated_channels) < 1:
                updated_channels = None

            # If all channels are not gone
            if updated_channels != None:
                # Update the feature with the remaining channels
                set_feature_state(
                    guild_id, feature_name, True, ",".join(updated_channels)
                )
                await ctx.response.send_message(
                    f"{', '.join([f'<#{ch_id}>' for ch_id in updated_channels])} still enabled for {feature_name}.",
                    ephemeral=True,
                )
            else:
                # If no channels are left, disable the feature entirely
                set_feature_state(guild_id, feature_name, False, "")
                await ctx.response.send_message(
                    f"No channels remain; {feature_name} has been disabled.",
                    ephemeral=True,
                )
        else:
            # For single-channel features, disabling removes the feature entirely
            set_feature_state(guild_id, feature_name, False, "")
            await ctx.response.send_message(
                f"{feature_name} disabled.",
                ephemeral=True,
            )
