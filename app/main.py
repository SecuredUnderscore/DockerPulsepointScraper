import os
from flask import Flask, render_template, request, jsonify
from app.scraper import start_scheduler, process_incidents
from app.config_manager import load_config, save_config
from app.pulsepoint import search_agencies

app = Flask(__name__)

# Start background scraper
start_scheduler()
# Run first scrape immediately instead of waiting for the 1-minute interval
process_incidents()

# Global caches
AGENCIES_CACHE = None
INCIDENT_TYPES_CACHE = None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/agencies')
def agencies():
    return render_template('agencies.html')

@app.route('/incident_types')
def incident_types():
    return render_template('incident_types.html')

@app.route('/map')
def map_view():
    return render_template('map.html')

@app.route('/notifications')
def notifications():
    return render_template('notifications.html')

# --- API Routes for config UI ---

@app.route('/api/config', methods=['GET'])
def get_config():
    config = load_config()
    return jsonify(config)

@app.route('/api/config', methods=['POST'])
def update_config():
    data = request.json
    save_config(data)
    return jsonify({"status": "success"})
    
@app.route('/api/agencies', methods=['GET'])
def get_agencies_list():
    global AGENCIES_CACHE
    if not AGENCIES_CACHE:
        # Fetch from pulsepoint and cache
        res = search_agencies()
        AGENCIES_CACHE = res.get('searchagencies', [])
    return jsonify(AGENCIES_CACHE)
    
import re

@app.route('/api/incident_types', methods=['GET'])
def get_incident_types_list():
    global INCIDENT_TYPES_CACHE
    if not INCIDENT_TYPES_CACHE:
        try:
            # Safely locate the json file inside the app directory
            json_path = os.path.join(os.path.dirname(__file__), 'incident_types.json')
            import json
            with open(json_path, 'r') as f:
                INCIDENT_TYPES_CACHE = json.load(f)
        except Exception as e:
            print(f"Error reading incident types json: {e}")
            INCIDENT_TYPES_CACHE = []
    return jsonify(INCIDENT_TYPES_CACHE)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
