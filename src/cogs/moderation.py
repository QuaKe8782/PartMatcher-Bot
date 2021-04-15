import discord
from discord.ext import commands
from captcha.image import ImageCaptcha
from string import ascii_lowercase, digits
from random import choice
from concurrent.futures import ThreadPoolExecutor
import asyncio
from utils import Embed
import os
from uuid import uuid4
from utils import Member
from datetime import datetime, timedelta
from math import ceil
from inflect import engine


chars = list(ascii_lowercase + digits)
image = ImageCaptcha(fonts=['./fonts/Comic.ttf', "./fonts/OpenSans-Bold.ttf"])
inf = engine()
 

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.loop.create_task(self.restart_tasks())


    def gen_id(self, length):
        return ''.join([choice(chars) for i in range(length)])


    def generate_captcha(self):
        id = self.gen_id(6)
        file_name = self.gen_id(6)
        path = f"captchas/{file_name}.png"
        image.write(id, path)
        return path, id


    def convert_float(self, num: float):
        if num.is_integer():
            return str(int(num))
        return str(num)


    async def restart_tasks(self):
        await self.bot.wait_until_ready()
        mutes = await self.bot.db["DiscordBot"]["Mutes"].find({"ended": False}).to_list(length=500)
        guild = self.bot.get_guild(self.bot.pm_discord["pm_server"])
        for mute in mutes:
            member = guild.get_member(mute["user"])
            asyncio.create_task(self.handle_mute(mute, member))


    async def handle_mute(self, mute_obj, member: discord.Member):
        muted_role = member.guild.get_role(self.bot.pm_discord["muted_role"])

        while True:
            sleep_time = (mute_obj["end_time"] - datetime.utcnow()).total_seconds()

            await asyncio.sleep(sleep_time)

            mute_obj = await self.bot.db["DiscordBot"]["Mutes"].find_one({"_id": mute_obj["_id"]})

            if mute_obj["end_time"] == "infinite":
                return

            if mute_obj["ended"]:
                return

            if datetime.utcnow() > mute_obj["end_time"]:
                await member.remove_roles(muted_role)
                embed = Embed(title="You have been unmuted.")
                try:
                    await member.send(embed=embed)
                except:
                    pass

                await self.bot.db["DiscordBot"]["Mutes"].update_one({"_id": mute_obj["_id"]}, {"$set": {"ended": True}})
                return


    def format_time(self, total_time):
        time_periods = {
            "s": (1, "second(s)"),
            "m": (60, "minute(s)"),
            "h": (3600, "hour(s)"),
            "d": (86400, "day(s)"),
            "w": (604800, "week(s)")
        }

        time_keys = list(time_periods)

        for count, time_period in enumerate(time_keys):
            if time_periods[time_period][0] > total_time:
                message = self.convert_float(round(total_time / time_periods[time_keys[count - 1]][0], 2)) + ' ' + time_periods[time_keys[count - 1]][1]
                break
            elif time_periods[time_period][0] == total_time:
                message = self.convert_float(round(total_time / time_periods[time_keys[count]][0], 2)) + ' ' + time_periods[time_keys[count]][1]
                break

        return message


    @commands.Cog.listener()
    async def on_member_join(self, member):
        if member.guild.id != self.bot.pm_discord["pm_server"]:
            return

        welcome_channel = member.guild.get_channel(self.bot.pm_discord["welcome_channel"])

        result = await self.bot.db["DiscordBot"]["Users"].find_one({"user": member.id})


        if not result:
            await self.bot.db["DiscordBot"]["Users"].insert_one({"user": member.id, "join_count": 0})
            count = 1
        else:
            count = result["join_count"] + 1

        await self.bot.db["DiscordBot"]["Users"].update_one({"user": member.id}, {"$inc": {"join_count": 1}})

        embed = Embed(
            title = f"{member} joined the server.",
            description = f"This is the {inf.ordinal(count)} time they have joined the server.\n"\
            f"Their account is {(datetime.utcnow() - member.created_at).days} days old."
        )

        embed.set_thumbnail(url=member.avatar_url)
        embed.set_footer(text=f"ID: {member.id}")

        await welcome_channel.send(embed=embed)

        incorrect_attempts = 0
        while True:
            with ThreadPoolExecutor() as pool:
                path, id = await asyncio.get_event_loop().run_in_executor(pool, self.generate_captcha)

            file = discord.File(path, filename=f"{os.path.basename(path)}")

            embed = Embed(
                title="Verification",
                description="Please complete this CAPTCHA to continue."
            )
            embed.set_image(url=f"attachment://{os.path.basename(path)}")
            try:
                await member.send(file=file, embed=embed)
            except:
                pass
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
                try:
                    await message.reply(embed=embed)
                except:
                    pass
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
                try:
                    await message.reply(embed=embed)
                except:
                    pass

            if incorrect_attempts >= 3:
                embed = Embed(
                    title="You've run out of CAPTCHA attempts!",
                    description="You have been kicked from the Discord server. Please rejoin the server if this is a mistake.",
                    colour=discord.Colour.red()
                )
                try:
                    await message.reply(embed=embed)
                except:
                    pass
                await member.kick(reason="Failed CAPTCHA")
                return

        member_role = member.guild.get_role(self.bot.pm_discord["member_role"])
        await member.add_roles(member_role, reason="Completed CAPTCHA")

        embed = Embed(
            title="Success! You have completed the CAPTCHA!",
            description="You have gained access to the rest of the server."
        )
        await message.reply(embed=embed)


    @commands.Cog.listener()
    async def on_member_remove(self, member):
        if member.guild.id != self.bot.pm_discord["pm_server"]:
            return

        welcome_channel = member.guild.get_channel(self.bot.pm_discord["welcome_channel"])

        embed = Embed(title = f"{member} left the server.",)
        embed.set_footer(text=f"ID: {member.id}")
        embed.set_thumbnail(url=member.avatar_url)

        await welcome_channel.send(embed=embed)


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
            "_id": str(uuid4()),
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
        embed.set_author(name=ctx.author, icon_url=ctx.author.avatar_url)

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
            embed = Embed()
            embed.set_author(
                name = f"Showing warns {i * 5 + 1} - {i * 5 + len(section_warns)} of {len(warns)} for {member}:",
                icon_url = member.avatar_url
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
                embed.set_footer(text=f"ID: {member.id}")


            embeds.append(embed)

        current_page = 0
        message = await ctx.reply(embed=embeds[current_page])
        
        while True:
            await message.clear_reactions()

            reaction_list = ["❌"]

            if current_page >= 1:
                reaction_list.append("◀️")

            if current_page < pages - 1:
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


    @commands.has_guild_permissions(kick_members=True)
    @commands.command()
    async def kick(self, ctx, member: Member = None, *, reason = "No reason provided."):
        if not member:
            embed = Embed(
                title = "You need to tell me which member to kick!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return
        
        if not ctx.me.top_role > member.top_role:
            embed = Embed(
                title = "I can't kick that user!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return

        embed = Embed(
            title = "You have been kicked from PartMatcher for:",
            description = reason,
            colour = discord.Colour.red()
        )
        await member.send(embed=embed)

        await member.kick(reason=reason)

        embed = Embed(
            title = f"Successfully kicked {member} for:",
            description = reason,
            colour = discord.Colour.red()
        )

        await ctx.reply(embed=embed)
        

    @commands.has_guild_permissions(ban_members=True)
    @commands.command()
    async def ban(self, ctx, member: Member = None, *, reason = "No reason provided."):
        if not member:
            embed = Embed(
                title = "You need to tell me which member to ban!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return
        
        if not ctx.me.top_role > member.top_role:
            embed = Embed(
                title = "I can't ban that user!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return

        embed = Embed(
            title = "You have been banned from PartMatcher for:",
            description = reason,
            colour = discord.Colour.red()
        )
        await member.send(embed=embed)

        await member.ban(reason=reason)

        embed = Embed(
            title = f"Successfully banned {member} for:",
            description = reason,
            colour = discord.Colour.red()
        )

        await ctx.reply(embed=embed)


    @commands.has_guild_permissions(ban_members=True)
    @commands.command()
    async def hackban(self, ctx, user_id = None):
        if not user_id:
            embed = Embed(
                title = "You need to tell me the user ID of the member to hackban!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return

        try:
            user = await self.bot.fetch_user(user_id)
        except (discord.errors.NotFound, discord.errors.HTTPException):
            embed = Embed(
                title = f"{user_id} is not a valid user ID!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return
            
        guild = self.bot.get_guild(self.bot.pm_discord["pm_server"])

        try:
            await guild.ban(discord.Object(id=user_id))
        except discord.errors.NotFound:
            embed = Embed(
                title = "That user is already banned!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return

        embed = Embed(title = f"Successfully hackbanned {user}.")
        await ctx.reply(embed=embed)


    @commands.command()
    @commands.has_guild_permissions(ban_members=True)
    async def unban(self, ctx, user_id = None):
        if not user_id:
            embed = Embed(
                title = "You need to tell me the user ID of the member to unban!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return

        try:
            user = await self.bot.fetch_user(user_id)
        except (discord.errors.NotFound, discord.errors.HTTPException):
            embed = Embed(
                title = f"{user_id} is not a valid user ID!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return
            
        guild = self.bot.get_guild(self.bot.pm_discord["pm_server"])

        try:
            await guild.unban(discord.Object(id=user_id))
        except discord.errors.NotFound:
            embed = Embed(
                title = "That user is not banned!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return

        embed = Embed(title = f"Successfully unbanned {user}.")
        await ctx.reply(embed=embed)


    @commands.command()
    @commands.has_guild_permissions(kick_members=True)
    async def mute(self, ctx, member: Member = None, *mute_periods):
        if not member:
            embed = Embed(
                title = "You need to tell me who to mute!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return

        time_periods = {
            "s": 1,
            "m": 60,
            "h": 3600,
            "d": 86400,
            "w": 604800,
        }
        
        if mute_periods:
            total_time = 0
            for time in mute_periods:
                time_period = time[-1]

                if not time_period in time_periods:
                    embed = Embed(
                        title = "Couldn't parse time value!",
                        description = f"Please format your command like so:\n```{self.bot.command_prefix}mute QuaKe 1d 12h```"
                    )
                    await ctx.reply(embed=embed)
                    return
                
                try:
                    num = float(time.strip("smhdw"))
                except ValueError:
                    embed = Embed(
                        title = "Couldn't parse time value!",
                        description = f"Please format your command like so:\n```{self.bot.command_prefix}mute QuaKe 1d 12h```"
                    )
                    await ctx.reply(embed=embed)
                    return

                total_time += num * time_periods[time_period]  

        if total_time < 1:
            embed = Embed(
                title = "The amount of time muted must be at least 1 second!",
                colour=discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return


        if total_time > 604800:
            embed = Embed(
                title = "The maximum amount of mute time is 1 week!",
                colour=discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return


        mute = await self.bot.db["DiscordBot"]["Mutes"].find_one({"user": member.id, "ended": False})

        message = self.format_time(total_time)

        # checks if member is already muted
        if mute:
            if not mute_periods:
                new_time = "infinite"
                embed = Embed(title = f"{member} has been muted until further notice.")
            else:
                new_time = mute["end_time"] + timedelta(seconds=total_time)
                embed = Embed(title=f"{member}'s mute has been extended by {message}.")

            await self.bot.db["DiscordBot"]["Mutes"].update_one({"_id": mute["_id"]}, {"$set": {"end_time": new_time}})

            await ctx.reply(embed=embed)

            return

        mute_object = {
            "_id": str(uuid4()),
            "user": member.id,
            "mod": ctx.author.id,
            "start_time": datetime.utcnow(),
            "end_time": (datetime.utcnow() + timedelta(seconds=total_time)) if mute_periods else "infinite",
            "ended": False
        }

        guild = self.bot.get_guild(self.bot.pm_discord["pm_server"])
        muted_role = guild.get_role(self.bot.pm_discord["muted_role"])

        await member.add_roles(muted_role)
        await self.bot.db["DiscordBot"]["Mutes"].insert_one(mute_object)

        if not mute_periods:
            embed = Embed(title = f"{member} has been muted until further notice.")
            await ctx.reply(embed=embed)

            embed = Embed(title = f"You have been muted until further notice.")
            await member.send(embed=embed)
            return

        asyncio.create_task(self.handle_mute(mute_object, member))

        embed = Embed(title = f"You have been muted for {message}.")
        await member.send(embed=embed)

        embed = Embed(title=f"{member} has been muted for {message}.") 
        await ctx.reply(embed=embed)


    @commands.command()
    @commands.has_guild_permissions(ban_members=True)
    async def unmute(self, ctx, *, member: Member = None):
        if not member:
            embed = Embed(
                title = "You need to tell me who to unmute!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return

        update_query = await self.bot.db["DiscordBot"]["Mutes"].update_one({"user": member.id, "ended": False}, {"$set": {"ended": True}})


        if not update_query.modified_count:
            embed = Embed(
                title = "That member is not muted!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return

        muted_role = ctx.guild.get_role(self.bot.pm_discord["muted_role"])
        await member.remove_roles(muted_role)

        embed = Embed(title="You have been unmuted.")
        await member.send(embed=embed)

        embed = Embed(title=f"Unmuted {member}.")
        await ctx.reply(embed=embed)


    @commands.command()
    @commands.has_guild_permissions(ban_members=True)
    async def mutes(self, ctx, *, member: Member):
        if not member:
            embed = Embed(
                title = "You need to tell me which member's mutes to show!",
                colour = discord.Colour.red()
            )
            await ctx.reply(embed=embed)
            return

        mutes = await self.bot.db["DiscordBot"]["Mutes"].find({"user": member.id}).to_list(length=50)

        if not mutes:
            embed = Embed(title=f"{member} has no mutes saved.")
            await ctx.reply(embed=embed)
            return

        embed = Embed()
        embed.set_author(name=f"Mutes for {member}:", icon_url=member.avatar_url)

        for mute in mutes:
            total_time = (mute["end_time"] - mute["start_time"]).total_seconds()

            message = self.format_time(total_time)

            embed.add_field(
                name = mute["start_time"].strftime("%c"),
                value = f"""\
    **Moderator:** <@{mute["mod"]}>
    **Duration:** {message}"""
            )
        embed.set_footer(text=f"ID: {member.id}")

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(Moderation(bot))
