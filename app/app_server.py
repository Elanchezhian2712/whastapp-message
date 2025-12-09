from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import JSONResponse
from app.whatsapp_sender import WhatsAppSender
import csv
import os
import traceback

app = FastAPI(title="WhatsApp Automation API")

SENDER = WhatsAppSender()


# -------------------------------------------------------------
# START SELENIUM SESSION
# -------------------------------------------------------------
@app.post("/start")
def start():
    try:
        if SENDER.running:
            return {"status": "already_running"}

        SENDER.start()
        logged = SENDER.ensure_login()

        return {
            "status": "logged_in" if logged else "waiting_for_qr"
        }

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


# -------------------------------------------------------------
# CHECK LOGIN STATUS
# -------------------------------------------------------------
@app.get("/status")
def status():
    try:
        if not SENDER.running:
            return {"status": "not_started"}

        page = SENDER.driver.page_source.lower()

        if ("search" in page or "new chat" in page or "community" in page):
            return {"status": "logged_in"}

        return {"status": "waiting_for_qr"}

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


# -------------------------------------------------------------
# LOAD AND CLEAN CONTACTS FROM CSV
# -------------------------------------------------------------
def load_contacts_from_csv():
    csv_path = os.path.abspath("data/contacts.csv")

    if not os.path.exists(csv_path):
        raise FileNotFoundError("contacts.csv not found in /data folder")

    cleaned_contacts = []

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:

            # Clean mobile (must be only digits)
            raw_mobile = (row.get("mobile") or "").replace("+", "").replace(" ", "").strip()

            if not raw_mobile.isdigit() or len(raw_mobile) < 8:
                continue  # skip invalid numbers

            name = (row.get("name") or "").strip()
            link = (row.get("link") or "").strip()

            if not name or not link:
                continue  # skip missing fields

            cleaned_contacts.append({
                "name": name,
                "mobile": raw_mobile,
                "link": link
            })

    return cleaned_contacts


# -------------------------------------------------------------
# SEND BULK MESSAGES (AUTO-LOAD CSV)
# -------------------------------------------------------------
@app.post("/send_bulk")
def send_bulk(data: dict = None, background: BackgroundTasks = None):

    try:
        # 1) Auto-load CSV if no contacts provided
        if not data or "contacts" not in data:
            contacts = load_contacts_from_csv()
            template = "Hello {name}, please complete this: {link}"
        else:
            contacts = data["contacts"]
            template = data["template"]

        if not contacts:
            return {"status": "error", "detail": "No valid contacts found"}

        def run_job():
            try:
                print(f"Starting bulk send for {len(contacts)} contacts...")
                results = SENDER.send_bulk(contacts, template)
                print("Bulk send completed:", results)
            except Exception:
                traceback.print_exc()

        background.add_task(run_job)

        return {
            "status": "processing",
            "total_contacts": len(contacts)
        }

    except Exception as e:
        traceback.print_exc()
        return JSONResponse(status_code=500, content={"status": "error", "detail": str(e)})


# -------------------------------------------------------------
# EVENTS
# -------------------------------------------------------------
@app.get("/events")
def events():
    return {"events": SENDER.get_events()}


# -------------------------------------------------------------
# STOP SELENIUM SESSION
# -------------------------------------------------------------
@app.post("/stop")
def stop():
    try:
        SENDER.stop()
        return {"status": "stopped"}

    except Exception as e:
        traceback.print_exc()
        return {"status": "error", "detail": str(e)}
