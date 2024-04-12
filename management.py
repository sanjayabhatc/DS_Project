from flask import Flask, request, jsonify, render_template
import threading
import logging
from datetime import datetime, timedelta
import requests
import time
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

logging.basicConfig(level=logging.INFO)

lock = threading.Lock()
heartbeats = {}
current_leader = None

LOAD_BALANCER_URL = 'http://localhost:5000'  

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    server_info = request.json
    with lock:
        heartbeats[server_info['server_id']] = {'last_seen': datetime.now(), 'port': server_info['port']}
    return jsonify({"status": f"Heartbeat received from server {server_info['server_id']}"})

current_worker_index = 0


worker_ports = [5001, 5002, 5003]  

def round_robin():
    global current_worker_index
    if not worker_ports:
        return None
    next_worker_port = worker_ports[current_worker_index]
    current_worker_index = (current_worker_index + 1) % len(worker_ports)
    return next_worker_port

@app.route('/execute_code', methods=['POST'])
def execute_code():
    code = request.json['code']
    with lock:
        if current_leader and current_leader in heartbeats:
            leader_port = heartbeats[current_leader]['port']
            try:
                response = requests.post(f'http://localhost:{leader_port}/execute', json={'code': code}, timeout=5)
                return jsonify(response.json())
            except requests.exceptions.RequestException as e:
                pass  
        selected_worker_port = round_robin()
        if selected_worker_port:
            try:
                response = requests.post(f'http://localhost:{selected_worker_port}/execute', json={'code': code}, timeout=5)
                return jsonify(response.json())
            except requests.exceptions.RequestException as e:
                return jsonify({"error": f"Failed to forward execution request to worker server {selected_worker_port}"}), 502
        
        return jsonify({"error": "No leader elected and no worker servers available"}), 503

def monitor_heartbeats_and_elect_leader():
    global current_leader
    while True:
        with lock:
            now = datetime.now()
            for server_id, info in list(heartbeats.items()):
                if now - info['last_seen'] > timedelta(seconds=15):
                    logging.info(f"Server {server_id} missed the heartbeat. Removing from active servers.")
                    del heartbeats[server_id]

            if current_leader is None or current_leader not in heartbeats:
                elect_leader_based_on_bully_algorithm()
        time.sleep(5)

def elect_leader_based_on_bully_algorithm():
    global current_leader
    if heartbeats:
        current_leader = max(heartbeats.keys(), key=int)
        logging.info(f"Elected Server {current_leader} as the new leader based on the Bully Algorithm.")
    else:
        current_leader = None
        logging.warning("No servers available to elect as leader.")

@app.route('/get_leader', methods=['GET'])
def get_leader():
    if current_leader:
        return jsonify({"current_leader": current_leader})
    else:
        return jsonify({"error": "No leader elected yet"}), 503
    

if __name__ == "__main__":
    threading.Thread(target=monitor_heartbeats_and_elect_leader, daemon=True).start()
    app.run(port=5000, debug=True)
