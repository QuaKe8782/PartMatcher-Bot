import discord
from discord.ext import commands
from pymongo import MongoClient


class Parts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


    @commands.group(invoke_without_command=True, aliases=["pm"], description="Lists all PartMatcher commands.")
    async def partmatcher(self, ctx):
        pass


    @partmatcher.command(description="Submit a part for verification.")
    async def submit(self, ctx):
        await ctx.send("submit")


def setup(bot):
    bot.add_cog(Parts(bot))
