#!/usr/bin/env python3

import os
import yaml
from messengers import initialize_messenger
from model import load_model

def load_config(path="config.yaml"):
    with open(path, "r") as f:
        return yaml.safe_load(f)
    
def main():
    config = load_config()

    model_config = config["model"]
    model = load_model(model_config["class"], model_config["args"])
    
    for svc, svc_config in config["messengers"].items():
        if svc_config["enabled"]:
            initialize_messenger(svc, svc_config)

if __name__ == '__main__':
    main()