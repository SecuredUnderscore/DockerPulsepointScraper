import json
import os

CONFIG_FILE = os.environ.get('CONFIG_FILE_PATH', 'data/config.json')

DEFAULT_CONFIG = {
    "agencies": [],  # list of strings like "06140"
    "incidentTypes": [],  # list of strings like "TC", "ME"
    "polygons": [],  # list of geojson polygons or custom structural dicts
    "notifications": {
        "discordWebhookUrl": "",
        "pushoverUserKey": "",
        "pushoverAppToken": "",
        "vehicleThreshold": 5,
        "timezone": "America/Vancouver",
        "checkIntervalSeconds": 60,
        "alerts": {
            "new": {
                "enabled": True,
                "pushoverSound": "pushover",
                "pushoverPriority": 0
            },
            "escalation": {
                "enabled": True,
                "pushoverSound": "pushover",
                "pushoverPriority": 0
            },
            "specialUnit": {
                "enabled": True,
                "pushoverSound": "siren",
                "pushoverPriority": 1
            }
        },
        "unitTypes": [
            {"pattern": "A", "label": "Ambulance", "emoji": "\U0001f691", "specialAlert": False},
            {"pattern": "B", "label": "Supervisor", "emoji": "\U0001f454", "specialAlert": False},
            {"pattern": "C", "label": "Commander", "emoji": "\u2b50", "specialAlert": False},
            {"pattern": "E", "label": "Engine", "emoji": "\U0001f692", "specialAlert": False},
            {"pattern": "J", "label": "Surge Unit", "emoji": "\U0001f4cb", "specialAlert": False},
            {"pattern": "K", "label": "On-Call Unit", "emoji": "\U0001f4df", "specialAlert": False},
            {"pattern": "P", "label": "Patrol/SUV", "emoji": "\U0001f693", "specialAlert": False},
            {"pattern": "S", "label": "Helicopter", "emoji": "\U0001f681", "specialAlert": True},
            {"pattern": "Z", "label": "Special Ops", "emoji": "\u26a1", "specialAlert": False}
        ]
    }
}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG

    with open(CONFIG_FILE, 'r') as f:
        try:
            return json.load(f)
        except:
            return DEFAULT_CONFIG

def save_config(config_data):
    # Ensure directory exists
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config_data, f, indent=4)
