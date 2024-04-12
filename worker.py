from flask import Flask, request, jsonify
import subprocess
import requests
import os
import threading
import time
from flask_cors import CORS
import logging

app = Flask(__name__)
CORS(app)

SERVER_ID = int(os.getenv('SERVER_ID', '1'))
PORT = int(os.getenv('PORT', '5001'))
MANAGEMENT_SERVER = 'http://localhost:5000'
IS_LEADER = False
WORKERS = {
    1: 5001,
    2: 5002,
}

def execute_code_safe(code):
    try:
        result = subprocess.check_output(["python3", "-c", code], stderr=subprocess.STDOUT, text=True)
        return True, result.strip()
    except subprocess.CalledProcessError as e:
        return False, e.output.strip()

@app.route('/execute', methods=['POST'])
def execute():
    global IS_LEADER
    if not IS_LEADER:
        return jsonify({"error": "Not the leader"}), 403
    code = request.json['code']
    success, output = execute_code_safe(code)
    if success:
        return jsonify({"output": output})
    else:
        return jsonify({"error": output})

@app.route('/election', methods=['POST'])
def election():
    global IS_LEADER
    server_id = request.json['server_id']
    if server_id < SERVER_ID:  # Respond only if the current server has a higher ID
        initiate_election()
    return jsonify({"message": "Election message received"}), 200

def send_heartbeat():
    global IS_LEADER
    while True:
        try:
            response = requests.post(f'{MANAGEMENT_SERVER}/heartbeat', json={'server_id': SERVER_ID, 'port': PORT})
            if IS_LEADER:
                announce_leader_to_management()
        except requests.exceptions.RequestException as e:
            print(f"Failed to send heartbeat: {e}")
        time.sleep(5)

def initiate_election():
    global IS_LEADER
    higher_ids_exist = False
    for id, port in WORKERS.items():
        if id > SERVER_ID:
            try:
                response = requests.post(f'http://localhost:{port}/election', json={'server_id': SERVER_ID}, timeout=1)
                if response.status_code == 200:
                    higher_ids_exist = True
                    break  
            except requests.exceptions.RequestException:
                continue  
    if not higher_ids_exist:
        IS_LEADER = True
        announce_leader_to_management()

def announce_leader_to_management():
    try:
        requests.post(f'{MANAGEMENT_SERVER}/announce_leader', json={'server_id': SERVER_ID, 'port': PORT})
    except requests.exceptions.RequestException as e:
        print(f"Failed to announce leadership: {e}")


LOAD_BALANCER_URL = 'http://localhost:5000'  

def register_with_load_balancer():
    try:
        response = requests.post(f'{LOAD_BALANCER_URL}/register', json={'server_id': SERVER_ID, 'port': PORT}, timeout=5)
        if response.status_code == 200:
            logging.info("Registered with the load balancer successfully.")
    except requests.exceptions.RequestException as e:
        logging.error(f"Failed to register with the load balancer: {e}")

if __name__ == "__main__":
    threading.Thread(target=register_with_load_balancer, daemon=True).start()


if __name__ == '__main__':
    threading.Thread(target=initiate_election, daemon=True).start()
    threading.Thread(target=send_heartbeat, daemon=True).start()
    app.run(host='0.0.0.0', port=PORT)
