import discord
from discord.ext import commands
from captcha.image import ImageCaptcha
from string import ascii_lowercase, digits
from random import choice
from concurrent.futures import ThreadPoolExecutor
import asyncio
from utils import Embed
import os
from uuid import uuid1
from utils import Member
from datetime import datetime
from math import ceil


chars = list(ascii_lowercase + digits)
image = ImageCaptcha(fonts=['./fonts/Comic.ttf', "./fonts/OpenSans-Bold.ttf"])


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    def gen_id(self, length):
        return ''.join([choice(chars) for i in range(length)])


    def generate_captcha(self):
        id = self.gen_id(6)
        file_name = self.gen_id(6)
        path = f"captchas/{file_name}.png"
        image.write(id, path)
        return path, id


    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != self.bot.pm_discord["pm_server"]:
            return

        incorrect_attempts = 0
        while True:
            with ThreadPoolExecutor() as pool:
                path, id = await asyncio.get_event_loop().run_in_executor(pool, self.generate_captcha)

            file = discord.File(path, filename=f"{id}.png")

            embed = Embed(
                title="Verification",
                description="Please complete this CAPTCHA to continue."
            )
            embed.set_image(url=f"attachment://{os.path.basename(path)}.png")
            await member.send(file=file, embed=embed)
            os.remove(path)

            def check(m): return not m.guild and m.author == member

            try:
                message = await self.bot.wait_for("message", check=check, timeout=60)
            except asyncio.TimeoutError:
                embed = Embed(
                    title="You've didn't respond in time!",
                    description="You have been kicked from the Discord server. Please rejoin the server if this is a mistake.",
                    colour=discord.Colour.red()
                )
                await member.send(embed=embed)
                await member.kick(reason="Failed CAPTCHA")
                return

            if message.content.lower() == id:
                break
            else:
                incorrect_attempts += 1
                embed = Embed(
                    title="CAPTCHA failed",
                    description=f"You have {3 - incorrect_attempts} attempts left.",
                    colour=discord.Colour.red()
                )
                await message.reply(embed=embed)

            if incorrect_attempts >= 3:
                embed = Embed(
                    title="You've run out of CAPTCHA attempts!",
                    description="You have been kicked from the Discord server. Please rejoin the server if this is a mistake.",
                    colour=discord.Colour.red()
                )
                await member.send(embed=embed)
                await member.kick(reason="Failed CAPTCHA")
                return

        member_role = member.guild.get_role(self.bot.pm_discord["member_role"])
        await member.add_roles(member_role, reason="Completed CAPTCHA")

        embed = Embed(
            title="Success! You have completed the CAPTCHA!",
            description="You have gained access to the rest of the server."
        )
        await message.reply(embed=embed)


    @commands.has_guild_permissions(kick_members=True)
    @commands.command()
    async def warn(self, ctx, member: Member = None, *, reason="No reason provided."):
        if not member:
            embed = Embed(
                title="You need to tell me which member to warn!",
                colour=discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return

        if member.bot:
            embed = Embed(
                title="I can't warn a bot!",
                colour=discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return

        warn_object = {
            "_id": str(uuid1()),
            "user": member.id,
            "mod": ctx.author.id,
            "reason": reason,
            "time": datetime.utcnow()
        }

        await self.bot.db["DiscordBot"]["Warns"].insert_one(warn_object)

        embed = Embed(
            title=f"Warned {member} for:",
            description=reason
        )

        await ctx.reply(embed=embed)

        embed = Embed(
            title="You have been warned in PartMatcher for:",
            description=reason,
            colour=discord.Colour.red()
        )

        await member.send(embed=embed)


    @commands.has_guild_permissions(kick_members=True)
    @commands.group(aliases=["warnings", "getwarns", "showwarns"], invoke_without_command=True)
    async def warns(self, ctx, *, member: Member = None):
        if not member:
            embed = Embed(
                title = "You need to tell me which member's warns to show!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return

        warns = await self.bot.db["DiscordBot"]["Warns"].find({"user": member.id}).to_list(length=50)

        if not warns:
            embed = Embed(
                title=f"{member} has no warns saved."
            )
            await ctx.reply(embed=embed)
            return

        embeds = []

        pages = ceil(len(warns)/5)
        for i in range(pages):
            section_warns = warns[i * 5: i * 5 + 5]
            embed = Embed(
                title=f"Showing warns {i * 5 + 1} - {i * 5 + len(section_warns)} of {len(warns)} for {member}:"
            )

            for warn in section_warns:
                embed.add_field(
                    name=f"Case ID - {warn['_id']}",
                    value=f"""\
**Reason -** {warn["reason"]}
**Moderator -** <@{warn["mod"]}> ({warn["mod"]})
**Time -** {warn["time"].strftime("%c")} UTC
""",                
                    inline = False
                )

            embeds.append(embed)

        current_page = 0
        message = await ctx.reply(embed=embeds[current_page])
        
        while True:
            await message.clear_reactions()

            reaction_list = ["❌"]

            if current_page >= 1:
                reaction_list.append("◀️")

            if current_page < pages:
                reaction_list.append("▶️")

            for reaction in reaction_list:
                await message.add_reaction(reaction)

            check = lambda r, u: r.message == message and u == ctx.author and str(r.emoji) in reaction_list  

            try:
                reaction = await self.bot.wait_for("reaction_add", check=check, timeout=30)
            except asyncio.TimeoutError:
                await message.clear_reactions()
                return

            reaction_emoji = str(reaction[0].emoji)

            if reaction_emoji == "❌":
                await message.clear_reactions()
                return
            
            if reaction_emoji == "◀️":
                current_page -= 1

            elif reaction_emoji == "▶️":
                current_page += 1

            await message.edit(embed=embeds[current_page])


    @warns.command()
    async def transfer(self, ctx, original_member: Member = None, *, new_member: Member = None):
        if not original_member or not new_member:
            embed = Embed(
                title = "You need to provide two members!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return
        
        warns = await self.bot.db["DiscordBot"]["Warns"].update_many({"user": original_member.id}, {"$set": {"user": new_member.id}})

        if warns.modified_count == 0:
            embed = Embed(
                title = f"{original_member} has no warns saved.",
                colour = discord.Colour.red()
            )
        else:
            embed = Embed(title = f"Successfully transferred {warns.modified_count} warn(s) from {original_member} to {new_member}.")
        await ctx.reply(embed=embed)


    @warns.command()
    async def clear(self, ctx, *, member: Member = None):
        if not member:
            embed = Embed(
                title = "You need to tell me which member's warns to clear!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return

        deletions = await self.bot.db["DiscordBot"]["Warns"].delete_many({"user": member.id})

        if deletions.deleted_count == 0:
            embed = Embed(
                title = f"{member} has no warns saved.",
                colour = discord.Colour.red()
            )
        else:
            embed = Embed(title = f"Successfully deleted {deletions.deleted_count} warn(s) from {member}.")
        await ctx.reply(embed=embed)


    @warns.command(aliases=["del", "delwarn"])
    async def delete(self, ctx, case_id):
        warn = await self.bot.db["DiscordBot"]["Warns"].delete_one({"_id": case_id})

        if warn.deleted_count == 0:
            embed = Embed(
                title = "Couldn't find a warn with that case ID.",
                description = "Perhaps you made a typo?",
                colour = discord.Colour.red()
            )
        else:
            embed = Embed(title = "Successfully deleted warn.")
        await ctx.reply(embed=embed)


def setup(bot):
    bot.add_cog(Moderation(bot))
