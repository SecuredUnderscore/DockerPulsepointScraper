import re
import requests
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
from app.config_manager import load_config

def format_local_time(utc_time_str, tz_name):
    """Convert a UTC datetime string like '2026-03-24T05:19:38Z' to local time."""
    if not utc_time_str:
        return 'Unknown'
    try:
        dt = datetime.fromisoformat(utc_time_str.replace('Z', '+00:00'))
        local_tz = ZoneInfo(tz_name)
        local_dt = dt.astimezone(local_tz)
        return local_dt.strftime('%b %d, %Y %I:%M %p %Z')
    except Exception:
        return utc_time_str

def google_maps_url(lat, lon):
    """Generate a Google Maps pin link from lat/lon."""
    if lat and lon:
        return f"https://www.google.com/maps?q={lat},{lon}"
    return None

def is_helicopter_unit(unit_id, pattern):
    """Check if a unit ID contains the helicopter pattern character.
    Pattern is matched as a letter within the unit ID, e.g. 'S' matches '1S41N', '3S41'.
    We look for the pattern character surrounded by digits (or at start/end)."""
    if not unit_id or not pattern:
        return False
    # Match the pattern as a character in the unit ID (case-insensitive)
    return bool(re.search(r'\d' + re.escape(pattern), unit_id, re.IGNORECASE))

def build_description(incident, tz_name):
    """Build common description fields for notifications."""
    lat = incident.get('Latitude')
    lon = incident.get('Longitude')
    local_time = format_local_time(incident.get('CallReceivedDateTime'), tz_name)
    maps_link = google_maps_url(lat, lon)
    
    # Unit list
    units = incident.get('Unit', [])
    unit_ids = [u.get('UnitID', '?') for u in units] if isinstance(units, list) else []
    
    return local_time, maps_link, unit_ids

def send_discord_notification(webhook_url, incident, tz_name, units_count=None, is_helicopter=False, heli_units=None):
    if not webhook_url:
        return
    
    inc_type = incident.get('PulsePointIncidentCallType', 'Unknown Type')
    
    if is_helicopter:
        title = f"🚁 Helicopter Dispatched: {inc_type}"
    elif units_count:
        title = f"⚠️ Incident Escalation: {inc_type} ({units_count} Units)"
    else:
        title = f"🔴 New Incident: {inc_type}"
    
    local_time, maps_link, unit_ids = build_description(incident, tz_name)
    
    description = f"**📍 Location:** {incident.get('FullDisplayAddress', 'Unknown Location')}\n"
    description += f"**🏢 Agency:** {incident.get('AgencyID', 'Unknown')}\n"
    description += f"**🕐 Time:** {local_time}\n"
    
    if unit_ids:
        description += f"**🚒 Units:** {', '.join(unit_ids)}\n"
    
    if is_helicopter and heli_units:
        description += f"**🚁 Helicopter Units:** {', '.join(heli_units)}\n"
    
    if maps_link:
        description += f"**🗺️ Map:** [Google Maps]({maps_link})\n"
    
    # Color: orange for helicopter, yellow for escalation, red for new
    if is_helicopter:
        color = 0xFF8C00  # Dark orange
    elif units_count:
        color = 0xFFAA00  # Amber
    else:
        color = 0xFF0000  # Red
    
    payload = {
        "username": "PulsePoint Scanner",
        "embeds": [
            {
                "title": title,
                "description": description,
                "color": color
            }
        ]
    }
    
    try:
        resp = requests.post(webhook_url, json=payload)
        if not resp.ok:
            print(f"Discord webhook returned {resp.status_code}: {resp.text}")
    except Exception as e:
        print(f"Error sending Discord notification: {e}")

def send_pushover_notification(user_key, app_token, incident, tz_name, units_count=None, is_helicopter=False, heli_units=None, priority=0, sound="pushover"):
    if not user_key or not app_token:
        return
    
    inc_type = incident.get('PulsePointIncidentCallType', 'Unknown Type')
    
    if is_helicopter:
        title = f"🚁 Helicopter Dispatched: {inc_type}"
    elif units_count:
        title = f"Incident Escalation: {inc_type} ({units_count} Units)"
    else:
        title = f"New Incident: {inc_type}"
    
    local_time, maps_link, unit_ids = build_description(incident, tz_name)
    
    message = f"Location: {incident.get('FullDisplayAddress', 'Unknown Location')}\n"
    message += f"Agency: {incident.get('AgencyID', 'Unknown')}\n"
    message += f"Time: {local_time}\n"
    
    if unit_ids:
        message += f"Units: {', '.join(unit_ids)}\n"
    
    if is_helicopter and heli_units:
        message += f"Helicopter Units: {', '.join(heli_units)}\n"
    
    if maps_link:
        message += f"Map: {maps_link}"
    
    payload = {
        "token": app_token,
        "user": user_key,
        "title": title,
        "message": message,
        "url": maps_link or "",
        "url_title": "View on Google Maps",
        "priority": priority,
        "sound": sound
    }
    
    # Priority 1 (high) requires retry and expire parameters
    if priority >= 1:
        payload["retry"] = 60
        payload["expire"] = 300
    
    try:
        requests.post("https://api.pushover.net/1/messages.json", data=payload)
    except Exception as e:
        print(f"Error sending Pushover notification: {e}")

def _get_notif_config():
    config = load_config()
    notif_config = config.get('notifications', {})
    return notif_config

def notify_new_incident(incident):
    notif_config = _get_notif_config()
    tz_name = notif_config.get('timezone', 'UTC')
    discord_url = notif_config.get('discordWebhookUrl')
    push_user = notif_config.get('pushoverUserKey')
    push_app = notif_config.get('pushoverAppToken')
    sound_normal = notif_config.get('pushoverSoundNormal', 'pushover')
    
    send_discord_notification(discord_url, incident, tz_name)
    send_pushover_notification(push_user, push_app, incident, tz_name, priority=0, sound=sound_normal)

def notify_incident_escalation(incident, active_units):
    notif_config = _get_notif_config()
    tz_name = notif_config.get('timezone', 'UTC')
    discord_url = notif_config.get('discordWebhookUrl')
    push_user = notif_config.get('pushoverUserKey')
    push_app = notif_config.get('pushoverAppToken')
    sound_normal = notif_config.get('pushoverSoundNormal', 'pushover')
    
    send_discord_notification(discord_url, incident, tz_name, units_count=active_units)
    send_pushover_notification(push_user, push_app, incident, tz_name, units_count=active_units, priority=0, sound=sound_normal)

def notify_helicopter(incident, heli_units):
    notif_config = _get_notif_config()
    tz_name = notif_config.get('timezone', 'UTC')
    discord_url = notif_config.get('discordWebhookUrl')
    push_user = notif_config.get('pushoverUserKey')
    push_app = notif_config.get('pushoverAppToken')
    sound_high = notif_config.get('pushoverSoundHigh', 'siren')
    
    send_discord_notification(discord_url, incident, tz_name, is_helicopter=True, heli_units=heli_units)
    send_pushover_notification(push_user, push_app, incident, tz_name, is_helicopter=True, heli_units=heli_units, priority=1, sound=sound_high)
