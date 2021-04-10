import discord
from discord.ext import commands
from utils import Embed, MessageTimeout, UserCancel
from json import load
import asyncio
from random import choice
from string import ascii_letters, digits
from datetime import datetime, timedelta


with open("part_spec_models.json") as file:
    part_spec_models = load(file)

input_types = {
    "string": "A single value.",
    "list": "A group of values seperated by a comma."
}

keywords = {
    "skip | next": "Skips the current input field and moves on to the next one.",
    "stop | exit | cancel": "Cancels the submission process."
}

chars = list(ascii_letters + digits)


class PartInput(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(self.restart_tasks())


    async def restart_tasks(self):
        await self.bot.wait_until_ready()
        submissions = self.bot.db["DiscordBot"]["Submissions"].find({})
        guild = self.bot.get_guild(self.bot.pm_discord["pm_server"])
        channel = guild.get_channel(self.bot.pm_discord["verification_channel"])
        for sub in await submissions.to_list(length=1000):
            message = await channel.fetch_message(sub["message_id"])
            await self.handle_submission(message, sub)


    def gen_id(self, length):
        return ''.join([choice(chars) for i in range(length)])


    def get_reaction_counts(self, message_obj: discord.Message, *reactions):
        result_dict = {}
        
        for reaction in message_obj.reactions:
            str_reaction = str(reaction.emoji)
            if str_reaction not in reactions:
                continue
            result_dict[str_reaction] = reaction.count

        return result_dict


    async def submit_part(self, part_dict):
        while True:
            new_id = self.gen_id(6)
            if not await self.bot.db["PartsDB"]["Parts"].find_one({"part_id": new_id}):
                part_dict["part_id"] = new_id
                part_dict.pop("message_id", None)
                await self.bot.db["PartsDB"]["Parts"].insert_one(part_dict)
                break
        return new_id


    def get_verified_count(self, role_id: int, guild: discord.Guild):
        return len(guild.get_role(role_id).members)


    def is_accepted(self, message_obj: discord.Message):
        reaction_counts = self.get_reaction_counts(message_obj, "✅", "❌")

        verified_count = self.get_verified_count(self.bot.pm_discord["verified_role"], message_obj.guild)

        submission_points = 0
        point_value = 200 / verified_count

        submission_points += point_value * reaction_counts["✅"]
        submission_points -= point_value * reaction_counts["❌"] * 0.75

        return submission_points >= 100


    async def handle_submission(self, message_obj: discord.Message, part_dict: dict):
        async def check_accepted():
            updated_message_obj = await message_obj.channel.fetch_message(message_obj.id)
            if not self.is_accepted(updated_message_obj):
                embed = Embed(title="Submission declined.", colour=discord.Colour.red())
            else:
                embed = Embed(title="Submission accepted.")
                await self.submit_part(part_dict)
            await self.bot.db["DiscordBot"]["Submissions"].delete_one({"part_id": part_dict["part_id"]})
            await message_obj.reply(embed=embed)

            return
        
        now = datetime.utcnow()

        submission_time = part_dict["_created_at"] + timedelta(days=3)

        if submission_time < now:
            await check_accepted()
            return

        await asyncio.sleep((submission_time - now).total_seconds())

        await check_accepted()


    async def assign(self, assign_dict, assign_key, ctx):
        assign_object = {}

        if assign_dict[assign_key].get("_note"):
            embed = Embed(
                title="Note", description=assign_dict[assign_key]["_note"],
                colour=discord.Colour.red()
            )
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

            def check(m): return m.author == ctx.author and m.channel == ctx.channel

            try:
                message = await self.bot.wait_for("message", check=check, timeout=60)
            except asyncio.TimeoutError:
                embed = Embed(title="You took too long to respond! Cancelling submit request.")
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
            description=' '.join([f"`{part}`" for part in part_spec_models if not part.startswith("_")])
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

        embed = Embed(
            title = "Submission Keywords",
            description = '\n'.join([f"`{', '.join(keyword.split(' | '))}` - {description}" for keyword, description in keywords.items()]),
            colour = discord.Colour.red()
        )
        await ctx.send(embed=embed)

        await asyncio.sleep(3)

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
        new_part["Type"] = variation

        for key in new_part:
            if key.startswith("_"):
                continue

            if isinstance(new_part[key], str):
                value = new_part[key]
            elif isinstance(new_part[key], list):
                value = '\n'.join(new_part[key])
            elif isinstance(new_part[key], dict):
                value = '\n'.join([f"• **{spec_key}:** {spec_value}" for spec_key, spec_value in new_part[key].items()])

            embed.add_field(name=key, value=value, inline=False)
    
        embed.set_footer(text="Send 'confirm' in the chat in the next 60 seconds to confirm your submission.")

        message = await ctx.reply(embed=embed)

        check = lambda m: m.author == ctx.author and m.channel == ctx.channel and m.content.lower() == "confirm"

        try:
            await self.bot.wait_for("message", check=check, timeout=60)
        except asyncio.TimeoutError:
            embed = Embed(title="Submission timed out.", description="You failed to respond within 60 seconds.")
            await message.edit(embed=embed)

        new_part["_created_at"] = datetime.utcnow()

        server = self.bot.get_guild(self.bot.pm_discord["pm_server"])
        channel = server.get_channel(self.bot.pm_discord["verification_channel"])

        embed.set_author(name=ctx.message.author, icon_url=ctx.message.author.avatar_url)
        embed.title = f"{variation} Submission"
        embed.set_footer(text="")

        message = await channel.send(embed=embed)

        for reaction in ("✅", "❌"):
            await message.add_reaction(reaction) 

        while True:
            new_id = self.gen_id(6)
            if not await self.bot.db["PartsDB"]["Parts"].find_one({"part_id": new_id}):
                new_part["part_id"] = new_id
                break

        new_part["message_id"] = message.id
        await self.bot.db["DiscordBot"]["Submissions"].insert_one(new_part)

        await asyncio.create_task(self.handle_submission(message, new_part))


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


    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload):
        if payload.channel_id != self.bot.pm_discord["verification_channel"]:
            return
        if payload.user_id == self.bot.user.id:
            return
        guild = self.bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        channel = guild.get_channel(payload.channel_id)
        message = await channel.fetch_message(payload.message_id)

        verified = guild.get_role(self.bot.pm_discord["verified_role"])

        if verified not in member.roles:
            await message.remove_reaction(payload.emoji, payload.member)


def setup(bot):
    bot.add_cog(PartInput(bot))
