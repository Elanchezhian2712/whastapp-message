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



from fastapi import FastAPI, Response
from pydantic import BaseModel
from typing import List
from PIL import Image, ImageDraw, ImageFont
import io
import math
import random



from fastapi import FastAPI, Response
from pydantic import BaseModel
from typing import List
from PIL import Image, ImageDraw, ImageFont
import io
import math
import random



def text_size(draw, text, font):
    """Utility to compute width/height with Pillow ≥10."""
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    return w, h

class ScoreItem(BaseModel):
    name: str
    score: int


def text_size(draw, text, font):
    """Utility to compute width/height with Pillow ≥10."""
    bbox = draw.textbbox((0, 0), text, font=font)
    w = bbox[2] - bbox[0]
    h = bbox[3] - bbox[1]
    return w, h

def get_rotated_bbox(x, y, w, h, angle_deg):
    """Get bounding box of rotated rectangle."""
    angle_rad = math.radians(angle_deg)
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    
    # Four corners of the rectangle
    corners = [
        (-w/2, -h/2), (w/2, -h/2),
        (w/2, h/2), (-w/2, h/2)
    ]
    
    # Rotate corners
    rotated = []
    for cx, cy in corners:
        rx = cx * cos_a - cy * sin_a
        ry = cx * sin_a + cy * cos_a
        rotated.append((x + rx, y + ry))
    
    # Get bounding box
    xs = [p[0] for p in rotated]
    ys = [p[1] for p in rotated]
    return min(xs), min(ys), max(xs), max(ys)

def check_collision(x, y, w, h, angle, placed_boxes, margin=8):
    """Check if text box collides with any placed boxes."""
    x1, y1, x2, y2 = get_rotated_bbox(x, y, w, h, angle)
    
    # Add margin
    x1 -= margin
    y1 -= margin
    x2 += margin
    y2 += margin
    
    for bx1, by1, bx2, by2 in placed_boxes:
        # Check if boxes overlap
        if not (x2 < bx1 or x1 > bx2 or y2 < by1 or y1 > by2):
            return True
    return False

class ScoreItem(BaseModel):
    name: str
    score: int
    
