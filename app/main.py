import os
from flask import Flask, render_template, request, jsonify
from app.scraper import start_scheduler
from app.config_manager import load_config, save_config
from app.pulsepoint import search_agencies

app = Flask(__name__)

# Start background scraper
start_scheduler()

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
            with open('incident_types.txt', 'r') as f:
                content = f.read()
            INCIDENT_TYPES_CACHE = []
            
            # Parse <option value="AED" label="AED Alarm">
            pattern = re.compile(r'<option value="([^"]+)" label="([^"]+)">')
            matches = pattern.findall(content)
            for val, label in matches:
                INCIDENT_TYPES_CACHE.append({
                    "id": val,
                    "name": label
                })
        except Exception as e:
            print(f"Error reading incident types: {e}")
            INCIDENT_TYPES_CACHE = []
    return jsonify(INCIDENT_TYPES_CACHE)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
