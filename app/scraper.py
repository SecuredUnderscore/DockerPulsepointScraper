import json
import hashlib
import time
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from app.pulsepoint import get_incidents
from app.config_manager import load_config
from app.geo import is_point_in_polygons
from app.notifications import (
    notify_new_incident, notify_incident_escalation, notify_special_unit,
    notify_location_moved, send_webhook_update, match_unit_type, classify_units,
    format_unit_breakdown
)

# State memory
# { 'incident_id': { 'notified_new': True, 'reported_units': 3, 'classification': {...}, ... } }
KNOWN_INCIDENTS = {}

def process_incidents():
    config = load_config()

    agencies = config.get('agencies', [])
    incident_types = config.get('incidentTypes', [])
    polygons = config.get('polygons', [])
    notif_config = config.get('notifications', {})
    threshold = int(notif_config.get('vehicleThreshold', 5))

    # Unit type config
    unit_types = notif_config.get('unitTypes', [])

    if not agencies:
        print("No agencies configured. Skipping scrape.")
        return

    for agency_id in agencies:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Scraping {agency_id}...")
        res = get_incidents(agency_id)

        # Structure is usually: {"incidents": {"active": [ ... ]}}
        incidents_data = res.get('incidents', {})
        active_incidents = incidents_data.get('active', [])

        for inc in active_incidents:
            inc_id = inc.get('ID')
            inc_type = inc.get('PulsePointIncidentCallType')
            lat = inc.get('Latitude')
            lon = inc.get('Longitude')

            if not inc_id:
                continue

            # Filter by Incident Type
            if incident_types and inc_type not in incident_types:
                continue

            # Filter by Polygon GeoFencing
            if polygons and lat and lon:
                if not is_point_in_polygons(lat, lon, polygons):
                    continue

            # Count Units (Usually in 'Unit' array)
            units = inc.get('Unit', [])
            active_units_count = len(units) if isinstance(units, list) else 0

            # Classify units by type
            classification = classify_units(units, unit_types) if unit_types else {}
            unit_breakdown = format_unit_breakdown(classification)

            # Compute a hash of the raw incident data to detect ANY change
            inc_hash = hashlib.md5(json.dumps(inc, sort_keys=True, default=str).encode()).hexdigest()

            if inc_id not in KNOWN_INCIDENTS:
                # New Incident!
                KNOWN_INCIDENTS[inc_id] = {
                    'notified_new': True,
                    'reported_units': active_units_count,
                    'last_escalation_units': 0,  # Unit count at last escalation trigger
                    'special_notified': set(),  # Track which special types we've notified
                    'classification': classification,
                    'last_escalation_classification': None,
                    'latitude': lat,
                    'longitude': lon,
                    'raw_hash': inc_hash
                }
                print(f"New Incident Detected! {inc_id} ({inc_type}) — {unit_breakdown}")
                notify_new_incident(inc, unit_breakdown=unit_breakdown)
                send_webhook_update(inc)

            state = KNOWN_INCIDENTS[inc_id]

            # Update classification
            prev_classification = state.get('classification', {})
            state['classification'] = classification

            # Check for Escalation Condition (repeating threshold)
            # Triggers every time unit count increases by >= threshold from the last trigger point
            last_esc_units = state.get('last_escalation_units', 0)
            if active_units_count >= threshold and (active_units_count - last_esc_units) >= threshold:
                # Build breakdown with delta markers from previous state
                last_esc = state.get('last_escalation_classification') or prev_classification
                esc_breakdown = format_unit_breakdown(classification, last_esc)
                print(f"Escalation condition met for {inc_id}. {active_units_count} units (prev trigger at {last_esc_units}). {esc_breakdown}")
                notify_incident_escalation(inc, active_units_count, unit_breakdown=esc_breakdown)
                state['last_escalation_units'] = active_units_count
                state['last_escalation_classification'] = dict(classification)

            # Check for Special Unit Types
            for label, info in classification.items():
                if info.get('specialAlert') and label not in state.get('special_notified', set()):
                    special_ids = info.get('unit_ids', [])
                    if special_ids:
                        print(f"🚨 Special unit [{label}] detected for {inc_id}: {special_ids}")
                        notify_special_unit(inc, special_ids, label, unit_breakdown=unit_breakdown)
                        state['special_notified'].add(label)

            # Keep highest count
            if active_units_count > state['reported_units']:
                state['reported_units'] = active_units_count

            # Check for Location Moved
            old_lat = state.get('latitude')
            old_lon = state.get('longitude')
            if lat and lon and old_lat and old_lon:
                if str(lat) != str(old_lat) or str(lon) != str(old_lon):
                    print(f"📍 Location moved for {inc_id}: ({old_lat},{old_lon}) → ({lat},{lon})")
                    notify_location_moved(inc, old_lat, old_lon, unit_breakdown=unit_breakdown)
                    state['latitude'] = lat
                    state['longitude'] = lon

            # Webhook: fire on ANY change to incident data
            if inc_hash != state.get('raw_hash'):
                print(f"🔔 Webhook triggered for {inc_id} (data changed)")
                send_webhook_update(inc)
                state['raw_hash'] = inc_hash

# Keep a module-level reference so the scheduler isn't garbage collected
_scheduler = None

def start_scheduler():
    global _scheduler
    config = load_config()
    notif_config = config.get('notifications', {})
    interval_seconds = max(int(notif_config.get('checkIntervalSeconds', 60)), 20)

    _scheduler = BackgroundScheduler()
    _scheduler.add_job(process_incidents, 'interval', seconds=interval_seconds)
    _scheduler.start()
    print(f"Scraper background scheduler started! (interval: {interval_seconds}s)")

def restart_scheduler():
    """Restart the scheduler with updated interval from config."""
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
    start_scheduler()
