from configparser import ConfigParser
import discord
from discord.ext import commands
from os import listdir
from utils import Embed
from motor.motor_asyncio import AsyncIOMotorClient

config = ConfigParser()
config.read("./config.ini")


bot = commands.Bot(command_prefix=config.get("Bot", "prefix"))


# "botvars"
bot.db = AsyncIOMotorClient(config.get("MongoDB", "connection_string"))
bot.pm_discord = {
    "pm_server": int(config.get("Discord", "pm_server")),
    "verification_channel": int(config.get("Discord", "verification_channel"))
}


production_cogs = []


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="PartMatcher"))


@bot.command(aliases=["re"])
async def reload(ctx, cog_name):
    try:
        bot.reload_extension(f"cogs.{cog_name}")
    except Exception as e:
        embed = Embed(
            title="Error",
            description=f"```{e}```"
        )
        await ctx.send(embed=embed)
        return
    embed = Embed(description=f"Successfully reloaded `cogs.{cog_name}`.")
    await ctx.send(embed=embed)


def main():
    for file in listdir("cogs"):
        if not file.endswith(".py"):
            continue
        filename = file.replace(".py", '')
        if filename in production_cogs:
            continue
        bot.load_extension(f"cogs.{filename}")
        print(f"Loaded cogs.{filename}")
    print("Bot is ready")
    bot.run(config.get("Discord", "token"))


main()
