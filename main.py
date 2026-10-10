from typing import Optional
import base64, json, os, pathlib, time, urllib.error, urllib.request
from collections import defaultdict, deque
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.staticfiles import StaticFiles

load_dotenv()
BASE = pathlib.Path(__file__).parent
OUTBOX = BASE / "outbox"
OUTBOX.mkdir(exist_ok=True)
MAX_BYTES = 10 * 1024 * 1024  # Brevo allows 20 MB per email incl. base64 overhead
BREVO_URL = "https://api.brevo.com/v3/smtp/email"
ALLOWED = {"image/jpeg", "image/png", "image/gif"}

DEPTS = {
    "pothole": ("Roads & Highways Dept", "EMAIL_POTHOLE"),
    "garbage": ("Sanitation Dept", "EMAIL_GARBAGE"),
    "streetlight": ("Street Lighting Dept", "EMAIL_STREETLIGHT"),
    "other": ("Municipal Helpdesk", "EMAIL_OTHER"),
}
app = FastAPI(title="CivicFix AI")
hits = defaultdict(deque)


def rate_limited(ip: str, limit=5, window=60) -> bool:
    """Max `limit` reports per IP per minute, so nobody can spam the authorities."""
    now, q = time.time(), hits[ip]
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        return True
    q.append(now)
    return False


@app.post("/api/report")
def report(
    request: Request,
    category: str = Form(...),
    report_id: int = Form(...),
    is_update: bool = Form(False),
    urgency: int = Form(0),
    reason: str = Form(""),
    count: int = Form(1),
    x_m: int = Form(0),
    y_m: int = Form(0),
    confidence: float = Form(0),
    note: str = Form(""),
    lat: Optional[float] = Form(None),
    lng: Optional[float] = Form(None),
    acc: Optional[float] = Form(None),
    photo: UploadFile = File(None),
):
    if category not in DEPTS:
        raise HTTPException(400, "Unknown category")
    if rate_limited(request.client.host if request.client else "?"):
        raise HTTPException(429, "Too many reports, please wait a minute")
    dept, env_key = DEPTS[category]
    to = os.getenv(env_key, "").strip()
    if not to:
        raise HTTPException(500, f"No recipient set: add {env_key} to .env")

    data = None
    if photo is not None:
        if photo.content_type not in ALLOWED:
            raise HTTPException(400, "Photo must be a JPEG, PNG or GIF")
        data = photo.file.read(MAX_BYTES + 1)
        if len(data) > MAX_BYTES:
            raise HTTPException(413, "Photo too large (max 10 MB)")

    gps_text = ""
    if lat is not None and lng is not None:
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise HTTPException(400, "Invalid GPS coordinates")
        gps_text = (f"GPS: {lat:.6f}, {lng:.6f}" + (f" (accuracy +/-{acc:.0f} m)" if acc else "") + "\n"
                    f"Map: https://www.google.com/maps?q={lat:.6f},{lng:.6f}\n")
    level = "CRITICAL" if urgency >= 70 else "MEDIUM" if urgency >= 40 else "LOW"
    subject = (
        f"[CivicFix] UPDATE #{report_id}: now {count} reports (priority {urgency}/100)"
        if is_update else f"[CivicFix] {level} {category} reported (priority {urgency}/100)"
    )
    body = (
        f"Dear {dept},\n\n"
        + ("Another citizen has reported an existing issue.\n" if is_update
           else "A new civic issue has been reported.\n")
        + f"\nIssue ID: #{report_id}\nCategory: {category} (AI confidence {round(confidence * 100)}%)\n"
        f"Urgency: {urgency}/100 ({reason})\nReports so far: {count}\n"
        f"Location: {x_m} m E, {y_m} m N on dashboard map (schematic)\n"
        + gps_text +
        f"Note: {note or '-'}\nPhoto: {'attached' if data else 'none'}\n\n"
        "Please review and update the status on the CivicFix dashboard.\n\n- CivicFix AI (automated message)\n"
    )
    recipients = [{"email": e.strip()} for e in to.split(",") if e.strip()]
    payload = {
        "sender": {"name": os.getenv("SENDER_NAME", "CivicFix AI"), "email": os.getenv("SENDER_EMAIL", "")},
        "to": recipients,
        "subject": subject,
        "textContent": body,
    }
    fname = None
    if data:
        fname = pathlib.Path(photo.filename or "").name
        if not pathlib.Path(fname).suffix:
            fname = f"report-{report_id}.{photo.content_type.split('/')[1]}"
        payload["attachment"] = [{"name": fname, "content": base64.b64encode(data).decode()}]

    key = os.getenv("BREVO_API_KEY", "").strip()
    if not (key and payload["sender"]["email"]):  # dry run: save instead of sending
        stamp = f"{int(time.time())}-{category}-{report_id}"
        (OUTBOX / f"{stamp}.txt").write_text(f"To: {to}\nSubject: {subject}\n\n{body}")
        if data:
            (OUTBOX / f"{stamp}-{fname}").write_bytes(data)
        return {"sent": False, "to": to, "detail": f"Brevo not configured, saved outbox/{stamp}.txt"}

    req = urllib.request.Request(
        BREVO_URL, data=json.dumps(payload).encode(), method="POST",
        headers={"api-key": key, "content-type": "application/json", "accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20):
            pass
    except urllib.error.HTTPError as e:
        raise HTTPException(502, f"Brevo error {e.code}: {e.read().decode(errors='ignore')[:200]}")
    except Exception as e:
        raise HTTPException(502, f"Email failed: {e}")
    return {"sent": True, "to": to, "detail": "sent"}


app.mount("/", StaticFiles(directory=BASE / "static", html=True), name="static")
