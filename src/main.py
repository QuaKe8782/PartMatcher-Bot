from configparser import ConfigParser
import discord
from discord.ext import commands
from os import listdir


config = ConfigParser()
config.read("./config.ini")

prefix = config.get("Bot", "prefix")

bot = commands.Bot(command_prefix=prefix)
production_cogs = []


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="PartMatcher"))


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
