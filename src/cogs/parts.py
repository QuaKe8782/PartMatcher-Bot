import discord
from discord.ext import commands
from pymongo import MongoClient


class Parts(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    
    @commands.command()
    async def test(self, ctx):
        await ctx.send("test")


def setup(bot):
    bot.add_cog(Parts(bot))