import discord
from discord.ext import commands
from utils import Embed


class Help(commands.HelpCommand):
    async def send_bot_help(self, mapping):
        embed = Embed(title="Help")
        for cog, commands in mapping.items():
            filtered_commands = set(await self.filter_commands(commands, sort=True))
            if not filtered_commands:
                continue
            embed.add_field(
                name=getattr(cog, "qualified_name", "No Category"),
                value=', '.join(
                    f"`{command.name}`" for command in filtered_commands),
                inline=False
            )
        await self.context.send(embed=embed)

    async def send_command_help(self, command):
        embed = Embed(title=f"Help - '{command.name}' command")
        embed.add_field(
            name="Description",
            value=f"{command.description if command.description else 'No description provided.'}",
            inline=False
        )
        embed.add_field(
            name="Usage",
            value=f"```{self.get_command_signature(command)}```",
            inline=False
        )

        await self.context.send(embed=embed)

    async def send_group_help(self, group):
        commands = [group] + list(group.commands)

        embed = Embed(title=f"Help - '{group.name}' group")

        for command in commands:
            embed.add_field(
                name=self.get_command_signature(command),
                value=command.description if command.description else "No description provided.",
                inline=False
            )

        await self.context.send(embed=embed)

    async def send_cog_help(self, cog):
        embed = Embed(title=f"Help - '{getattr(cog, 'qualified_name', 'No Category')}' cog")

        embed.add_field(
            name="Commands",
            value=', '.join([f"`{command.name}`" for command in cog.get_commands()])
        )

        await self.context.send(embed=embed)
