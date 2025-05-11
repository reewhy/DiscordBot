import discord
from datetime import datetime

class EmbedFactory:
    """
    A factory class for generating visually appealing and customizable Discord embeds.

    This class provides a static method to create Discord embeds with options like title, description, color, author information,
    and more to enhance the visual experience of your embeds.
    """
    
    # Default values for embed creation
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
            author: str = "",
            timestamp: bool = True
    ) -> discord.Embed:
        """
        Creates and returns a customized, visually appealing Discord embed.

        Args:
            interaction (discord.Interaction, optional): The interaction that triggered the embed (e.g., from a command).
                                                        If provided, the footer will include the user's name and avatar.
            description (str, optional): The description to set in the embed. Defaults to an empty string.
            title (str, optional): The title of the embed. If not provided, uses a default title. Defaults to an empty string.
            thumbnail (str, optional): The URL of an image to set as the embed's thumbnail. Defaults to an empty string.
            colour (discord.Colour, optional): The color of the embed. Defaults to a random color if not provided.
            author (str, optional): The name of the author to set for the embed. If not provided, uses a default name. Defaults to an empty string.
            timestamp (bool, optional): Whether to include the current timestamp in the footer.

        Returns:
            discord.Embed: A fully constructed Discord embed with the provided parameters.

        Example:
            embed = EmbedFactory.create_embed(
                title="Welcome!",
                description="Hello, world!",
                colour=discord.Colour.blue(),
                author="Bot Developer",
                timestamp=True
            )
        """
        # Create the embed object with the basic information
        embed = discord.Embed(
            colour=colour,
            title=title or EmbedFactory.DEFAULT_TITLE,  # Fallback to the default title if none is provided
            description=description
        )
        
        # Set the footer with the user's information if an interaction is provided
        if interaction:
            embed.set_footer(text=f"By {interaction.user.name}", icon_url=interaction.user.avatar.url)
        
        # Set the author of the embed if an author name is provided
        if author:
            embed.set_author(name=author, url=EmbedFactory.AUTHOR_URL)
        else:
            embed.set_author(name=EmbedFactory.AUTHOR_NAME, url=EmbedFactory.AUTHOR_URL)

        # Set the thumbnail if a URL is provided
        if thumbnail:
            embed.set_thumbnail(url=thumbnail)
        
        # Include timestamp if specified
        if timestamp:
            embed.timestamp = datetime.utcnow()

        return embed
