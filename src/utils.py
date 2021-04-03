import discord

class Embed(discord.Embed):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.colour = discord.Colour(0x14d18c)