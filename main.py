#!/usr/bin/env python3

import logging
import os
import threading
import yaml
from messengers import ChatMessenger, initialize_messenger
from model import load_model

def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)
    
"""
class MessengerThread(threading.Thread):
    def __init__(self, chat_messenger: ChatMessenger):
        super().__init__()
        self.messenger = chat_messenger
"""

class Rengabot:
    def __init__(self, config):
        self.config = config

        model_config = config["model"]
        self.model = load_model(model_config["class"], model_config["args"])

        self.messengers = []
    
    def update_image(self, path, src_file):
        os.replace(src_file, f"{path}/current.png")

    def run(self):
        threads = []
        for svc, svc_config in self.config["messengers"].items():
            if svc_config["enabled"]:
                messenger = initialize_messenger(svc, svc_config, self)
                self.messengers.append(messenger)
                t = threading.Thread(target=messenger.run, daemon=True)
                t.start()
                threads.append(t)
        for t in threads:
            t.join()

if __name__ == '__main__':
    config = load_config()
    logging.basicConfig(level=logging.INFO)
    rengabot = Rengabot(config)
    rengabot.run()
