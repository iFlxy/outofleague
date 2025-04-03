from email import message
from http import server
import discord
from discord.ui import Modal, TextInput, View, ChannelSelect
import os
import os.path
import json
import datetime
from discord.ext import tasks

token = os.getenv("BOT_TOKEN")
muted_users = {}

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
intents.presences = True
intents.members = True

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
        config_manager.set_guild_config(message.guild.id, "active", "on")

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

    if not message.author.guild_permissions.administrator:
        await message.channel.send("You need administrator permissions to use this command.")
        return

    elif message.content.startswith("l!setpenalty"):
        parts = message.content.split()
        if len(parts) > 1 and parts[1] in ["ban", "kick", "mute"]:
            await message.channel.send(f"Penalty set to {parts[1]}.")
            config_manager.set_guild_config(message.guild.id, "action", parts[1])
        else:
            await message.channel.send("Invalid penalty type. Use 'ban', 'kick', or 'mute'.")

    elif message.content.startswith("l!setlogs"):
        parts = message.content.split()
        if len(message.channel_mentions) > 0:
            logs_channel = message.channel_mentions[0].id
            await message.channel.send(f"Logs channel set to <#{logs_channel}>.")
        else:
            await message.channel.send("Please mention a channel. Make sure it's highlighted.")

    elif message.content.startswith("l!setmessage"):
        parts = message.content.split(maxsplit=1)
        if len(parts) > 1:
            if len(parts[1]) <= 128:
                await message.channel.send(f"Penalty message updated to: {parts[1]}")
                config_manager.set_guild_config(message.guild.id, "action_message", parts[1])
            else:
                await message.channel.send("Message too long!")
        else:
            await message.channel.send("Please provide a message.")

    elif message.content.startswith("l!toggle"):
        parts = message.content.split()
        if len(parts) > 1 and parts[1] in ["on", "off"]:
            await message.channel.send(f"Bot turned {parts[1]}.")
            config_manager.set_guild_config(message.guild.id, "active", parts[1])
        else:
            await message.channel.send("Invalid option. Use 'on' or 'off'.")

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

@client.event
async def on_presence_update(before: discord.Member, after: discord.Member):
    if before.activities != after.activities:
        for activity in after.activities:
            print(activity)
            if activity.name == "League of Legends":
                guild_id = after.guild.id if after.guild else None
                if guild_id and config_manager.get_guild_value(guild_id, "active", None) == "on":
                    match config_manager.get_guild_value(guild_id, "action", None):
                        case "ban":
                            await after.ban(reason=config_manager.get_guild_value(guild_id, "action_message", "unknown"))
                            ending = "banned"
                        case "kick":
                            await after.kick(reason=config_manager.get_guild_value(guild_id, "action_message", "unknown"))
                            ending = "kicked"
                        case "mute":
                            await mute_user(after)
                            ending = "muted"

                    embed = discord.Embed(
                        title="LOG: Action",
                        description=f"An action has been taken against the user {after.name}: User {ending}.",
                        colour=0xee0000,
                        timestamp=datetime.datetime.now()
                    )

                    embed.set_author(name="OutOfLeague")
                    embed.set_footer(text="Logging")

                    log_channel_id = config_manager.get_guild_value(guild_id, "log_channel")
                    if log_channel_id:
                        await client.get_channel(log_channel_id).send(embed=embed)

async def mute_user(user):
    if user not in muted_users:
        muted_users[user] = True
        check_muted_users.start()

    if config_manager.get_guild_value(user.guild.id, "active", None) == "on":
        await user.timeout(datetime.timedelta(seconds=45), reason=config_manager.get_guild_value(user.guild.id, "action_message", "unknown"))

@tasks.loop(seconds=30)
async def check_muted_users():
    if not muted_users:
        check_muted_users.stop()

    to_remove = []

    for member in list(muted_users.keys()):
        if not member:
            to_remove.append(member)
            continue

        for activity in member.activities:
            if activity.name == "League of Legends":
                await mute_user(member)
                break
        else:
            to_remove.append(member)

    for member in to_remove:
        muted_users.pop(member, None)



client.run(token)
