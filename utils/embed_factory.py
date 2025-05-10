import discord

class EmbedFactory:
    DEFAULT_TITLE = "Discord Bot"
    AUTHOR_NAME = "Luca"
    AUTHOR_URL = "https://github.com/reewhy"

    @staticmethod
    def create_embed(
            interaction: discord.Interaction = None,
            description: str = "",
            title: str = "",
            thumbnail: str = "",
            colour: discord.Colour = discord.Colour.random(),
        author: bool = True
    ) -> discord.Embed:
        embed = discord.Embed(
            colour=colour,
            title= title or EmbedFactory.DEFAULT_TITLE,
            description=description
        )
        
        if interaction:
            embed.set_footer(text=f"By {interaction.user.name}", icon_url=interaction.user.avatar.url)
        
        if author:
            embed.set_author(name=EmbedFactory.AUTHOR_NAME, url=EmbedFactory.AUTHOR_URL)
        
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)

        return embed
