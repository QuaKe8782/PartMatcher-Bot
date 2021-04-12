from configparser import ConfigParser
import discord
from discord.ext import commands
from os import listdir
from utils import Embed
from motor.motor_asyncio import AsyncIOMotorClient
import traceback
import asyncio


config = ConfigParser()
config.read("./config.ini")


intents = discord.Intents.all()
bot = commands.Bot(command_prefix=config.get("Bot", "prefix"), intents=intents)


# "botvars"
bot.db = AsyncIOMotorClient(config.get("MongoDB", "connection_string"))
bot.pm_discord = {
    "pm_server": int(config.get("Discord", "pm_server")),
    "verified_role": int(config.get("Discord", "verified_role")),
    "verification_channel": int(config.get("Discord", "verification_channel")),
    "member_role": int(config.get("Discord", "member_role"))
}


production_cogs = []


async def report_error(ctx, error):
    embed = Embed(
        title = "Error",
        description = f"```{''.join(traceback.TracebackException.from_exception(error).format())[:2000]}```"
    )

    await ctx.send(embed=embed)

    raise error


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandInvokeError):
        error = error.original
        if isinstance(error, discord.errors.Forbidden):
            return
        await report_error(ctx, error)
    if isinstance(error, commands.MemberNotFound):
        embed = Embed(
            title = "Member Not Found",
            description = "Unable to find that member. Perhaps you made a typo?",
            colour = discord.Colour.red()
        )
        await ctx.reply(embed=embed)
        return
    if isinstance(error, commands.MissingPermissions):
        embed = Embed(
            title = "Missing Permissions",
            description = "You don't have the permissions necessary to use that command!",
            colour = discord.Colour.red()
        )
        await ctx.reply(embed=embed)
        return
    await report_error(ctx, error)

async def send_rules_and_roles():
    server = bot.get_guild(809900131494789120)
    channel = server.get_channel(827817671252508672)

    roles = {
        810130205209264139: "PartMatcher Developers who work on the site and infrastructure.",
        810793565319069736: "People who moderate chats and members to ensure everybody is following the rules.",
        827947939472867371: "Server bots. Includes the official PartMatcher bot.",
        830570385141268481: "Members who have contributed to PartMatcher's code on GitHub.",
        810130497485275166: "PartMatcher approved tech enthusiasts who vote on part submissions/edits and suggest improvements.",
        830570099928596512: "PartMatcher approved content creators on YouTube and other platforms who create high quality tech/gaming content and have a decently sized following.",
        810274283367432264: "Members of the server who can chat and speak."
    }

    rules = [
        "No overly spamming messages, reactions, emojis, images etc...",
        "Use channels for what they are meant for. Keep bot commands to the bot channels unless they're part of the conversation.",
        "No trolling or toxicity. Be respectful to other server members, and don't harass people."
        "No posting or referencing NSFW/NSFL content. You will be banned on sight if your username or avatar is NSFW.",
        "No discussing politics or religion. These are controversial topics that are best not discussed in a tech Discord server.",
        "No discriminating other people because of their race, religion, gender, sexual orientation etc... No use of discriminatory slurs.",
        "No ban/mute evading with alt accounts or other means.",
        "No doxxing.",
        "No begging for roles. This will only make it harder for you to obtain them.",
        "No advertising. You are allowed to link YouTube videos, for example, if it relates to the conversation. Other advertising must be done in the Content Creator channels, where you can DM a mod for them to post it there.",
        "Always think twice before doing something and use common sense.",
        "Moderators get final say. If you disagree with a decision, take the argument to DMs rather than letting it spill out in the server.",
        "Follow Discord's [Terms of Service](https://discord.com/terms) and the [Community Guidelines](https://discord.com/guidelines)."
    ]

    links = {
        "Permanent Invite Link": "https://discord.gg/TfVdDQcHKb"
    }

    embeds = [
        Embed(
            title = "PartMatcher Discord Rules",
            description = '\n\n'.join([f"**{count + 1}**. {rule}" for count, rule in enumerate(rules)])
        ),
        Embed(
            title = "PartMatcher Discord Roles",
            description = '\n\n'.join([f"**<@&{role}> -** {roles[role]}" for role in roles])
        ),
        Embed(
            title = "PartMatcher Links",
            description = '\n\n'.join([f"[{link}]({links[link]})" for link in links])
        )
    ]

    for embed in embeds:
        await channel.send(embed=embed)


@bot.event
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="PartMatcher"))
    # await send_rules_and_roles()


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
