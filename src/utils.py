import discord


class Embed(discord.Embed):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not kwargs.get("colour"):
            self.colour = discord.Colour(0x14d18c)


class UserCancel(Exception):
    pass


class MessageTimeout(Exception):
    pass
