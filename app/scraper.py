import time
from apscheduler.schedulers.background import BackgroundScheduler
from app.pulsepoint import get_incidents
from app.config_manager import load_config
from app.geo import is_point_in_polygons
from app.notifications import notify_new_incident, notify_incident_escalation, notify_helicopter, is_helicopter_unit

# State memory
# { 'incident_id': { 'notified_new': True, 'reported_units': 3 } }
KNOWN_INCIDENTS = {}

def process_incidents():
    config = load_config()
    
    agencies = config.get('agencies', [])
    incident_types = config.get('incidentTypes', [])
    polygons = config.get('polygons', [])
    notif_config = config.get('notifications', {})
    threshold = int(notif_config.get('vehicleThreshold', 5))
    
    # Helicopter alert config
    heli_config = notif_config.get('helicopterAlert', {})
    heli_enabled = heli_config.get('enabled', False)
    heli_pattern = heli_config.get('unitPattern', 'S')
    
    if not agencies:
        print("No agencies configured. Skipping scrape.")
        return
        
    for agency_id in agencies:
        print(f"Scraping {agency_id}...")
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
            
            if inc_id not in KNOWN_INCIDENTS:
                # New Incident!
                KNOWN_INCIDENTS[inc_id] = {
                    'notified_new': True,
                    'reported_units': active_units_count,
                    'escalated': False,
                    'heli_notified': False
                }
                print(f"New Incident Detected! {inc_id} ({inc_type})")
                notify_new_incident(inc)
            
            state = KNOWN_INCIDENTS[inc_id]
            
            # Check for Escalation Condition
            if active_units_count >= threshold and not state.get('escalated'):
                print(f"Escalation condition met for {inc_id}. {active_units_count} units.")
                notify_incident_escalation(inc, active_units_count)
                state['escalated'] = True
            
            # Check for Helicopter Units
            if heli_enabled and not state.get('heli_notified'):
                heli_units = [
                    u.get('UnitID', '') for u in units
                    if isinstance(units, list) and is_helicopter_unit(u.get('UnitID', ''), heli_pattern)
                ]
                if heli_units:
                    print(f"🚁 Helicopter detected for {inc_id}: {heli_units}")
                    notify_helicopter(inc, heli_units)
                    state['heli_notified'] = True
            
            # Keep highest count
            if active_units_count > state['reported_units']:
                state['reported_units'] = active_units_count

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(process_incidents, 'interval', minutes=1)
    scheduler.start()
    print("Scraper background scheduler started!")
