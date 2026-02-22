import json
import os
import requests
from typing import Optional
from .base import ChatMessenger, register
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

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
        
        self.app = App(token=self.bot_token)
        self.register_listeners()

    def _is_admin(self, user_id: str) -> bool:
        return user_id in self.config.get("admins", [])

    def _channel_dir(self, team_id: str, channel_id: str) -> str:
        uploads_dir = os.environ.get("UPLOADS_DIR", "/tmp")
        return os.path.join(uploads_dir, team_id, channel_id)

    def _get_current_image_path(self, team_id: str, channel_id: str) -> Optional[str]:
        channel_dir = self._channel_dir(team_id, channel_id)
        for ext in ("png", "jpg", "jpeg"):
            path = os.path.join(channel_dir, f"current.{ext}")
            if os.path.exists(path):
                return path
        return None

    def register_listeners(self):
        self.app.event("app_mention")(self.handle_mention)
        self.app.command("/rengabot")(self.handle_slash_cmd)
        self.app.view("upload_modal")(self.handle_set_image_upload)
    
    def handle_mention(self, event, say):
        say("Use the /rengabot slash command!")

    def handle_slash_cmd(self, ack, body, respond, client, logger):
        ack()
        user_id = body["user_id"]
        text = body["text"]
        
        # See which subcommand they're using
        fields = text.split()
        if len(fields) == 0:
            respond(text=HELP_MESSAGE, response_type="ephemeral")
            return
            
        match fields[0]:
            case "help":
                respond(
                    text=HELP_MESSAGE,
                    response_type="ephemeral"
                )
            case "change":
                if len(fields) == 1:
                    respond(
                        text=CHANGE_USAGE,
                        response_type="ephemeral"
                    )
                    return
                text = ' '.join(fields[1:])
                channel_id = body.get("channel_id", "")
                team_id = body.get("team_id", "")
                current_path = self._get_current_image_path(team_id, channel_id)
                if not current_path:
                    respond(
                        text="No image has been set yet. An admin must run `/rengabot set-image` first.",
                        response_type="ephemeral",
                    )
                    return
                respond(text="Working on it...", response_type="ephemeral")
                is_valid, reason = self.rengabot.model.validate_prompt(text)
                if not is_valid:
                    respond(
                        text=f"Disallowed change: {reason or 'prompt does not match the rules.'}",
                        response_type="ephemeral",
                    )
                    return
                try:
                    image_bytes = self.rengabot.model.generate_image(text, current_path)
                except Exception as e:
                    logger.exception("Image generation failed: %s", e)
                    respond(text="Image generation failed. Please try again.", response_type="ephemeral")
                    return
                channel_dir = self._channel_dir(team_id, channel_id)
                os.makedirs(channel_dir, exist_ok=True)
                next_path = os.path.join(channel_dir, "current.png")
                with open(next_path, "wb") as f:
                    f.write(image_bytes)
                client.files_upload_v2(
                    channel=channel_id,
                    file=next_path,
                    filename="renga.png",
                    initial_comment=f"Renga update: {text}",
                )
            case "set-image":
                if not self._is_admin(user_id):
                    respond(
                        text="Only admins can set the image.",
                        response_type="ephemeral",
                    )
                    return
                channel_id = body.get("channel_id", "")
                client.views_open(
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
                    respond(
                        text="No image has been set yet. An admin must run `/rengabot set-image` first.",
                        response_type="ephemeral",
                    )
                    return
                client.files_upload_v2(
                    channel=channel_id,
                    file=current_path,
                    filename="renga.png",
                    initial_comment="Current renga image:",
                )

    def handle_set_image_upload(self, ack, body, client, logger):
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
            ack(response_action="errors", errors={"file_block": "Please attach a file before submitting."})
            return
        ack()
        if not self._is_admin(user_id):
            client.chat_postEphemeral(
                channel=channel_id,
                user=user_id,
                text="Only admins can set the image.",
            )
            return
        
        description = state_values["message_input_block"]["message_input_element"]["value"]

        file_id = files[0]["id"]
        file_info = client.files_info(file=file_id)
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
            dest_path = self._channel_dir(team_id, channel_id)
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
            
        # Share to slack channel
        client.chat_postMessage(
            channel=channel_id,
            text=f"The renga has been reset: {description}\n{file_permalink}"
        )

    def run(self):
        SocketModeHandler(self.app, self.app_token).start()
