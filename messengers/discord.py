import asyncio
import os
from typing import Optional

import discord
from discord import app_commands
from game.service import (
    ChangeInProgressError,
    GenerationError,
    InvalidPromptError,
    NoImageError,
)

from .base import ChatMessenger, register


@register("discord")
class DiscordMessenger(ChatMessenger):
    def __init__(self, config, rengabot):
        super().__init__(config, rengabot)

        if os.environ.get("DISCORD_BOT_TOKEN"):
            self.bot_token = os.environ["DISCORD_BOT_TOKEN"]
        elif config.get("bot_token"):
            self.bot_token = config["bot_token"]
        else:
            raise Exception("no bot token set for Discord")

        intents = discord.Intents.default()
        self.client = discord.Client(intents=intents)
        self.tree = app_commands.CommandTree(self.client)
        self.guild_id = config.get("guild_id")

        self._register_commands()

        @self.client.event
        async def on_ready():
            if self.guild_id:
                guild = discord.Object(id=int(self.guild_id))
                await self.tree.sync(guild=guild)
            else:
                await self.tree.sync()

    def _is_admin(self, user: discord.abc.User) -> bool:
        if str(user.id) in self.config.get("admins", []):
            return True
        if isinstance(user, discord.Member):
            return user.guild_permissions.administrator
        return False

    def _channel_dir(self, guild_id: str, channel_id: str) -> str:
        return self.rengabot.service.channel_dir("discord", guild_id, channel_id)

    def _get_current_image_path(self, guild_id: str, channel_id: str) -> Optional[str]:
        return self.rengabot.service.get_current_image_path("discord", guild_id, channel_id)

    def _register_commands(self):
        guild = discord.Object(id=int(self.guild_id)) if self.guild_id else None
        group = app_commands.Group(
            name="rengabot",
            description="Rengabot game commands",
        )
        self.tree.add_command(group, guild=guild)

        @group.command(name="help", description="Show Rengabot help")
        async def rengabot_help(interaction: discord.Interaction):
            await interaction.response.send_message(
                "Available subcommands: /rengabot change, /rengabot set-image, /rengabot show-image",
                ephemeral=True,
            )

        @group.command(
            name="set-image",
            description="Set or reset the starting image (admin only)",
        )
        @app_commands.describe(
            image="Image to set as the base",
            description="Description of the new base image",
        )
        async def rengabot_set_image(
            interaction: discord.Interaction,
            image: discord.Attachment,
            description: Optional[str] = None,
        ):
            if not self._is_admin(interaction.user):
                await interaction.response.send_message(
                    "Only admins can set the image.",
                    ephemeral=True,
                )
                return
            if not image:
                await interaction.response.send_message(
                    "Please attach an image file.",
                    ephemeral=True,
                )
                return
            if not image.content_type or not image.content_type.startswith("image/"):
                await interaction.response.send_message(
                    "Only image uploads are supported.",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True, thinking=True)

            guild_id = str(interaction.guild_id)
            channel_id = str(interaction.channel_id)
            dest_dir = self._channel_dir(guild_id, channel_id)
            os.makedirs(dest_dir, exist_ok=True)

            ext = (image.filename.split(".")[-1] or "png").lower()
            if ext not in ("png", "jpg", "jpeg"):
                ext = "png"
            dest_path = os.path.join(dest_dir, f"current.{ext}")
            await image.save(dest_path)
            self.rengabot.service.save_image_file(
                "discord", guild_id, channel_id, dest_path, ext
            )

            await interaction.followup.send(
                f"The renga has been reset: {description or '(no description)'}",
                ephemeral=False,
            )
            await interaction.channel.send(
                content=f"Renga reset: {description or '(no description)'}",
                file=discord.File(dest_path, filename="renga.png"),
            )

        @group.command(
            name="change",
            description="Make a single change to the current image",
        )
        @app_commands.describe(prompt="Describe a single change")
        async def rengabot_change(interaction: discord.Interaction, prompt: str):
            if not prompt:
                await interaction.response.send_message(
                    "Usage: /rengabot change prompt:<describe change>",
                    ephemeral=True,
                )
                return

            await interaction.response.defer(ephemeral=True, thinking=True)

            guild_id = str(interaction.guild_id)
            channel_id = str(interaction.channel_id)
            try:
                next_path = await asyncio.to_thread(
                    self.rengabot.service.change_image,
                    "discord",
                    guild_id,
                    channel_id,
                    prompt,
                )
            except NoImageError:
                await interaction.followup.send(
                    self.rengabot.service.NO_IMAGE_MESSAGE,
                    ephemeral=True,
                )
                return
            except InvalidPromptError as e:
                await interaction.followup.send(
                    self.rengabot.service.format_invalid_prompt(e.reason),
                    ephemeral=True,
                )
                return
            except ChangeInProgressError:
                await interaction.followup.send(
                    self.rengabot.service.CHANGE_IN_PROGRESS_MESSAGE,
                    ephemeral=True,
                )
                return
            except GenerationError:
                await interaction.followup.send(
                    self.rengabot.service.GENERATION_ERROR_MESSAGE,
                    ephemeral=True,
                )
                return

            await interaction.channel.send(
                content=f"Renga update: {prompt}",
                file=discord.File(next_path, filename="renga.png"),
            )

        @group.command(
            name="show-image",
            description="Show the current image",
        )
        async def rengabot_show_image(interaction: discord.Interaction):
            await interaction.response.defer(ephemeral=True, thinking=True)

            guild_id = str(interaction.guild_id)
            channel_id = str(interaction.channel_id)
            try:
                current_path = self.rengabot.service.show_image(
                    "discord", guild_id, channel_id
                )
            except NoImageError:
                await interaction.followup.send(
                    self.rengabot.service.NO_IMAGE_MESSAGE,
                    ephemeral=True,
                )
                return

            await interaction.channel.send(
                content="Current renga image:",
                file=discord.File(current_path, filename="renga.png"),
            )
            await interaction.followup.send("Posted the current image.", ephemeral=True)

    def run(self):
        self.client.run(self.bot_token)
