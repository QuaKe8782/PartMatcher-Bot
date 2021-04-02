import discord
from discord.ext import commands
from pymongo import MongoClient


class Parts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.group(invoke_without_command=True)
    async def partmatcher(self, ctx):
        await ctx.send("test")

    @partmatcher.command()
    async def submit(self, ctx):
        await ctx.send("submit")


def setup(bot):
    bot.add_cog(Parts(bot))
