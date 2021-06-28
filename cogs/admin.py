import discord
from discord.ext import commands
from io import BytesIO
import requests
from os import path
from uuid import uuid4
from PIL import Image


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    

    def get_image(self, url):
        try:
            response = requests.get(url)
        except requests.exceptions.ConnectionError:
            return None, None

        image_bytes = BytesIO(response.content)
        image_id = str(uuid4())
        image_filename = f"{image_id}{path.splitext(url)[1].split('?')[0]}"

        # image downscaling code: makes sure images aren't too high resolution
        img = Image.open(image_bytes)
        downscale_size = 1024, 1024

        img.thumbnail(downscale_size, Image.ANTIALIAS)

        byte_array = BytesIO()
        img.save(byte_array, format=img.format)
        out_bytes = byte_array.getvalue()

        return out_bytes, image_filename


    @commands.has_guild_permissions(kick_members=True)
    @commands.command()
    async def sendimage(self, ctx, filename):
        try:
            image_bytes = await self.bot.grid.open_download_stream_by_name(filename)
        except Exception as e:
            await ctx.send(f"```{str(e)}```")
        image = BytesIO(await image_bytes.read())
        await ctx.send(file=discord.File(fp=image, filename=filename))


    @commands.has_guild_permissions(kick_members=True)
    @commands.command()
    async def saveimage(self, ctx):
        image_urls = [attachment.url for attachment in ctx.message.attachments if getattr(attachment, "width")]
        if not image_urls:
            return

        for image in image_urls:
            image_bytes, image_filename = self.get_image(image)
            await self.bot.grid.upload_from_stream(image_filename, image_bytes)
            await ctx.send(f"`{image_filename}`")


def setup(bot):
    bot.add_cog(Admin(bot))
