import requests
from app.config_manager import load_config

def send_discord_notification(webhook_url, incident, units_count=None):
    if not webhook_url:
        return
        
    title = f"New Incident: {incident.get('Type_Force', 'Unknown Type')}"
    if units_count:
         title = f"Incident Escalation: {incident.get('Type_Force', 'Unknown Type')} ({units_count} Units)"
         
    description = f"**Location:** {incident.get('FullDisplayAddress', 'Unknown Location')}\n"
    description += f"**Agency:** {incident.get('AgencyID', 'Unknown')}\n"
    description += f"**Time:** {incident.get('CallReceivedDateTime', 'Unknown')}\n"
    
    payload = {
        "username": "PulsePoint Scanner",
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": 16711680 # Red
            }
        ]
    }
    
    try:
        requests.post(webhook_url, json=payload)
    except Exception as e:
        print(f"Error sending Discord notification: {e}")

def send_pushover_notification(user_key, app_token, incident, units_count=None):
    if not user_key or not app_token:
        return
        
    title = f"New Incident: {incident.get('Type_Force', 'Unknown Type')}"
    if units_count:
         title = f"Incident Escalation: {incident.get('Type_Force', 'Unknown Type')} ({units_count} Units)"
         
    message = f"Location: {incident.get('FullDisplayAddress', 'Unknown Location')}\n"
    message += f"Agency: {incident.get('AgencyID', 'Unknown')}"
    
    payload = {
        "token": app_token,
        "user": user_key,
        "title": title,
        "message": message
    }
    
    try:
        requests.post("https://api.pushover.net/1/messages.json", data=payload)
    except Exception as e:
        print(f"Error sending Pushover notification: {e}")

def notify_new_incident(incident):
    config = load_config()
    notif_config = config.get('notifications', {})
    
    discord_url = notif_config.get('discordWebhookUrl')
    push_user = notif_config.get('pushoverUserKey')
    push_app = notif_config.get('pushoverAppToken')
    
    send_discord_notification(discord_url, incident)
    send_pushover_notification(push_user, push_app, incident)

def notify_incident_escalation(incident, active_units):
    config = load_config()
    notif_config = config.get('notifications', {})
    
    discord_url = notif_config.get('discordWebhookUrl')
    push_user = notif_config.get('pushoverUserKey')
    push_app = notif_config.get('pushoverAppToken')
    
    send_discord_notification(discord_url, incident, units_count=active_units)
    send_pushover_notification(push_user, push_app, incident, units_count=active_units)
