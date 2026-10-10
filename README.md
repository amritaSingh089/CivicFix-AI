# CivicFix AI: working email alerts

Upload a photo, pick a category -> the matching department gets an email with the photo attached.

## Run
1. Install Python 3.9+.
2. In this folder:
   ```
   python -m venv venv
   venv\Scripts\activate        (Windows)   |   source venv/bin/activate   (Mac/Linux)
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill it in (see below).
4. Start: `uvicorn main:app --reload`
5. Open http://localhost:8000

## Gmail setup (sender)
Google Account -> Security -> turn on 2-Step Verification -> App passwords -> create one.
Put it in `SMTP_PASS` (no spaces). Use `SMTP_HOST=smtp.gmail.com`, `SMTP_PORT=587`.

## Test safely first
Set all four `EMAIL_*` values to your own address. Only switch to real authority
addresses after you've confirmed it works.
If SMTP isn't configured, emails are saved as `.eml` files in `outbox/` instead (dry run).

## Notes
- Max 5 reports per IP per minute and 10 MB per photo (edit in main.py).
- The AI category detection in the page is still simulated; the category dropdown is what
  decides the recipient, so pick it explicitly. A real classifier (CLIP) can be added to main.py.
- To let others use it, deploy it (Render, Railway, a VPS) and keep `.env` secret.
