## Running the Application

This project requires three separate terminal sessions to run the worker processes and the management server. Here's how to set it up:

**Prerequisites:**

* Python 3 (https://www.python.org/downloads/)

**Steps:**

1. **Open three terminal windows.**

2. **In Terminal 1 (Worker Process 1):**
```
set SERVER_ID=1
set PORT=5001
python worker.py
```
3. **In Terminal 2 (Worker Process 2):**
```
set SERVER_ID=2
set PORT=5002
python worker.py
```
4. **In Terminal 3 (Management Process 1):**
```
set PORT=5000
python management.py
```
