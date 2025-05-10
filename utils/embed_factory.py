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
            author: str = ""
    ) -> discord.Embed:
        """
        Generator function for discord.Embed.

        Args:
            interaction (discord.Interaction): Discord interaction with user.
            description (str): Embed message description.
            title (str): Embed message title.
            thumbnail (str): URL to set embed thumbnail.
            colour (discord.Colour): Color of the embed.
            author (str): Author of the embed.

        Returns:
            discord.Embed: Generated embed.
        """
        embed = discord.Embed(
            colour=colour,
            title= title or EmbedFactory.DEFAULT_TITLE,
            description=description
        )
        
        if interaction:
            embed.set_footer(text=f"By {interaction.user.name}", icon_url=interaction.user.avatar.url)
        
        if author:
            embed.set_author(name=author or AUTHOR_NAME, url=EmbedFactory.AUTHOR_URL)
        
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)

        return embed