def generate_circular_leaderboard(scores):
    # Sort by score descending
    scores = sorted(scores, key=lambda x: x.score, reverse=True)
    
    if not scores:
        # Empty image
        img = Image.new("RGB", (1400, 1400), "black")
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
    
    top = scores[0]
    size = 1600
    center = size // 2
    
    # Black background
    img = Image.new("RGB", (size, size), "black")
    draw = ImageDraw.Draw(img)

    # Color palette - more variety
    colors = [
        "#E91E63", "#F06292", "#EC407A", "#D81B60", "#FF5252",
        "#FF1744", "#C2185B", "#AD1457", "#F48FB1", "#FF80AB",
        "#AAAAAA", "#CCCCCC", "#999999", "#DDDDDD", "#FFFFFF",
    ]

    # Track placed text boxes
    placed_boxes = []

    # --- Draw CENTER text (largest) ---
    try:
        center_font = ImageFont.truetype("arial.ttf", 85)
    except:
        center_font = ImageFont.load_default()
    
    text = top.name.lower()
    w, h = text_size(draw, text, center_font)
    cx, cy = center - w/2, center - h/2
    draw.text((cx, cy), text, fill="#E91E63", font=center_font)
    
    # Add center box to placed boxes
    placed_boxes.append((cx - 5, cy - 5, cx + w + 5, cy + h + 5))

    # --- Prepare other items ---
    others = scores[1:]
    if not others:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
    
    max_score = others[0].score
    min_score = others[-1].score
    score_range = max_score - min_score if max_score != min_score else 1
    
    # Prepare all items with properties
    items_data = []
    for item in others:
        normalized_score = (item.score - min_score) / score_range
        font_size = int(18 + normalized_score * 42)  # 18-60px
        
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
        
        label = item.name.lower()
        tw, th = text_size(draw, label, font)
        color = random.choice(colors)
        
        items_data.append({
            'item': item,
            'font': font,
            'size': font_size,
            'color': color,
            'text': label,
            'w': tw,
            'h': th
        })
    
    # Sort by size (place larger items first)
    items_data.sort(key=lambda x: x['size'], reverse=True)
    
    # --- Spiral placement with better collision detection ---
    placed_count = 0
    max_attempts = 100
    
    # Spiral parameters
    spiral_tightness = 8  # How quickly spiral expands
    angle_increment = 0.5  # Radians per step
    start_radius = 120
    
    for data in items_data:
        placed = False
        
        # Try spiral positions
        for attempt in range(max_attempts):
            # Calculate position on spiral
            spiral_angle = attempt * angle_increment
            spiral_radius = start_radius + (spiral_tightness * spiral_angle)
            
            # Add some randomness
            angle_noise = random.uniform(-0.3, 0.3)
            radius_noise = random.uniform(-15, 15)
            
            final_angle = spiral_angle + angle_noise
            final_radius = spiral_radius + radius_noise
            
            # Convert to cartesian coordinates
            x = center + final_radius * math.cos(final_angle)
            y = center + final_radius * math.sin(final_angle)
            
            # Random rotation for visual variety
            rotation = random.uniform(-70, 70)
            
            # Occasionally align with radial direction
            if random.random() > 0.7:
                rotation = -math.degrees(final_angle) + random.choice([0, 90, -90, 180])
            
            # Check if position is valid
            if check_collision(x, y, data['w'], data['h'], rotation, placed_boxes, margin=6):
                continue
            
            # Check bounds
            x1, y1, x2, y2 = get_rotated_bbox(x, y, data['w'], data['h'], rotation)
            if x1 < 20 or y1 < 20 or x2 > size - 20 or y2 > size - 20:
                continue
            
            # Place text
            txt_img = Image.new('RGBA', (int(data['w'] + 40), int(data['h'] + 40)), (0, 0, 0, 0))
            txt_draw = ImageDraw.Draw(txt_img)
            txt_draw.text((20, 20), data['text'], fill=data['color'], font=data['font'])
            
            rotated = txt_img.rotate(rotation, expand=True, resample=Image.BICUBIC)
            
            paste_x = int(x - rotated.width/2)
            paste_y = int(y - rotated.height/2)
            
            img.paste(rotated, (paste_x, paste_y), rotated)
            
            # Add to placed boxes
            placed_boxes.append((x1, y1, x2, y2))
            placed_count += 1
            placed = False
            break
        
        if not placed and attempt == max_attempts - 1:
            # Last resort: try a few random positions far from center
            for _ in range(20):
                angle = random.uniform(0, 2 * math.pi)
                radius = random.uniform(400, 650)
                x = center + radius * math.cos(angle)
                y = center + radius * math.sin(angle)
                rotation = random.uniform(-70, 70)
                
                if not check_collision(x, y, data['w'], data['h'], rotation, placed_boxes, margin=6):
                    x1, y1, x2, y2 = get_rotated_bbox(x, y, data['w'], data['h'], rotation)
                    if 20 < x1 and 20 < y1 and x2 < size - 20 and y2 < size - 20:
                        txt_img = Image.new('RGBA', (int(data['w'] + 40), int(data['h'] + 40)), (0, 0, 0, 0))
                        txt_draw = ImageDraw.Draw(txt_img)
                        txt_draw.text((20, 20), data['text'], fill=data['color'], font=data['font'])
                        rotated = txt_img.rotate(rotation, expand=True, resample=Image.BICUBIC)
                        paste_x = int(x - rotated.width/2)
                        paste_y = int(y - rotated.height/2)
                        img.paste(rotated, (paste_x, paste_y), rotated)
                        placed_boxes.append((x1, y1, x2, y2))
                        placed_count += 1
                        break

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf

@app.post("/leaderboard")
def leaderboard(scores: List[ScoreItem]):
   
    img = generate_circular_leaderboard(scores)
    return Response(content=img.getvalue(), media_type="image/png")