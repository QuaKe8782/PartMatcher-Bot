import discord
from discord.ext import commands
from captcha.image import ImageCaptcha
from string import ascii_lowercase, digits
from random import choice
from concurrent.futures import ThreadPoolExecutor
import asyncio
from utils import Embed
from os import remove


chars = list(ascii_lowercase + digits)
image = ImageCaptcha(fonts=['./fonts/Comic.ttf', "./fonts/OpenSans-Bold.ttf"])


class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    def gen_id(self, length):
        return ''.join([choice(chars) for i in range(length)])


    def generate_captcha(self):
        id = self.gen_id(6)
        path = f'captchas/{id}.png'
        image.write(id, path)
        return path, id


    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != self.bot.pm_discord["pm_server"]:
            return
        with ThreadPoolExecutor() as pool:
            path, id = await asyncio.get_event_loop().run_in_executor(pool, self.generate_captcha)
        
        file = discord.File(path, filename=f"{id}.png")

        embed = Embed(
            title = "Verification",
            description = "Plase complete this CAPTCHA to continue."
        )
        embed.set_image(url=f"attachment://{id}.png")
        await member.send(file=file, embed=embed)
        remove(path)


def setup(bot):
    bot.add_cog(Moderation(bot))
