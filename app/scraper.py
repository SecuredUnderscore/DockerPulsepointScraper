import time
from apscheduler.schedulers.background import BackgroundScheduler
from app.pulsepoint import get_incidents
from app.config_manager import load_config
from app.geo import is_point_in_polygons
from app.notifications import notify_new_incident, notify_incident_escalation

# State memory
# { 'incident_id': { 'notified_new': True, 'reported_units': 3 } }
KNOWN_INCIDENTS = {}

def process_incidents():
    config = load_config()
    
    agencies = config.get('agencies', [])
    incident_types = config.get('incidentTypes', [])
    polygons = config.get('polygons', [])
    threshold = int(config.get('notifications', {}).get('vehicleThreshold', 5))
    
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
            inc_type = inc.get('Type_Force')
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
                    'escalated': False
                }
                print(f"New Incident Detected! {inc_id} ({inc_type})")
                notify_new_incident(inc)
            
            # Check for Escalation Condition
            state = KNOWN_INCIDENTS[inc_id]
            if active_units_count >= threshold and not state.get('escalated'):
                print(f"Escalation condition met for {inc_id}. {active_units_count} units.")
                notify_incident_escalation(inc, active_units_count)
                state['escalated'] = True
            
            # Keep highest count
            if active_units_count > state['reported_units']:
                state['reported_units'] = active_units_count

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(process_incidents, 'interval', minutes=1)
    scheduler.start()
    print("Scraper background scheduler started!")
