# FOSNHU
# 2022, Fops Bot
# MIT License


from types import NoneType
import discord
import logging

from discord.ext import commands


class SelfAssignRoleCog(commands.Cog, name="Roles"):
    def __init__(self, bot):
        self.bot = bot

        # These should be defined maybe in a yaml somewhere else
        self.self_assignable_roles = [
            "On Campus",
            "Remote",
            "Vulpes",
            "Canis lupus familiaris",
            "Canis lupus" "Feline",
        ]

    @commands.command()
    async def addroles(self, ctx, *args, member: discord.Member = None):
        """
        Adds a user to a self assignable role.

        ex: ^addroles "Feline"

        Written by Joe.
        """

        # Adds a user to a subteam
        logging.info(args)
        roles = args
        role_objects = []
        user = ctx.message.author

        logging.info(f"Attempting to add user to {roles}")

        if all(item in self.self_assignable_roles for item in roles):
            for role in roles:
                logging.info(f"Searching for role {role}...")
                d_role = discord.utils.get(ctx.message.guild.roles, name=role)
                role_objects.append(d_role)

                logging.info(f"Found {d_role} for role {role}!")

            await user.add_roles(*role_objects)
            await ctx.send(f"You've been added to the following roles: {roles}")
        else:
            await ctx.send(
                f"Invalid role name or unassignable role (make sure you spelt it correctly, and used qoutes, ie: `{self_assignable_roles[0]}` or `{self_assignable_roles[2]}`) Role was: {roles}"
            )

    @commands.command()
    async def removeroles(self, ctx, *args, member: discord.Member = None):
        """
        Removes a user from a role (or roles),

        ex: ^removeroles "Canis lupus"

        Written by Joe.
        """

        # Adds a user to a group
        roles = args[1:]
        role_objects = []
        user = ctx.message.author
        if all(item in self.self_assignable_roles for item in roles):
            for role in roles:
                role_objects.append(
                    discord.utils.get(ctx.message.guild.roles, name=role)
                )

            await user.remove_roles(*role_objects)
            await ctx.send(f"You've been removed from the following roles: {roles}")
        else:
            await ctx.send(
                f"Invalid role name or unassignable role (make sure you spelt it correctly, and used qoutes, ie: `{self_assignable_roles[0]}` or `{self_assignable_roles[2]}`) Role was: {roles}"
            )

    @commands.command()
    async def listroles(self, ctx, *args, member: discord.Member = None):
        """
        Lists the possible roles.

        ex: ^listroles

        Written by Joe.
        """

        # Random chance to rick-roll
        if await self.bot.rick(ctx):
            return

        rolestr = ""
        for role in self.self_assignable_roles:
            rolestr += f"`{role}`, "
        await ctx.send(f"The possible roles are: {rolestr}")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        await ctx.send(f"Error! {error}")

        raise error


def setup(bot):
    bot.add_cog(SelfAssignRoleCog(bot))
