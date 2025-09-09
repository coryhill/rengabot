#!/usr/bin/env python3

import os
import threading
import yaml
from messengers import ChatMessenger, initialize_messenger
from model import load_model

def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)
    
class MessengerThread(threading.Thread):
    def __init__(self, chat_messenger: ChatMessenger):
        super().__init__()
        self.messenger = chat_messenger

class Rengabot:
    def __init__(self, config):
        self.config = config
        self.messengers = []
    
    def update_image(path, src_file):
        os.replace(src_file, f"{path}/current.png")

    def run(self):
        model_config = config["model"]
        model = load_model(model_config["class"], model_config["args"])
        
        for svc, svc_config in config["messengers"].items():
            if svc_config["enabled"]:
                messenger = initialize_messenger(svc, svc_config, self)
                messenger.run()
                self.messengers.append(messenger)

if __name__ == '__main__':
    config = load_config()
    rengabot = Rengabot(config)
    rengabot.run()