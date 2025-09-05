import os
from .base import ChatMessenger, register
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

@register("slack")
class SlackMessenger(ChatMessenger):
    def __init__(self, config):
        super().__init__(config)

        if os.environ.get("SLACK_BOT_TOKEN"):
            self.bot_token = os.environ["SLACK_BOT_TOKEN"]
        elif config.get("bot_token"):
            self.bot_token = config["bot_token"]
        else:
            raise Exception("no bot token set for Slack")
        
        if os.environ.get("SLACK_APP_TOKEN"):
            self.bot_token = os.environ["SLACK_APP_TOKEN"]
        elif config.get("app_token"):
            self.app_token = config.app_token
        else:
            raise Exception("no app token set for Slack")
        
        self.app = App(token=self.bot_token)
        self.register_listeners()

    def register_listeners(self):
        self.app.event("app_mention")(self.handle_mention)
        self.app.command("/set-image")(self.handle_set_image_cmd)
        self.app.view("upload_media")(self.handle_set_image_upload)
    
    def handle_mention(event, say):
        say(f"User {event["user"]} said \"{event["text"]}\"")

    def handle_set_image_cmd(ack, body, client):
        ack()
        user = body["user_id"]
        client.views_open(
            trigger_id=body["trigger_id"],
            view={
                "type": "modal",
                "callback_id": "upload_modal",
                "title": {"type": "plain_text", "text": "Upload an image"},
                "submit": {"type": "plain_text", "text": "Set image"},
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
                    }
                ]
            }
        )

    def handle_set_image_upload(ack, body, client):
        files_state = body["view"]["state"]["values"]["file_block"]["file_action"]
        file_ids = files_state.get("files", [])  # list of file IDs

        for fid in file_ids:
            info = client.files_info(file=fid)
            # Use info["file"]["url_private_download"] with a bot token header to download,
            # then do your processing...

    def run(self):
        SocketModeHandler(self.app, self.app_token).start()