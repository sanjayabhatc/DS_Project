from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import subprocess
import threading
import logging
import os
from time import sleep, time
import requests

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
CORS(app)  # Enable CORS on all routes

# Environment variables for server configuration
SERVER_ID = int(os.getenv('SERVER_ID', '1'))
PORT = int(os.getenv('PORT', '5000'))

# Information about the servers in the network
SERVERS_INFO = {
    1: {"host": "127.0.0.1", "port": 5000},
    2: {"host": "127.0.0.1", "port": 5001},
    3: {"host": "127.0.0.1", "port": 5002},
}

LEADER_ID = None
IS_LEADER = False

@app.route('/')
def index():
    # Serve the HTML page
    return render_template('index.html')

def execute_code_safe(code):
    try:
        result = subprocess.check_output(["python3", "-c", code], stderr=subprocess.STDOUT, text=True)
        return result.strip(), None
    except subprocess.CalledProcessError as e:
        return None, e.output.strip()

@app.route('/execute', methods=['POST'])
def execute():
    global LEADER_ID, IS_LEADER
    if LEADER_ID is None:
        return jsonify({"error": "Leader has not been elected yet. Try again later."}), 503

    code = request.json['code']
    if not IS_LEADER:
        leader_info = SERVERS_INFO[LEADER_ID]
        response = requests.post(f"http://{leader_info['host']}:{leader_info['port']}/execute", json={"code": code})
        return jsonify(response.json())

    output, error = execute_code_safe(code)
    if output:
        return jsonify({"output": output})
    else:
        return jsonify({"error": error}), 400

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "up"}), 200

@app.route('/leader', methods=['POST'])
def set_leader():
    global LEADER_ID, IS_LEADER
    LEADER_ID = request.json.get('leader_id')
    IS_LEADER = (LEADER_ID == SERVER_ID)
    logging.info(f"Server {SERVER_ID}: Leader set to {LEADER_ID}")
    return jsonify({"status": "leader set", "leader_id": LEADER_ID}), 200

def elect_leader():
    global LEADER_ID, IS_LEADER
    sleep(5)  # Initial delay to allow all servers to start
    while True:
        if LEADER_ID is None or not IS_LEADER:
            logging.info(f"Server {SERVER_ID} starting the leader election process.")
            candidates = [sid for sid in SERVERS_INFO if sid > SERVER_ID]
            for sid in candidates:
                try:
                    resp = requests.get(f"http://{SERVERS_INFO[sid]['host']}:{SERVERS_INFO[sid]['port']}/health", timeout=2)
                    if resp.status_code == 200:
                        logging.info(f"Server {sid} is up. Server {SERVER_ID} will not be the leader.")
                        break
                except requests.exceptions.RequestException:
                    continue  # Server sid is not reachable or down

            # If no higher ID server is up, or all requests failed, this server becomes the leader
            else:
                LEADER_ID = SERVER_ID
                IS_LEADER = True
                logging.info(f"Server {SERVER_ID} has elected itself as the leader.")
                # Notify other servers
                for sid, info in SERVERS_INFO.items():
                    if sid != SERVER_ID:
                        try:
                            requests.post(f"http://{info['host']}:{info['port']}/leader", json={"leader_id": SERVER_ID}, timeout=2)
                            logging.info(f"Server {SERVER_ID} notified Server {sid} of its leadership.")
                        except requests.exceptions.RequestException as e:
                            logging.error(f"Server {SERVER_ID} failed to notify Server {sid} of its leadership: {e}")
        sleep(5)

if __name__ == '__main__':
    elect_leader_thread = threading.Thread(target=elect_leader, daemon=True)
    elect_leader_thread.start()
    app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
