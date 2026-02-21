import json
import os
import requests
from .base import ChatMessenger, register
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

HELP_MESSAGE = """Available subcommands:
- *change* - make a change to the current image
- *set-image* - (admin only) Set or reset the starting image
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
            self.app_token = config.app_token
        else:
            raise Exception("no app token set for Slack")
        
        self.app = App(token=self.bot_token)
        self.register_listeners()

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
                text = ' '.join(fields[1:])
            case "set-image":
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

    def handle_set_image_upload(self, ack, body, client, logger):
        ack()

        private_metadata = json.loads(body["view"]["private_metadata"])
        channel_id = private_metadata["channel_id"]
        team_id = body["team"]["id"]
        state_values = body["view"]["state"]["values"]
        
        try:
            files = state_values["file_block"]["file_action"].get("files", [])
        except Exception:
            files = []

        if not files:
            ack(response_action="errors", errors={"file_block": "Please attach a file before submitting."})
            return
        
        description = state_values["message_input_block"]["message_input_element"]["value"]

        file_id = files[0]["id"]
        file_info = client.files_info(file=file_id)
        f = file_info["file"]
        file_permalink = f["permalink"]

        # Download the image
        try:
            url = f.get("url_private_download") or f.get("url_private")
            original_name = f.get("name") or f.get("title") or f"slack-file-{file_id}"

            # Ensure a safe local path
            # TODO: figure out where files should actually go
            uploads_dir = os.environ.get("UPLOADS_DIR", "/tmp")
            dest_path = os.path.join(uploads_dir, team_id, channel_id)
            os.makedirs(dest_path, exist_ok=True)
            local_path = os.path.join(dest_path, "current")

            # Stream download with bot token
            resp = requests.get(
                url,
                headers={"Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}"},
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