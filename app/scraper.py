import time
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from app.pulsepoint import get_incidents
from app.config_manager import load_config
from app.geo import is_point_in_polygons
from app.notifications import (
    notify_new_incident, notify_incident_escalation, notify_special_unit,
    match_unit_type, classify_units, format_unit_breakdown
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

            if inc_id not in KNOWN_INCIDENTS:
                # New Incident!
                KNOWN_INCIDENTS[inc_id] = {
                    'notified_new': True,
                    'reported_units': active_units_count,
                    'escalated': False,
                    'special_notified': set(),  # Track which special types we've notified
                    'classification': classification,
                    'last_escalation_classification': None
                }
                print(f"New Incident Detected! {inc_id} ({inc_type}) — {unit_breakdown}")
                notify_new_incident(inc, unit_breakdown=unit_breakdown)

            state = KNOWN_INCIDENTS[inc_id]

            # Update classification
            prev_classification = state.get('classification', {})
            state['classification'] = classification

            # Check for Escalation Condition
            if active_units_count >= threshold and not state.get('escalated'):
                # Build breakdown with delta markers from previous state
                last_esc = state.get('last_escalation_classification') or prev_classification
                esc_breakdown = format_unit_breakdown(classification, last_esc)
                print(f"Escalation condition met for {inc_id}. {active_units_count} units. {esc_breakdown}")
                notify_incident_escalation(inc, active_units_count, unit_breakdown=esc_breakdown)
                state['escalated'] = True
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
