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


def match_unit_type(unit_id, pattern):
    """Check if a unit ID contains the given type pattern character.
    Pattern is matched as a letter within the unit ID after a digit,
    e.g. 'S' matches '1S40D', '5S31'; 'A' matches '140A3D'."""
    if not unit_id or not pattern:
        return False
    return bool(re.search(r'\d' + re.escape(pattern), unit_id, re.IGNORECASE))


def classify_units(units, unit_types_config):
    """Classify a list of unit dicts into types based on configured patterns.

    Returns a dict: { 'label': { 'emoji': str, 'count': int, 'unit_ids': [str], 'specialAlert': bool } }
    Also includes an 'Unknown' bucket for unmatched units.
    """
    classification = {}
    unmatched = []

    unit_ids = [u.get('UnitID', '?') for u in units] if isinstance(units, list) else []

    for uid in unit_ids:
        matched = False
        for ut in unit_types_config:
            pattern = ut.get('pattern', '')
            if match_unit_type(uid, pattern):
                label = ut.get('label', pattern)
                if label not in classification:
                    classification[label] = {
                        'emoji': ut.get('emoji', '🔹'),
                        'count': 0,
                        'unit_ids': [],
                        'specialAlert': ut.get('specialAlert', False)
                    }
                classification[label]['count'] += 1
                classification[label]['unit_ids'].append(uid)
                matched = True
                break  # First matching pattern wins
        if not matched:
            unmatched.append(uid)

    if unmatched:
        classification['Other'] = {
            'emoji': '🔹',
            'count': len(unmatched),
            'unit_ids': unmatched,
            'specialAlert': False
        }

    return classification


def format_unit_breakdown(classification, prev_classification=None):
    """Format unit types into a readable string like 'Ambulance (x2), Helicopter (x1)'.

    If prev_classification is provided, adds '+' markers for new units since last alert.
    Example: 'Ambulance (x4)++' means 2 new ambulances added since last alert.
    """
    parts = []
    for label, info in sorted(classification.items(), key=lambda x: -x[1]['count']):
        count = info['count']
        emoji = info['emoji']
        entry = f"{emoji} {label} (x{count})"

        if prev_classification and label in prev_classification:
            prev_count = prev_classification[label]['count']
            new_count = count - prev_count
            if new_count > 0:
                entry += '+' * new_count
        elif prev_classification:
            # Entirely new type since last escalation
            entry += '+' * count

        parts.append(entry)

    return ', '.join(parts) if parts else 'None'


def build_description(incident, tz_name):
    """Build common description fields for notifications."""
    lat = incident.get('Latitude')
    lon = incident.get('Longitude')
    local_time = format_local_time(incident.get('CallReceivedDateTime'), tz_name)
    maps_link = google_maps_url(lat, lon)

    units = incident.get('Unit', [])
    unit_ids = [u.get('UnitID', '?') for u in units] if isinstance(units, list) else []

    return local_time, maps_link, unit_ids


def send_discord_notification(webhook_url, incident, tz_name, alert_type='new',
                              units_count=None, unit_breakdown='',
                              special_units=None, special_label='',
                              old_lat=None, old_lon=None):
    if not webhook_url:
        return

    inc_type = incident.get('PulsePointIncidentCallType', 'Unknown Type')

    if alert_type == 'special':
        title = f"🚨 {special_label} Dispatched: {inc_type}"
    elif alert_type == 'escalation':
        title = f"⚠️ Incident Escalation: {inc_type} ({units_count} Units)"
    elif alert_type == 'location':
        title = f"📍 Location Moved: {inc_type}"
    else:
        title = f"🔴 New Incident: {inc_type}"

    local_time, maps_link, unit_ids = build_description(incident, tz_name)

    description = f"**📍 Location:** {incident.get('FullDisplayAddress', 'Unknown Location')}\n"
    description += f"**🏢 Agency:** {incident.get('AgencyID', 'Unknown')}\n"
    description += f"**🕐 Time:** {local_time}\n"

    if unit_breakdown:
        description += f"**📊 Units:** {unit_breakdown}\n"
    elif unit_ids:
        description += f"**🚒 Units:** {', '.join(unit_ids)}\n"

    if alert_type == 'special' and special_units:
        description += f"**🚨 {special_label}:** {', '.join(special_units)}\n"

    if alert_type == 'location' and old_lat and old_lon:
        old_maps = google_maps_url(old_lat, old_lon)
        description += f"**📌 Previous:** [Old Location]({old_maps})\n"

    if maps_link:
        description += f"**🗺️ Map:** [Google Maps]({maps_link})\n"

    # Color: orange for special, yellow for escalation, purple for location, red for new
    if alert_type == 'special':
        color = 0xFF8C00  # Dark orange
    elif alert_type == 'escalation':
        color = 0xFFAA00  # Amber
    elif alert_type == 'location':
        color = 0x9B59B6  # Purple
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


