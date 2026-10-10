"""Posts a sample pothole report WITH a photo to your running CivicFix server
and prints exactly what the server answers.
1) Start the server in one terminal:  uvicorn main:app --reload
2) In a second terminal (venv active):  python test_app.py"""
import base64
import json
import urllib.error
import urllib.request
import uuid

PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)
fields = {
    "category": "pothole", "report_id": "99", "is_update": "false", "urgency": "70",
    "reason": "test report", "count": "1", "x_m": "100", "y_m": "100",
    "confidence": "0.9", "note": "test from test_app.py",
}
b = uuid.uuid4().hex
parts = []
for k, v in fields.items():
    parts.append(f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
parts.append(
    f'--{b}\r\nContent-Disposition: form-data; name="photo"; filename="pothole.png"\r\n'
    f"Content-Type: image/png\r\n\r\n".encode() + PNG + b"\r\n"
)
parts.append(f"--{b}--\r\n".encode())
req = urllib.request.Request(
    "http://localhost:8000/api/report", data=b"".join(parts), method="POST",
    headers={"Content-Type": f"multipart/form-data; boundary={b}"},
)
try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print("HTTP", r.status, json.loads(r.read().decode()))
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode())
except Exception as e:
    print("Could not reach the server (is uvicorn running?):", e)
