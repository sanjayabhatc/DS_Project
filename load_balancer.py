from flask import Flask, request, jsonify
import threading
import random
import requests

app = Flask(__name__)

workers = []

def round_robin():
    if workers:
        return random.choice(workers)
    return None

@app.route('/execute', methods=['POST'])
def execute():
    code = request.json['code']
    selected_worker = round_robin()
    if selected_worker:
        try:
            response = requests.post(f'http://localhost:{selected_worker}/execute', json={'code': code}, timeout=5)
            return jsonify(response.json())
        except requests.exceptions.RequestException as e:
            return jsonify({"error": f"Failed to forward execution request to worker server {selected_worker}"}), 502
    else:
        return jsonify({"error": "No worker servers available"}), 503

@app.route('/register', methods=['POST'])
def register():
    server_info = request.json
    workers.append(server_info['port'])
    return jsonify({"status": f"Registered worker server {server_info['port']}"}), 200

if __name__ == "__main__":
    app.run(port=5000)
