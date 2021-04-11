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
                title = "Verification",
                description = "Please complete this CAPTCHA to continue."
            )
            embed.set_image(url=f"attachment://{os.path.basename(path)}.png")
            await member.send(file=file, embed=embed)
            os.remove(path)

            check = lambda m: not m.guild and m.author == member

            try:
                message = await self.bot.wait_for("message", check=check, timeout=60)
            except asyncio.TimeoutError:
                embed = Embed(
                    title = "You've didn't respond in time!",
                    description = "You have been kicked from the Discord server. Please rejoin the server if this is a mistake.",
                    colour = discord.Colour.red()
                )
                await member.send(embed=embed)
                await member.kick(reason="Failed CAPTCHA")
                return

            if message.content.lower() == id:
                break
            else:
                incorrect_attempts += 1
                embed = Embed(
                    title = "CAPTCHA failed",
                    description = f"You have {3 - incorrect_attempts} attempts left.",
                    colour = discord.Colour.red()
                )
                await message.reply(embed=embed)
            
            if incorrect_attempts >= 3:
                embed = Embed(
                    title = "You've run out of CAPTCHA attempts!",
                    description = "You have been kicked from the Discord server. Please rejoin the server if this is a mistake.",
                    colour = discord.Colour.red()
                )
                await member.send(embed=embed)
                await member.kick(reason="Failed CAPTCHA")
                return

        member_role = member.guild.get_role(self.bot.pm_discord["member_role"])
        await member.add_roles(member_role, reason="Completed CAPTCHA")

        embed = Embed(
            title = "Success! You have completed the CAPTCHA!",
            description = "You have gained access to the rest of the server."
        )
        await message.reply(embed=embed)


    @commands.has_guild_permissions(kick_members=True)
    @commands.command()
    async def warn(self, ctx, member: Member = None, reason="No reason provided."):
        if not member:
            embed = Embed(
                title = "You need to tell me who to warn!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)

        warn_object = {
            "_id": str(uuid1()),
            "user": member.id,
            "mod": ctx.author.id,
            "reason": reason,
            "time": datetime.utcnow()
        }

        await self.bot.db["DiscordBot"]["Warns"].insert_one(warn_object)

        embed = Embed(
            title = f"Warned {member} for:",
            description = reason
        )

        await ctx.reply(embed=embed)

        embed = Embed(
            title = "You have been warned in PartMatcher for:",
            description = reason,
            colour = discord.Colour.red()
        )

        await member.send(embed=embed)


    @commands.command(aliases=["warnings", "getwarns", "showwarns"])
    async def warns(self, ctx, member: Member):
        pass


def setup(bot):
    bot.add_cog(Moderation(bot))
