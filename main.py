#!/usr/bin/env python3

import os
import yaml
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from messengers import initialize_messenger
from model import load_model

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

@app.command("/set-image")
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

@app.view("upload_modal")
def handle_set_image_upload(ack, body, client):
    files_state = body["view"]["state"]["values"]["file_block"]["file_action"]
    file_ids = files_state.get("files", [])  # list of file IDs

    for fid in file_ids:
        info = client.files_info(file=fid)
        # Use info["file"]["url_private_download"] with a bot token header to download,
        # then do your processing...


@app.event("app_mention")
def handle_mention(event, say):
    say(f"User {event["user"]} said \"{event["text"]}\"")

def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)
    
def main():
    config = load_config()

    model_config = config["model"]
    model = load_model(model_config["class"], model_config["args"])
    
    messenger_config = config["messengers"]
    for svc, svc_config in messenger_config.items():
        if svc_config["enabled"]:
            initialize_messenger(svc)
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()

if __name__ == '__main__':
    main()