import json
import os

CONFIG_FILE = os.environ.get('CONFIG_FILE_PATH', 'data/config.json')

DEFAULT_CONFIG = {
    "agencies": [], # list of strings like "06140"
    "incidentTypes": [], # list of strings like "TC", "ME"
    "polygons": [], # list of geojson polygons or custom structural dicts
    "notifications": {
        "discordWebhookUrl": "",
        "pushoverUserKey": "",
        "pushoverAppToken": "",
        "vehicleThreshold": 5,
        "timezone": "America/Vancouver",
        "pushoverSoundNormal": "pushover",
        "pushoverSoundHigh": "siren",
        "helicopterAlert": {
            "enabled": False,
            "unitPattern": "S"
        }
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
