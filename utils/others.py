import discord

def is_it_me(interaction: discord.Interaction) -> bool:
    return interaction.user.id == 1406018517425459404