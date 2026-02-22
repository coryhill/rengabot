import asyncio
import json
import os
import requests
from .base import ChatMessenger, register
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from game.service import (
    ChangeInProgressError,
    GenerationError,
    InvalidPromptError,
    NoImageError,
)

HELP_MESSAGE = """Available subcommands:
- *change* - make a change to the current image
- *set-image* - (admin only) Set or reset the starting image
- *show-image* - show the current image
"""

CHANGE_USAGE = """Usage: /rengabot change [describe change]
Example: /rengabot change add an angry dinosaur in the background
"""

@register("slack")
class SlackMessenger(ChatMessenger):
    def __init__(self, config, rengabot):
        super().__init__(config, rengabot)

        if os.environ.get("SLACK_BOT_TOKEN"):
            self.bot_token = os.environ["SLACK_BOT_TOKEN"]
        elif config.get("bot_token"):
            self.bot_token = config["bot_token"]
        else:
            raise Exception("no bot token set for Slack")
        
        if os.environ.get("SLACK_APP_TOKEN"):
            self.app_token = os.environ["SLACK_APP_TOKEN"]
        elif config.get("app_token"):
            self.app_token = config["app_token"]
        else:
            raise Exception("no app token set for Slack")
        
        self.app = AsyncApp(token=self.bot_token)
        self.register_listeners()

    def _is_admin(self, user_id: str) -> bool:
        return user_id in self.config.get("admins", [])

    def _get_current_image_path(self, team_id: str, channel_id: str):
        return self.rengabot.service.get_current_image_path("slack", team_id, channel_id)

    def register_listeners(self):
        self.app.event("app_mention")(self.handle_mention)
        self.app.command("/rengabot")(self.handle_slash_cmd)
        self.app.view("upload_modal")(self.handle_set_image_upload)
    
    async def handle_mention(self, event, say):
        await say("Use the /rengabot slash command!")

    async def _handle_change_async(
        self,
        client,
        logger,
        user_id: str,
        team_id: str,
        channel_id: str,
        prompt: str,
    ):
        try:
            next_path = await asyncio.to_thread(
                self.rengabot.service.change_image, "slack", team_id, channel_id, prompt
            )
        except NoImageError:
            await client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=self.rengabot.service.NO_IMAGE_MESSAGE,
            )
            return
        except InvalidPromptError as e:
            await client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=self.rengabot.service.format_invalid_prompt(e.reason),
            )
            return
        except ChangeInProgressError:
            await client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=self.rengabot.service.CHANGE_IN_PROGRESS_MESSAGE,
            )
            return
        except GenerationError as e:
            logger.exception("Image generation failed: %s", e)
            await client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text=self.rengabot.service.GENERATION_ERROR_MESSAGE,
            )
            return
        await client.files_upload_v2(
            channel=channel_id,
            file=next_path,
            filename="renga.png",
            initial_comment=f"Renga update: {prompt}",
        )

    async def handle_slash_cmd(self, ack, body, respond, client, logger):
        await ack()
        user_id = body["user_id"]
        text = body["text"]
        
        # See which subcommand they're using
        fields = text.split()
        if len(fields) == 0:
            await respond(text=HELP_MESSAGE, response_type="ephemeral")
            return
            
        match fields[0]:
            case "help":
                await respond(
                    text=HELP_MESSAGE,
                    response_type="ephemeral"
                )
            case "change":
                if len(fields) == 1:
                    await respond(
                        text=CHANGE_USAGE,
                        response_type="ephemeral"
                    )
                    return
                text = ' '.join(fields[1:])
                channel_id = body.get("channel_id", "")
                team_id = body.get("team_id", "")
                current_path = self._get_current_image_path(team_id, channel_id)
                if not current_path:
                    await respond(
                        text=self.rengabot.service.NO_IMAGE_MESSAGE,
                        response_type="ephemeral",
                    )
                    return
                await respond(text="Working on it...", response_type="ephemeral")
                asyncio.create_task(
                    self._handle_change_async(
                        client, logger, user_id, team_id, channel_id, text
                    )
                )
            case "set-image":
                if not self._is_admin(user_id):
                    await respond(
                        text="Only admins can set the image.",
                        response_type="ephemeral",
                    )
                    return
                channel_id = body.get("channel_id", "")
                await client.views_open(
                    trigger_id=body["trigger_id"],
                    view={
                        "type": "modal",
                        "callback_id": "upload_modal",
                        "title": {"type": "plain_text", "text": "Upload an image"},
                        "submit": {"type": "plain_text", "text": "Set image"},
                        "close": {"type": "plain_text", "text": "Cancel"},
                        "private_metadata": json.dumps({"channel_id": body["channel_id"]}),
                        "blocks": [
                            {
                                "type": "input",
                                "block_id": "file_block",
                                "label": {"type": "plain_text", "text": "Choose one image"},
                                "element": {
                                    "type": "file_input",
                                    "action_id": "file_action",
                                    "filetypes": ["jpg", "jpeg", "png"],
                                    "max_files": 1
                                }
                            },
                            {
                                "type": "input",
                                "block_id": "message_input_block",
                                "label": {
                                    "type": "plain_text",
                                    "text": "Description",
                                },
                                "element": {
                                    "type": "plain_text_input",
                                    "action_id": "message_input_element",
                                    "multiline": True,
                                },
                            },
                        ]
                    }
                )
            case "show-image":
                channel_id = body.get("channel_id", "")
                team_id = body.get("team_id", "")
                current_path = self._get_current_image_path(team_id, channel_id)
                if not current_path:
                    await respond(
                        text=self.rengabot.service.NO_IMAGE_MESSAGE,
                        response_type="ephemeral",
                    )
                    return
                await client.files_upload_v2(
                    channel=channel_id,
                    file=current_path,
                    filename="renga.png",
                    initial_comment="Current renga image:",
                )

    async def handle_set_image_upload(self, ack, body, client, logger):
        private_metadata = json.loads(body["view"]["private_metadata"])
        channel_id = private_metadata["channel_id"]
        team_id = body["team"]["id"]
        user_id = body["user"]["id"]
        state_values = body["view"]["state"]["values"]
        
        try:
            files = state_values["file_block"]["file_action"].get("files", [])
        except Exception:
            files = []

        if not files:
            await ack(response_action="errors", errors={"file_block": "Please attach a file before submitting."})
            return
        await ack()
        if not self._is_admin(user_id):
            await client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="Only admins can set the image.",
            )
            return
        
        description = state_values["message_input_block"]["message_input_element"]["value"]

        file_id = files[0]["id"]
        file_info = await client.files_info(file=file_id)
        f = file_info["file"]
        file_permalink = f["permalink"]
        file_ext = (f.get("filetype") or "png").lower()
        if file_ext not in ("png", "jpg", "jpeg"):
            file_ext = "png"

        # Download the image
        try:
            url = f.get("url_private_download") or f.get("url_private")
            original_name = f.get("name") or f.get("title") or f"slack-file-{file_id}"

            # Ensure a safe local path
            # TODO: figure out where files should actually go
            dest_path = self.rengabot.service.channel_dir("slack", team_id, channel_id)
            os.makedirs(dest_path, exist_ok=True)
            local_path = os.path.join(dest_path, f"current.{file_ext}")

            # Stream download with bot token
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {self.bot_token}"},
                stream=True,
                timeout=60,
            )
            resp.raise_for_status()
            with open(local_path, "wb") as out:
                for chunk in resp.iter_content(chunk_size=8192):
                    if chunk:
                        out.write(chunk)
        except Exception as e:
            logger.exception("Local save failed: %s", e)
            
        self.rengabot.service.save_image_file(
            "slack", team_id, channel_id, local_path, file_ext
        )

        # Share to slack channel
        await client.chat_postMessage(
            channel=channel_id,
            text=f"The renga has been reset: {description}\n{file_permalink}"
        )

    def run(self):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        handler = AsyncSocketModeHandler(self.app, self.app_token, loop=loop)
        loop.run_until_complete(handler.start_async())