def send_pushover_notification(user_key, app_token, incident, tz_name,
                               alert_type='new', units_count=None,
                               unit_breakdown='', special_units=None,
                               special_label='', priority=0, sound="pushover",
                               old_lat=None, old_lon=None):
    if not user_key or not app_token:
        return

    inc_type = incident.get('PulsePointIncidentCallType', 'Unknown Type')

    if alert_type == 'special':
        title = f"🚨 {special_label} Dispatched: {inc_type}"
    elif alert_type == 'escalation':
        title = f"Incident Escalation: {inc_type} ({units_count} Units)"
    elif alert_type == 'location':
        title = f"📍 Location Moved: {inc_type}"
    else:
        title = f"New Incident: {inc_type}"

    local_time, maps_link, unit_ids = build_description(incident, tz_name)

    message = f"Location: {incident.get('FullDisplayAddress', 'Unknown Location')}\n"
    message += f"Agency: {incident.get('AgencyID', 'Unknown')}\n"
    message += f"Time: {local_time}\n"

    if unit_breakdown:
        message += f"Units: {unit_breakdown}\n"
    elif unit_ids:
        message += f"Units: {', '.join(unit_ids)}\n"

    if alert_type == 'special' and special_units:
        message += f"{special_label}: {', '.join(special_units)}\n"

    if alert_type == 'location' and old_lat and old_lon:
        old_maps = google_maps_url(old_lat, old_lon)
        message += f"Previous: {old_maps}\n"

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


def notify_new_incident(incident, unit_breakdown=''):
    notif_config = _get_notif_config()
    alerts = notif_config.get('alerts', {})
    new_alert = alerts.get('new', {})

    if not new_alert.get('enabled', True):
        return

    tz_name = notif_config.get('timezone', 'UTC')
    discord_url = notif_config.get('discordWebhookUrl')
    push_user = notif_config.get('pushoverUserKey')
    push_app = notif_config.get('pushoverAppToken')
    sound = new_alert.get('pushoverSound', 'pushover')
    priority = new_alert.get('pushoverPriority', 0)

    send_discord_notification(discord_url, incident, tz_name,
                              alert_type='new', unit_breakdown=unit_breakdown)
    send_pushover_notification(push_user, push_app, incident, tz_name,
                               alert_type='new', unit_breakdown=unit_breakdown,
                               priority=priority, sound=sound)


def notify_incident_escalation(incident, active_units, unit_breakdown=''):
    notif_config = _get_notif_config()
    alerts = notif_config.get('alerts', {})
    esc_alert = alerts.get('escalation', {})

    if not esc_alert.get('enabled', True):
        return

    tz_name = notif_config.get('timezone', 'UTC')
    discord_url = notif_config.get('discordWebhookUrl')
    push_user = notif_config.get('pushoverUserKey')
    push_app = notif_config.get('pushoverAppToken')
    sound = esc_alert.get('pushoverSound', 'pushover')
    priority = esc_alert.get('pushoverPriority', 0)

    send_discord_notification(discord_url, incident, tz_name,
                              alert_type='escalation', units_count=active_units,
                              unit_breakdown=unit_breakdown)
    send_pushover_notification(push_user, push_app, incident, tz_name,
                               alert_type='escalation', units_count=active_units,
                               unit_breakdown=unit_breakdown,
                               priority=priority, sound=sound)


def notify_special_unit(incident, special_unit_ids, special_label, unit_breakdown=''):
    notif_config = _get_notif_config()
    alerts = notif_config.get('alerts', {})
    special_alert = alerts.get('specialUnit', {})

    if not special_alert.get('enabled', True):
        return

    tz_name = notif_config.get('timezone', 'UTC')
    discord_url = notif_config.get('discordWebhookUrl')
    push_user = notif_config.get('pushoverUserKey')
    push_app = notif_config.get('pushoverAppToken')
    sound = special_alert.get('pushoverSound', 'siren')
    priority = special_alert.get('pushoverPriority', 1)

    send_discord_notification(discord_url, incident, tz_name,
                              alert_type='special', special_units=special_unit_ids,
                              special_label=special_label, unit_breakdown=unit_breakdown)
    send_pushover_notification(push_user, push_app, incident, tz_name,
                               alert_type='special', special_units=special_unit_ids,
                               special_label=special_label, unit_breakdown=unit_breakdown,
                               priority=priority, sound=sound)


def notify_location_moved(incident, old_lat, old_lon, unit_breakdown=''):
    notif_config = _get_notif_config()
    alerts = notif_config.get('alerts', {})
    loc_alert = alerts.get('locationMoved', {})

    if not loc_alert.get('enabled', True):
        return

    tz_name = notif_config.get('timezone', 'UTC')
    discord_url = notif_config.get('discordWebhookUrl')
    push_user = notif_config.get('pushoverUserKey')
    push_app = notif_config.get('pushoverAppToken')
    sound = loc_alert.get('pushoverSound', 'pushover')
    priority = loc_alert.get('pushoverPriority', 0)

    send_discord_notification(discord_url, incident, tz_name,
                              alert_type='location', unit_breakdown=unit_breakdown,
                              old_lat=old_lat, old_lon=old_lon)
    send_pushover_notification(push_user, push_app, incident, tz_name,
                               alert_type='location', unit_breakdown=unit_breakdown,
                               old_lat=old_lat, old_lon=old_lon,
                               priority=priority, sound=sound)
