from email import message
from http import server
import discord
from discord.ui import Modal, TextInput, View, ChannelSelect
import os
import os.path
import json

token = os.getenv("BOT_TOKEN")

CONFIG_FILE = "serverdata.json"

class GuildConfigManager:
    def __init__(self):
        self.ensure_config_file()

    def ensure_config_file(self):
        if not os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "w") as f:
                f.write("{}")

    def load_config(self):
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)

    def save_config(self, config):
        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=4)

    def get_guild_config(self, guild_id):
        config = self.load_config()
        return config.get(str(guild_id), {})

    def set_guild_config(self, guild_id, key, value):
        guild_id = str(guild_id)
        config = self.load_config()

        if guild_id not in config:
            config[guild_id] = {}
        config[guild_id][key] = value

        self.save_config(config)

    def get_guild_value(self, guild_id, key, default=None):
        return self.get_guild_config(guild_id).get(key, default)

config_manager = GuildConfigManager()

def help_embed(title: str):
    embed = discord.Embed(title=title,
                          colour=0xee0000)

    embed.set_author(name="OutOfLeague")

    embed.add_field(name="l!setup",
                    value="Set up penalties and logs interactively",
                    inline=False)
    embed.add_field(name="l!setpenalty <ban/kick/mute>",
                    value="Set a penalty manually (active while playing LoL)",
                    inline=False)
    embed.add_field(name="l!setlogs <#channel>",
                    value="Set the logs channel manually.",
                    inline=False)
    embed.add_field(name="l!setmessage <message>",
                    value="Change the penalty message",
                    inline=False)
    embed.add_field(name="l!toggle <on/off>",
                    value="Turn the bot off or on",
                    inline=False)
    embed.add_field(name="l!help",
                    value="Show this message",
                    inline=False)

    embed.set_footer(text="OutOfLeague")

    return embed


intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)

@client.event
async def on_ready():
    print(f'Forcing people to touch grass as {client.user}')
    for guild in client.guilds:
        if config_manager.get_guild_value(guild.id, "sent_help_message", 0) == 0:
            config_manager.set_guild_config(guild.id, "sent_help_message", 1)

            text_channel = next((ch for ch in guild.text_channels if ch.permissions_for(guild.me).send_messages), None)
            if text_channel:
                await text_channel.send(embed=help_embed("Thanks for using OutOfLeague! Avaliable commands:"))


class ChannelSelectionView(discord.ui.View):
    def __init__(self, author_id, msg, msgc):
        super().__init__(timeout=None)
        self.author_id = author_id

        self.emsg = msg
        self.emsgc = msgc

        self.channel_select = ChannelSelect(
            custom_id="channelselect",
            placeholder="Select a channel...",
            min_values=1,
            max_values=1,
            channel_types=[discord.ChannelType.text],
        )

        self.channel_select.callback = self.channel_select_callback
        self.add_item(self.channel_select)

    async def channel_select_callback(self, interaction: discord.Interaction):
        selected_channel = self.channel_select.values[0].id
        config_manager.set_guild_config(interaction.guild.id, "log_channel", selected_channel)
        embed = discord.Embed(title="Setup done!",
                              description="The OutOfLeague bot is now set up and looking for LoL players!",
                              colour=0xee0000)
        embed.set_author(name="OutOfLeague Setup")
        embed.set_footer(text="OutOfLeague")

        message = await self.emsgc.fetch_message(self.emsg)
        await message.edit(embed=embed, view=None)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.author_id


class TextModal(Modal):
    def __init__(self, original_message: discord.Message):
        super().__init__(title="Set penalty message")
        self.original_message = original_message
        self.text_input = TextInput(
            label="Enter your message",
            placeholder="Type something...",
            max_length=128,
            required=True
        )
        self.add_item(self.text_input)

    async def on_submit(self, interaction: discord.Interaction):
        config_manager.set_guild_config(interaction.guild.id, "action_message", self.text_input.value)
        embed = discord.Embed(
            title="Set the Logs channel",
            description="Click the dropdown below to set it up",
            colour=0xee0000
        )
        embed.set_author(name="OutOfLeague Setup <3/3>")
        embed.set_footer(text="OutOfLeague")
        await self.original_message.edit(embed=embed, view=ChannelSelectionView(interaction.user.id, self.original_message.id, self.original_message.channel))
        await interaction.response.defer()


class MessageView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=None)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            return False
        return True

    async def handle_selection(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Set a penalty message",
                              description="Click the button below to set the message",
                              colour=0xee0000)
        embed.set_author(name="OutOfLeague Setup <2/3>")
        embed.set_footer(text="OutOfLeague")
        await interaction.response.edit_message(embed=embed)

    @discord.ui.button(label="Set message", style=discord.ButtonStyle.danger)
    async def message_write(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TextModal(original_message=interaction.message))

class PenaltyView(discord.ui.View):
    def __init__(self, author_id):
        super().__init__(timeout=None)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            return False
        return True

    async def handle_selection(self, interaction: discord.Interaction):
        embed = discord.Embed(title="Set a penalty message",
                              description="Click the button below to set the message",
                              colour=0xee0000)
        embed.set_author(name="OutOfLeague Setup <2/3>")
        embed.set_footer(text="OutOfLeague")
        await interaction.response.edit_message(embed=embed, view=MessageView(self.author_id))

    @discord.ui.button(label="Ban", style=discord.ButtonStyle.danger)
    async def ban_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        config_manager.set_guild_config(interaction.guild.id, "action", "ban")
        await self.handle_selection(interaction)

    @discord.ui.button(label="Kick", style=discord.ButtonStyle.danger)
    async def kick_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        config_manager.set_guild_config(interaction.guild.id, "action", "kick")
        await self.handle_selection(interaction)

    @discord.ui.button(label="Mute", style=discord.ButtonStyle.danger)
    async def mute_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        config_manager.set_guild_config(interaction.guild.id, "action", "mute")
        await self.handle_selection(interaction)



@client.event
async def on_message(message):
    if message.author == client.user:
        return

    if message.content.startswith('l!help'):
        await message.channel.send(embed=help_embed("Avaliable commands:"))
    if message.content.startswith('l!setup'):
        embed = discord.Embed(
            title="Select a penalty for playing LoL",
            description="Available choices:",
            colour=0xee0000
        )
        embed.set_author(name="OutOfLeague Setup <1/3>")
        embed.add_field(name="Ban", value="Bans any user for playing LoL", inline=True)
        embed.add_field(name="Kick", value="Kicks the user from the server if they are playing LoL", inline=True)
        embed.add_field(name="Mute", value="Mutes the user while they are playing LoL", inline=True)
        embed.set_footer(text="OutOfLeague")

        await message.channel.send(embed=embed, view=PenaltyView(message.author.id))


client.run(token)
