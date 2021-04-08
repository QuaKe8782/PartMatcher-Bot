import discord
from discord.ext import commands
from utils import Embed, MessageTimeout, UserCancel
from json import load
import asyncio
from random import choice
from string import ascii_letters, digits
from datetime import datetime


with open("part_spec_models.json") as file:
    part_spec_models = load(file)

input_types = {
    "string": "A single value.",
    "list": "A group of values seperated by a comma."
}

chars = list(ascii_letters + digits)


class PartInput(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    def gen_id(self, length):
        return ''.join([choice(chars) for i in range(length)])


    async def assign(self, assign_dict, assign_key, ctx):
        assign_object = {}

        if assign_dict[assign_key].get("_note"):
            embed = Embed(
                title="Note", description=assign_dict[assign_key]["_note"])
            await ctx.reply(embed=embed)
            await asyncio.sleep(3)

        for category in assign_dict[assign_key]:
            if category.startswith("_"):
                continue

            expected_value = assign_dict[assign_key][category]
            examples = []

            if isinstance(expected_value, str):
                input_type = "string"
                for example in expected_value.split(" | "):
                    examples.append(example)
            elif isinstance(expected_value, list):
                input_type = "list"
                examples.append(', '.join(expected_value))
            else:
                raise ValueError("Invalid example value!")

            embed = Embed(title=f"Category - {category}")

            embed.add_field(
                name="Input Type",
                value=f"`{input_type}` - {input_types[input_type]}",
                inline=False
            )

            embed.add_field(
                name="Example(s)",
                value='\n'.join([f"`{example}`" for example in examples]),
                inline=False
            )

            prev_message = await ctx.reply(embed=embed)

            def check(
                m): return m.author == ctx.author and m.channel == ctx.channel

            try:
                message = await self.bot.wait_for("message", check=check, timeout=60)
            except asyncio.TimeoutError:
                embed = Embed(
                    title="You took too long to respond! Cancelling submit request.")
                await ctx.reply(embed=embed)
                raise MessageTimeout()

            await prev_message.delete()

            if message.content.lower() in ("stop", "exit", "cancel", "terminate", "break", "arrêter"):
                embed = Embed(title="Cancelled part submission")
                await ctx.reply(embed=embed)
                raise UserCancel()

            if message.content.lower() in ("continue", "skip", "next"):
                assign_object[category] = "?"
                continue

            assign_object[category] = message.content

        return assign_object


    @commands.group(invoke_without_command=True, aliases=["pm"], description="Lists all PartMatcher commands.")
    async def partmatcher(self, ctx):
        embed = Embed(
            title="PartMatcher Commands",
            description='\n'.join(
                [f"`{command.name}{' ' + command.signature if command.signature else ''}` - {command.description if command.description else '(No description provided)'}" for command in self.partmatcher.commands])
        )
        await ctx.send(embed=embed)


    @partmatcher.command(description="Submit a part for verification.")
    async def submit(self, ctx):
        embed = Embed(
            title="What part type would you like to submit?",
            description=' '.join(
                [f"`{part}`" for part in part_spec_models if not part.startswith("_")])
        )
        def check(m): return m.author == ctx.author and m.channel == ctx.channel

        prev_msg = await ctx.reply(embed=embed)
        embed.title = "That's is not a valid part type! Please choose from the below types."

        waiting = True
        while True:
            try:
                message = await self.bot.wait_for("message", check=check, timeout=30)
            except asyncio.TimeoutError:
                embed = Embed(
                    title="You took too long to respond! Cancelling submit request.")
                await ctx.reply(embed=embed)
                return

            for variation in (message.content.capitalize(), message.content.title(), message.content.upper()):
                if variation in part_spec_models:
                    waiting = False
                    break

            if not waiting:
                break

            await prev_msg.delete()
            prev_msg = await message.reply(embed=embed)

        for count, key in enumerate(("_part", variation)):
            try:
                if count == 0:
                    new_part = await self.assign(part_spec_models, key, ctx)
                else:
                    new_part["Specs"] = await self.assign(part_spec_models, key, ctx)
            except (UserCancel, MessageTimeout):
                return

        embed = Embed(title="Part Selection Completed")

        new_part["Specs"].pop("_note", None)

        for key in new_part:
            if key.startswith("_"):
                continue

            if isinstance(new_part[key], str):
                value = new_part[key]
            elif isinstance(new_part[key], list):
                value = '\n'.join(new_part[key])
            elif isinstance(new_part[key], dict):
                value = '\n'.join([f"**{spec_key}**: {spec_value}" for spec_key, spec_value in new_part[key].items()])

            embed.add_field(name=key, value=value, inline=False)
    
        embed.set_footer(text="Send 'confirm' in the chat in the next 60 seconds to confirm your submission.")

        message = await ctx.reply(embed=embed)

        check = lambda m: m == ctx.author and m.channel == ctx.channel and m.content.lower() == "confirm"

        try:
            await self.bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            embed = Embed(title="Submission timed out.", description="You failed to respond within 60 seconds.")
            await message.edit(embed=embed)

        new_part["Type"] = variation
        new_part["_created_at"] = datetime.utcnow()
        new_part["_contributors"].append(ctx.author.id)


        server = self.bot.get_guild(self.bot.pm_discord["pm_server"])
        channel = server.get_channel(self.bot.pm_discord["verification_channel"])


        embed.set_author(name=ctx.message.author, icon_url=ctx.message.author.avatar_url)
        embed.title = "Part Submission"

        while True:
            new_id = self.gen_id(6)
            if not await self.bot.db["DiscordBot"]["Submissions"].find_one({"part_id": new_id}):
                new_part["part_id"] = new_id
                await self.bot.db["DiscordBot"]["Submissions"].insert_one(new_part)
            
                break


    @partmatcher.command()
    async def info(self, ctx, *, search_term):
        query = list(await self.bot.db["PartsDB"]["Parts"].find({"$text": {"$search": search_term}}))

        if not query:
            embed = Embed(
                title = f"No results found for '{search_term}'",
                description = "Perhaps you made a typo?"
            )

        else:
            embed = Embed(
                title = f"Results for '{search_term}':",
                description = '\n'.join([part["name"] for part in query])
            )

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(PartInput(bot))
