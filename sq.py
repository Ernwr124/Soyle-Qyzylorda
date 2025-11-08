"""
Soyle Qyzylorda - Оқиғалар мен бизнес платформасы
Дербестендірумен және аналитикамен толық веб-платформа
"""

from fastapi import FastAPI, HTTPException, Request, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, Literal, List
from datetime import datetime
import uvicorn
import sqlite3
from contextlib import contextmanager
import json
import random
import base64

# ============================================================================
# FastAPI қолданбасын бастау
# ============================================================================

app = FastAPI(title="Soyle Qyzylorda API", version="2.0.0")

DATABASE_FILE = "soyle_qyzylorda.db"

# ============================================================================
# Деректер модельдері (Pydantic)
# ============================================================================

class EventModel(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1)
    date_time: str
    location: str = Field(..., min_length=1)
    category: str = Field(default="Басқа")
    image_data: Optional[str] = None

class BusinessModel(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    category: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    contact_instagram: Optional[str] = None
    contact_whatsapp: Optional[str] = None
    logo_data: Optional[str] = None

class SubmitModel(BaseModel):
    type: Literal["event", "business"]
    data: dict

class UserInteractionModel(BaseModel):
    item_type: Literal["event", "business"]
    item_id: int
    interaction_type: Literal["view", "click", "save"]
    category: Optional[str] = None

class EventRegistrationModel(BaseModel):
    event_id: int
    session_id: str

# ============================================================================
# Дерекқор (SQLite)
# ============================================================================

@contextmanager
def get_db():
    """Дерекқормен жұмыс істеу үшін контекст менеджері"""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()

def init_database():
    """Аналитикамен дерекқорды бастау"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='events'")
        events_exists = cursor.fetchone() is not None
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='businesses'")
        businesses_exists = cursor.fetchone() is not None
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL,
                date_time TEXT NOT NULL,
                location TEXT NOT NULL,
                category TEXT NOT NULL DEFAULT 'Басқа',
                image_data TEXT,
                is_published BOOLEAN DEFAULT TRUE,
                view_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        if events_exists:
            try:
                cursor.execute("SELECT category FROM events LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute("ALTER TABLE events ADD COLUMN category TEXT NOT NULL DEFAULT 'Басқа'")
                print("✓ 'category' бағаны events кестесіне қосылды")
            
            try:
                cursor.execute("SELECT view_count FROM events LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute("ALTER TABLE events ADD COLUMN view_count INTEGER DEFAULT 0")
                print("✓ 'view_count' бағаны events кестесіне қосылды")
            
            try:
                cursor.execute("SELECT image_data FROM events LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute("ALTER TABLE events ADD COLUMN image_data TEXT")
                print("✓ 'image_data' бағаны events кестесіне қосылды")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS businesses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                contact_instagram TEXT,
                contact_whatsapp TEXT,
                logo_data TEXT,
                is_published BOOLEAN DEFAULT TRUE,
                view_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        if businesses_exists:
            try:
                cursor.execute("SELECT view_count FROM businesses LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute("ALTER TABLE businesses ADD COLUMN view_count INTEGER DEFAULT 0")
                print("✓ 'view_count' бағаны businesses кестесіне қосылды")
            
            try:
                cursor.execute("SELECT logo_data FROM businesses LIMIT 1")
            except sqlite3.OperationalError:
                cursor.execute("ALTER TABLE businesses ADD COLUMN logo_data TEXT")
                print("✓ 'logo_data' бағаны businesses кестесіне қосылды")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                item_type TEXT NOT NULL,
                item_id INTEGER NOT NULL,
                interaction_type TEXT NOT NULL,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS event_registrations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id INTEGER NOT NULL,
                session_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(event_id, session_id)
            )
        """)
        
        conn.commit()
        print("✓ База данных готова - все новые записи будут автоматически опубликованы")

init_database()

# ============================================================================
# API соңғы нүктелер
# ============================================================================

@app.get("/api/events")
async def get_events(category: Optional[str] = None, session_id: Optional[str] = None):
    """Категория бойынша қосымша сүзгілеумен оқиғаларды алу"""
    with get_db() as conn:
        cursor = conn.cursor()
        if category:
            cursor.execute("""
                SELECT id, title, description, date_time, location, category, image_data, view_count, created_at
                FROM events
                WHERE is_published = TRUE AND category = ?
                ORDER BY date_time ASC
            """, (category,))
        else:
            cursor.execute("""
                SELECT id, title, description, date_time, location, category, image_data, view_count, created_at
                FROM events
                WHERE is_published = TRUE
                ORDER BY date_time ASC
            """)
        events = [dict(row) for row in cursor.fetchall()]
        
        if session_id:
            for event in events:
                cursor.execute("""
                    SELECT id FROM event_registrations 
                    WHERE event_id = ? AND session_id = ?
                """, (event['id'], session_id))
                event['is_registered'] = cursor.fetchone() is not None
        else:
            for event in events:
                event['is_registered'] = False
        
        return JSONResponse(content=events)

@app.get("/api/businesses")
async def get_businesses(category: Optional[str] = None):
    """Қосымша сүзгілеумен бизнестерді алу"""
    with get_db() as conn:
        cursor = conn.cursor()
        if category:
            cursor.execute("""
                SELECT id, name, category, description, contact_instagram, contact_whatsapp, logo_data, view_count, created_at
                FROM businesses
                WHERE is_published = TRUE AND category = ?
                ORDER BY created_at DESC
            """, (category,))
        else:
            cursor.execute("""
                SELECT id, name, category, description, contact_instagram, contact_whatsapp, logo_data, view_count, created_at
                FROM businesses
                WHERE is_published = TRUE
                ORDER BY created_at DESC
            """)
        businesses = [dict(row) for row in cursor.fetchall()]
        return JSONResponse(content=businesses)

@app.get("/api/categories")
async def get_categories():
    """Барлық категорияларды алу"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT category FROM events WHERE is_published = TRUE")
        event_categories = [row[0] for row in cursor.fetchall()]
        cursor.execute("SELECT DISTINCT category FROM businesses WHERE is_published = TRUE")
        business_categories = [row[0] for row in cursor.fetchall()]
        return JSONResponse(content={
            "events": event_categories,
            "businesses": business_categories
        })

@app.get("/api/recommendations/{session_id}")
async def get_recommendations(session_id: str):
    """Көру тарихына негізделген дербес ұсыныстарды алу"""
    with get_db() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM user_interactions
            WHERE session_id = ? AND category IS NOT NULL
            GROUP BY category
            ORDER BY count DESC
            LIMIT 3
        """, (session_id,))
        
        favorite_categories = [row[0] for row in cursor.fetchall()]
        
        if not favorite_categories:
            cursor.execute("""
                SELECT id, title, description, date_time, location, category, image_data, view_count
                FROM events
                WHERE is_published = TRUE
                ORDER BY view_count DESC
                LIMIT 6
            """)
            events = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute("""
                SELECT id, name, category, description, contact_instagram, contact_whatsapp, logo_data, view_count
                FROM businesses
                WHERE is_published = TRUE
                ORDER BY view_count DESC
                LIMIT 6
            """)
            businesses = [dict(row) for row in cursor.fetchall()]
        else:
            placeholders = ','.join(['?' for _ in favorite_categories])
            cursor.execute(f"""
                SELECT id, title, description, date_time, location, category, image_data, view_count
                FROM events
                WHERE is_published = TRUE AND category IN ({placeholders})
                ORDER BY view_count DESC
                LIMIT 6
            """, favorite_categories)
            events = [dict(row) for row in cursor.fetchall()]
            
            cursor.execute(f"""
                SELECT id, name, category, description, contact_instagram, contact_whatsapp, logo_data, view_count
                FROM businesses
                WHERE is_published = TRUE AND category IN ({placeholders})
                ORDER BY view_count DESC
                LIMIT 6
            """, favorite_categories)
            businesses = [dict(row) for row in cursor.fetchall()]
        
        return JSONResponse(content={
            "events": events,
            "businesses": businesses,
            "favorite_categories": favorite_categories
        })

@app.post("/api/track")
async def track_interaction(interaction: UserInteractionModel, request: Request):
    """Дербестендіру үшін пайдаланушы әрекеттерін қадағалау"""
    session_id = request.cookies.get("session_id", f"session_{random.randint(100000, 999999)}")
    
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO user_interactions (session_id, item_type, item_id, interaction_type, category)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, interaction.item_type, interaction.item_id, 
              interaction.interaction_type, interaction.category))
        
        if interaction.interaction_type == "view":
            if interaction.item_type == "event":
                cursor.execute("UPDATE events SET view_count = view_count + 1 WHERE id = ?", 
                             (interaction.item_id,))
            else:
                cursor.execute("UPDATE businesses SET view_count = view_count + 1 WHERE id = ?",
                             (interaction.item_id,))
        
        conn.commit()
    
    response = JSONResponse(content={"success": True, "session_id": session_id})
    response.set_cookie("session_id", session_id, max_age=31536000)
    return response

@app.post("/api/register-event")
async def register_event(registration: EventRegistrationModel):
    """Регистрация на событие"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            cursor.execute("SELECT id FROM events WHERE id = ? AND is_published = TRUE", (registration.event_id,))
            event = cursor.fetchone()
            if not event:
                raise HTTPException(status_code=404, detail="Оқиға табылмады")
            
            cursor.execute("""
                INSERT OR IGNORE INTO event_registrations (event_id, session_id)
                VALUES (?, ?)
            """, (registration.event_id, registration.session_id))
            
            conn.commit()
            
            return JSONResponse(content={"success": True, "message": "Тіркелу сәтті орындалды!"})
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/api/submit")
async def submit_application(submission: SubmitModel):
    """Жариялауға өтінімдерді қабылдау (автоматты жарияланады)"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            if submission.type == "event":
                event = EventModel(**submission.data)
                cursor.execute("""
                    INSERT INTO events (title, description, date_time, location, category, image_data, is_published)
                    VALUES (?, ?, ?, ?, ?, ?, TRUE)
                """, (event.title, event.description, event.date_time, event.location, 
                      event.category, event.image_data))
                
            elif submission.type == "business":
                business = BusinessModel(**submission.data)
                cursor.execute("""
                    INSERT INTO businesses (name, category, description, contact_instagram, contact_whatsapp, logo_data, is_published)
                    VALUES (?, ?, ?, ?, ?, ?, TRUE)
                """, (business.name, business.category, business.description, 
                      business.contact_instagram, business.contact_whatsapp, business.logo_data))
            
            conn.commit()
            return JSONResponse(content={
                "success": True,
                "message": "Өтінім сәтті жарияланды!"
            })
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# ============================================================================
# Frontend маршруттары
# ============================================================================

@app.get("/", response_class=HTMLResponse)
async def get_home():
    """Басты бет"""
    return HTMLResponse(content=HTML_TEMPLATE)

@app.get("/submit", response_class=HTMLResponse)
async def get_submit_page():
    """Өтінім беру беті"""
    return HTMLResponse(content=SUBMIT_TEMPLATE)

# ============================================================================
# HTML үлгілері
# ============================================================================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="kk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
    <title>Soyle Qyzylorda - Оқиғалар мен бизнес платформасы</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        :root {
            --color-background: #000000;
            --color-foreground: #ffffff;
            --color-muted: #1a1a1a;
            --color-muted-foreground: #a3a3a3;
            --color-accent: #ffffff;
            --color-accent-foreground: #000000;
            --color-border: #262626;
            --color-primary: #ffffff;
            --color-primary-hover: #e5e5e5;
            --color-secondary: #404040;
            --color-success: #10b981;
            --font-sans: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        }
        
        body {
            font-family: var(--font-sans);
            background: var(--color-background);
            color: var(--color-foreground);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            padding: 0 16px;
        }
        
        /* Header */
        .header {
            position: sticky;
            top: 0;
            z-index: 1000;
            background: rgba(0, 0, 0, 0.95);
            border-bottom: 1px solid var(--color-border);
            backdrop-filter: blur(20px);
        }
        
        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            gap: 12px;
        }
        
        .logo {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .logo-image {
            width: 40px;
            height: 40px;
            border-radius: 50%;
        }
        
        .logo-text-container {
            display: flex;
            flex-direction: column;
        }
        
        .logo-text {
            font-size: 16px;
            font-weight: 600;
            letter-spacing: -0.5px;
            line-height: 1.2;
        }
        
        .logo-subtitle {
            font-size: 9px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--color-muted-foreground);
        }
        
        .header-actions {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .lang-switcher {
            display: flex;
            background: var(--color-muted);
            border-radius: 6px;
            padding: 4px;
            gap: 2px;
        }
        
        .lang-button {
            padding: 6px 10px;
            background: transparent;
            border: none;
            color: var(--color-muted-foreground);
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            border-radius: 4px;
            transition: all 0.2s;
            font-family: var(--font-sans);
        }
        
        .lang-button.active {
            background: var(--color-accent);
            color: var(--color-accent-foreground);
        }
        
        .cta-button {
            background: var(--color-accent);
            color: var(--color-accent-foreground);
            padding: 8px 14px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 13px;
            font-weight: 600;
            transition: all 0.2s;
            border: 1px solid var(--color-accent);
            white-space: nowrap;
        }
        
        .cta-button:hover {
            background: var(--color-primary-hover);
        }
        
        /* Hero */
        .hero {
            padding: 40px 0 30px;
            text-align: center;
        }
        
        .hero-slogan {
            font-size: 14px;
            font-weight: 600;
            letter-spacing: 2px;
            text-transform: uppercase;
            color: var(--color-muted-foreground);
            margin-bottom: 16px;
        }
        
        .hero-title {
            font-size: 36px;
            font-weight: 700;
            line-height: 1.1;
            letter-spacing: -1.5px;
            margin-bottom: 16px;
            background: linear-gradient(to bottom, var(--color-foreground), var(--color-muted-foreground));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .hero-subtitle {
            font-size: 15px;
            color: var(--color-muted-foreground);
            max-width: 500px;
            margin: 0 auto;
            line-height: 1.6;
        }
        
        /* Filter Section */
        .filter-section {
            padding: 24px 0;
            border-top: 1px solid var(--color-border);
        }
        
        .filter-tabs {
            display: flex;
            gap: 8px;
            overflow-x: auto;
            padding-bottom: 8px;
            -webkit-overflow-scrolling: touch;
            scrollbar-width: thin;
        }
        
        .filter-tabs::-webkit-scrollbar {
            height: 4px;
        }
        
        .filter-tabs::-webkit-scrollbar-track {
            background: var(--color-muted);
        }
        
        .filter-tabs::-webkit-scrollbar-thumb {
            background: var(--color-secondary);
            border-radius: 2px;
        }
        
        .filter-tab {
            padding: 8px 16px;
            background: var(--color-muted);
            border: 1px solid var(--color-border);
            border-radius: 6px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s;
            white-space: nowrap;
            color: var(--color-muted-foreground);
            font-family: var(--font-sans);
        }
        
        .filter-tab:hover {
            background: var(--color-secondary);
            color: var(--color-foreground);
        }
        
        .filter-tab.active {
            background: var(--color-accent);
            color: var(--color-accent-foreground);
            border-color: var(--color-accent);
        }
        
        /* Content Sections */
        .content-section {
            padding: 40px 0;
        }
        
        .section-header {
            margin-bottom: 24px;
        }
        
        .section-title {
            font-size: 24px;
            font-weight: 700;
            letter-spacing: -1px;
        }
        
        /* Event Grid */
        .event-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 16px;
        }
        
        .event-card {
            background: var(--color-muted);
            border: 1px solid var(--color-border);
            border-radius: 12px;
            overflow: hidden;
            transition: all 0.3s;
        }
        
        .event-image {
            width: 100%;
            height: 200px;
            object-fit: cover;
            background: linear-gradient(135deg, #1a1a1a 0%, #0a0a0a 100%);
        }
        
        .event-content {
            padding: 16px;
        }
        
        .event-category {
            display: inline-block;
            padding: 4px 10px;
            background: var(--color-secondary);
            color: var(--color-foreground);
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 10px;
        }
        
        .event-title {
            font-size: 18px;
            font-weight: 600;
            margin-bottom: 10px;
            line-height: 1.3;
            letter-spacing: -0.5px;
        }
        
        .event-description {
            font-size: 13px;
            color: var(--color-muted-foreground);
            margin-bottom: 12px;
            line-height: 1.6;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        
        .event-meta {
            display: flex;
            flex-direction: column;
            gap: 6px;
            font-size: 12px;
            color: var(--color-muted-foreground);
            margin-bottom: 12px;
        }
        
        .event-meta-item {
            display: flex;
            align-items: center;
            gap: 6px;
        }
        
        /* Register Button */
        .register-button {
            width: 100%;
            padding: 10px 16px;
            background: var(--color-accent);
            color: var(--color-accent-foreground);
            border: 1px solid var(--color-accent);
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s;
            font-family: var(--font-sans);
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
        }
        
        .register-button:hover {
            background: var(--color-primary-hover);
        }
        
        .register-button.registered {
            background: transparent;
            color: var(--color-success);
            border-color: var(--color-success);
            cursor: default;
        }
        
        .checkmark {
            display: inline-block;
            font-size: 16px;
            animation: checkmark-appear 0.4s ease-out;
        }
        
        @keyframes checkmark-appear {
            0% {
                opacity: 0;
                transform: scale(0) rotate(-45deg);
            }
            50% {
                transform: scale(1.2) rotate(5deg);
            }
            100% {
                opacity: 1;
                transform: scale(1) rotate(0deg);
            }
        }
        
        /* Business Grid */
        .business-grid {
            display: grid;
            grid-template-columns: 1fr;
            gap: 16px;
        }
        
        .business-card {
            background: var(--color-muted);
            border: 1px solid var(--color-border);
            border-radius: 12px;
            padding: 16px;
            transition: all 0.3s;
            cursor: pointer;
        }
        
        .business-card:active {
            transform: scale(0.98);
        }
        
        .business-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }
        
        .business-logo {
            width: 48px;
            height: 48px;
            border-radius: 8px;
            object-fit: cover;
            background: var(--color-secondary);
            flex-shrink: 0;
        }
        
        .business-info h3 {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 4px;
            letter-spacing: -0.3px;
        }
        
        .business-category {
            font-size: 11px;
            color: var(--color-muted-foreground);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .business-description {
            font-size: 13px;
            color: var(--color-muted-foreground);
            line-height: 1.6;
            margin-bottom: 12px;
            display: -webkit-box;
            -webkit-line-clamp: 3;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        
        .business-contacts {
            display: flex;
            gap: 8px;
            flex-wrap: wrap;
        }
        
        .contact-link {
            padding: 6px 12px;
            background: var(--color-secondary);
            color: var(--color-foreground);
            text-decoration: none;
            border-radius: 6px;
            font-size: 12px;
            font-weight: 500;
            transition: all 0.2s;
        }
        
        .contact-link:hover {
            background: var(--color-accent);
            color: var(--color-accent-foreground);
        }
        
        /* Loading & Empty States */
        .loading {
            text-align: center;
            padding: 60px 16px;
            color: var(--color-muted-foreground);
        }
        
        .spinner {
            width: 32px;
            height: 32px;
            border: 3px solid var(--color-border);
            border-top-color: var(--color-foreground);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 12px;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 16px;
            color: var(--color-muted-foreground);
        }
        
        .empty-icon {
            font-size: 40px;
            margin-bottom: 12px;
            opacity: 0.5;
        }
        
        .empty-state h3 {
            font-size: 18px;
            margin-bottom: 8px;
        }
        
        .empty-state p {
            font-size: 14px;
        }
        
        /* Footer */
        .footer {
            border-top: 1px solid var(--color-border);
            padding: 40px 0;
            margin-top: 60px;
        }
        
        .footer-content {
            text-align: center;
        }
        
        .footer-text {
            color: var(--color-muted-foreground);
            font-size: 13px;
            margin-bottom: 16px;
        }
        
        .footer-links {
            display: flex;
            justify-content: center;
            gap: 16px;
            flex-wrap: wrap;
        }
        
        .footer-link {
            color: var(--color-muted-foreground);
            text-decoration: none;
            font-size: 13px;
            transition: color 0.2s;
        }
        
        .footer-link:hover {
            color: var(--color-foreground);
        }
        
        /* Tablet & Desktop */
        @media (min-width: 640px) {
            .container {
                padding: 0 24px;
            }
            
            .header-content {
                padding: 16px 0;
            }
            
            .logo-image {
                width: 48px;
                height: 48px;
            }
            
            .logo-text {
                font-size: 18px;
            }
            
            .logo-subtitle {
                font-size: 10px;
            }
            
            .hero {
                padding: 60px 0 40px;
            }
            
            .hero-title {
                font-size: 52px;
            }
            
            .hero-subtitle {
                font-size: 17px;
            }
            
            .event-grid {
                grid-template-columns: repeat(2, 1fr);
                gap: 20px;
            }
            
            .business-grid {
                grid-template-columns: repeat(2, 1fr);
                gap: 20px;
            }
            
            .section-title {
                font-size: 28px;
            }
        }
        
        @media (min-width: 1024px) {
            .hero-title {
                font-size: 64px;
            }
            
            .hero-subtitle {
                font-size: 19px;
                max-width: 600px;
            }
            
            .event-grid {
                grid-template-columns: repeat(3, 1fr);
                gap: 24px;
            }
            
            .business-grid {
                grid-template-columns: repeat(3, 1fr);
                gap: 24px;
            }
            
            .event-card:hover {
                transform: translateY(-4px);
                border-color: var(--color-secondary);
            }
            
            .business-card:hover {
                transform: translateY(-4px);
                border-color: var(--color-secondary);
            }
            
            .section-title {
                font-size: 32px;
            }
        }
    </style>
</head>
<body>
    <!-- Header -->
    <header class="header">
        <div class="container">
            <div class="header-content">
                <div class="logo">
                    <img src="https://hebbkx1anhila5yf.public.blob.vercel-storage.com/result-zZHo3z48W1J0hOmY9lQ8uSwMk08STi.png" alt="Soyle Logo" class="logo-image">
                    <div class="logo-text-container">
                        <div class="logo-text">Soyle Qyzylorda</div>
                        <div class="logo-subtitle" data-kk="ОҚИҒАЛАР МЕН БИЗНЕС" data-ru="СОБЫТИЯ И БИЗНЕС">ОҚИҒАЛАР МЕН БИЗНЕС</div>
                    </div>
                </div>
                <div class="header-actions">
                    <div class="lang-switcher">
                        <button class="lang-button active" data-lang="kk">ҚАЗ</button>
                        <button class="lang-button" data-lang="ru">РУС</button>
                    </div>
                    <a href="/submit" class="cta-button" data-kk="Қосу" data-ru="Добавить">Қосу</a>
                </div>
            </div>
        </div>
    </header>

    <!-- Hero -->
    <section class="hero">
        <div class="container">
            <div class="hero-slogan">Біл. Қатыс. Табыс.</div>
            <h1 class="hero-title" data-kk="Қаланы жаңаша ашыңыз" data-ru="Откройте город заново">Қаланы жаңаша ашыңыз</h1>
            <p class="hero-subtitle" data-kk="Қызылорданың оқиғалары мен бизнесі үшін дербестендірілген платформа" data-ru="Персонализированная платформа событий и бизнеса Кызылорды">Қызылорданың оқиғалары мен бизнесі үшін дербестендірілген платформа</p>
        </div>
    </section>

    <!-- Event Filters -->
    <section class="filter-section">
        <div class="container">
            <div class="filter-tabs" id="event-filters">
                <button class="filter-tab active" data-category="" data-kk="Барлық оқиғалар" data-ru="Все события">Барлық оқиғалар</button>
            </div>
        </div>
    </section>

    <!-- Events Section -->
    <section class="content-section" id="events">
        <div class="container">
            <div class="section-header">
                <h2 class="section-title" data-kk="Алдағы оқиғалар" data-ru="Предстоящие события">Алдағы оқиғалар</h2>
            </div>
            <div id="events-container" class="event-grid">
                <div class="loading">
                    <div class="spinner"></div>
                    <p data-kk="Оқиғалар жүктелуде..." data-ru="Загрузка событий...">Оқиғалар жүктелуде...</p>
                </div>
            </div>
        </div>
    </section>

    <!-- Business Filters -->
    <section class="filter-section">
        <div class="container">
            <div class="filter-tabs" id="business-filters">
                <button class="filter-tab active" data-category="" data-kk="Барлық категориялар" data-ru="Все категории">Барлық категориялар</button>
            </div>
        </div>
    </section>

    <!-- Business Section -->
    <section class="content-section" id="businesses">
        <div class="container">
            <div class="section-header">
                <h2 class="section-title" data-kk="Жергілікті бизнес" data-ru="Местный бизнес">Жергілікті бизнес</h2>
            </div>
            <div id="businesses-container" class="business-grid">
                <div class="loading">
                    <div class="spinner"></div>
                    <p data-kk="Бизнестер жүктелуде..." data-ru="Загрузка бизнесов...">Бизнестер жүктелуде...</p>
                </div>
            </div>
        </div>
    </section>

    <!-- Footer -->
    <footer class="footer">
        <div class="container">
            <div class="footer-content">
                <div class="footer-text">© 2025 Soyle Qyzylorda. <span data-kk="Барлық құқықтар қорғалған." data-ru="Все права защищены.">Барлық құқықтар қорғалған.</span></div>
                <div class="footer-links">
                    <a href="#" class="footer-link" data-kk="Байланыстар" data-ru="Контакты">Байланыстар</a>
                    <a href="#" class="footer-link" data-kk="Шарттар" data-ru="Условия">Шарттар</a>
                    <a href="#" class="footer-link" data-kk="Құпиялылық" data-ru="Конфиденциальность">Құпиялылық</a>
                </div>
            </div>
        </div>
    </footer>

    <script>
        let sessionId = getCookie('session_id') || `session_${Math.floor(Math.random() * 900000) + 100000}`;
        let currentEventCategory = '';
        let currentBusinessCategory = '';
        let currentLang = localStorage.getItem('lang') || 'kk';
        
        console.log('[v0] Initializing platform with session:', sessionId);
        
        function switchLanguage(lang) {
            currentLang = lang;
            localStorage.setItem('lang', lang);
            
            document.querySelectorAll('.lang-button').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.lang === lang);
            });
            
            document.querySelectorAll('[data-kk][data-ru]').forEach(el => {
                if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                    el.placeholder = el.dataset[lang];
                } else if (el.tagName === 'OPTION') {
                    el.textContent = el.dataset[lang];
                } else {
                    el.textContent = el.dataset[lang];
                }
            });
            loadEvents();
            loadBusinesses();
        }
        
        document.querySelectorAll('.lang-button').forEach(btn => {
            btn.addEventListener('click', () => switchLanguage(btn.dataset.lang));
        });
        
        switchLanguage(currentLang);
        
        function getCookie(name) {
            const value = `; ${document.cookie}`;
            const parts = value.split(`; ${name}=`);
            if (parts.length === 2) return parts.pop().split(';').shift();
        }
        
        function formatDate(dateString) {
            const date = new Date(dateString);
            const options = { 
                day: 'numeric', 
                month: 'long',
                hour: '2-digit',
                minute: '2-digit'
            };
            return date.toLocaleDateString(currentLang === 'kk' ? 'kk-KZ' : 'ru-RU', options);
        }
        
        async function trackInteraction(itemType, itemId, interactionType, category) {
            try {
                await fetch('/api/track', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        item_type: itemType,
                        item_id: itemId,
                        interaction_type: interactionType,
                        category: category
                    })
                });
            } catch (error) {
                console.error('Tracking error:', error);
            }
        }
        
        async function registerForEvent(eventId, buttonElement) {
            try {
                const response = await fetch('/api/register-event', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        event_id: eventId,
                        session_id: sessionId
                    })
                });
                
                if (response.ok) {
                    buttonElement.classList.add('registered');
                    buttonElement.innerHTML = `<span class="checkmark">✓</span><span>${currentLang === 'kk' ? 'Тіркелдіңіз' : 'Зарегистрированы'}</span>`;
                    buttonElement.disabled = true;
                }
            } catch (error) {
                console.error('Registration error:', error);
            }
        }
        
        async function loadCategories() {
            try {
                const response = await fetch('/api/categories');
                const data = await response.json();
                
                const eventFilters = document.getElementById('event-filters');
                data.events.forEach(cat => {
                    const btn = document.createElement('button');
                    btn.className = 'filter-tab';
                    btn.textContent = cat;
                    btn.dataset.category = cat;
                    btn.onclick = () => filterEvents(cat);
                    eventFilters.appendChild(btn);
                });
                
                const businessFilters = document.getElementById('business-filters');
                data.businesses.forEach(cat => {
                    const btn = document.createElement('button');
                    btn.className = 'filter-tab';
                    btn.textContent = cat;
                    btn.dataset.category = cat;
                    btn.onclick = () => filterBusinesses(cat);
                    businessFilters.appendChild(btn);
                });
            } catch (error) {
                console.error('Categories error:', error);
            }
        }
        
        function filterEvents(category) {
            currentEventCategory = category;
            document.querySelectorAll('#event-filters .filter-tab').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.category === category);
            });
            loadEvents();
        }
        
        function filterBusinesses(category) {
            currentBusinessCategory = category;
            document.querySelectorAll('#business-filters .filter-tab').forEach(btn => {
                btn.classList.toggle('active', btn.dataset.category === category);
            });
            loadBusinesses();
        }
        
        async function loadEvents() {
            console.log('[v0] Loading events with category:', currentEventCategory);
            
            try {
                const params = new URLSearchParams();
                if (currentEventCategory) params.append('category', currentEventCategory);
                params.append('session_id', sessionId);
                
                const url = `/api/events?${params.toString()}`;
                console.log('[v0] Fetching events from:', url);
                
                const response = await fetch(url);
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const events = await response.json();
                console.log('[v0] Loaded events:', events.length);
                
                const container = document.getElementById('events-container');
                
                if (events.length === 0) {
                    container.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-icon">📅</div>
                            <h3>${currentLang === 'kk' ? 'Оқиғалар табылмады' : 'События не найдены'}</h3>
                            <p>${currentLang === 'kk' ? 'Жақында қайтадан тексеріңіз' : 'Проверьте снова позже'}</p>
                        </div>
                    `;
                    return;
                }
                
                container.innerHTML = events.map(event => `
                    <div class="event-card" onclick="handleEventClick(${event.id}, '${event.category}')">
                        <img src="${event.image_data || '/placeholder.svg?height=200&width=400'}" 
                             alt="${event.title}" 
                             class="event-image"
                             onerror="this.src='/placeholder.svg?height=200&width=400'">
                        <div class="event-content">
                            <span class="event-category">${event.category}</span>
                            <h3 class="event-title">${event.title}</h3>
                            <p class="event-description">${event.description}</p>
                            <div class="event-meta">
                                <div class="event-meta-item">
                                    <span>📅</span>
                                    <span>${formatDate(event.date_time)}</span>
                                </div>
                                <div class="event-meta-item">
                                    <span>📍</span>
                                    <span>${event.location}</span>
                                </div>
                            </div>
                            ${event.is_registered 
                                ? `<button class="register-button registered" disabled onclick="event.stopPropagation()">
                                    <span class="checkmark">✓</span>
                                    <span>${currentLang === 'kk' ? 'Тіркелдіңіз' : 'Зарегистрированы'}</span>
                                   </button>`
                                : `<button class="register-button" onclick="event.stopPropagation(); registerForEvent(${event.id}, this)">
                                    ${currentLang === 'kk' ? 'Тіркелу' : 'Регистрироваться'}
                                   </button>`
                            }
                        </div>
                    </div>
                `).join('');
            } catch (error) {
                console.error('[v0] Events loading error:', error);
                const container = document.getElementById('events-container');
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">⚠️</div>
                        <h3>${currentLang === 'kk' ? 'Қате орын алды' : 'Произошла ошибка'}</h3>
                        <p>${currentLang === 'kk' ? 'Оқиғаларды жүктеу мүмкін болмады' : 'Не удалось загрузить события'}</p>
                        <button onclick="loadEvents()" style="margin-top: 16px; padding: 8px 16px; background: var(--color-foreground); color: var(--color-background); border: none; border-radius: 8px; cursor: pointer;">
                            ${currentLang === 'kk' ? 'Қайта көріңіз' : 'Попробовать снова'}
                        </button>
                    </div>
                `;
            }
        }
        
        async function loadBusinesses() {
            console.log('[v0] Loading businesses with category:', currentBusinessCategory);
            
            try {
                const url = currentBusinessCategory 
                    ? `/api/businesses?category=${encodeURIComponent(currentBusinessCategory)}`
                    : '/api/businesses';
                
                console.log('[v0] Fetching businesses from:', url);
                
                const response = await fetch(url);
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const businesses = await response.json();
                console.log('[v0] Loaded businesses:', businesses.length);
                
                const container = document.getElementById('businesses-container');
                
                if (businesses.length === 0) {
                    container.innerHTML = `
                        <div class="empty-state">
                            <div class="empty-icon">🏪</div>
                            <h3>${currentLang === 'kk' ? 'Бизнестер табылмады' : 'Бизнесы не найдены'}</h3>
                            <p>${currentLang === 'kk' ? 'Жақында қайтадан тексеріңіз' : 'Проверьте снова позже'}</p>
                        </div>
                    `;
                    return;
                }
                
                container.innerHTML = businesses.map(business => `
                    <div class="business-card" onclick="handleBusinessClick(${business.id}, '${business.category}')">
                        <img src="${business.logo_data || '/placeholder.svg?height=200&width=200'}" 
                             alt="${business.name}" 
                             class="business-logo"
                             onerror="this.src='/placeholder.svg?height=200&width=200'">
                        <div class="business-content">
                            <div>
                                <h3 class="business-name">${business.name}</h3>
                                <span class="business-category">${business.category}</span>
                                <p class="business-description">${business.description}</p>
                            </div>
                            <div class="business-actions">
                                ${business.instagram ? `<a href="https://instagram.com/${business.instagram.replace('@', '')}" target="_blank" class="business-link" onclick="event.stopPropagation()">Instagram</a>` : ''}
                                ${business.whatsapp ? `<a href="https://wa.me/${business.whatsapp.replace(/\D/g, '')}" target="_blank" class="business-link" onclick="event.stopPropagation()">WhatsApp</a>` : ''}
                            </div>
                        </div>
                    </div>
                `).join('');
            } catch (error) {
                console.error('[v0] Businesses loading error:', error);
                const container = document.getElementById('businesses-container');
                container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">⚠️</div>
                        <h3>${currentLang === 'kk' ? 'Қате орын алды' : 'Произошла ошибка'}</h3>
                        <p>${currentLang === 'kk' ? 'Бизнестерді жүктеу мүмкін болмады' : 'Не удалось загрузить бизнесы'}</p>
                        <button onclick="loadBusinesses()" style="margin-top: 16px; padding: 8px 16px; background: var(--color-foreground); color: var(--color-background); border: none; border-radius: 8px; cursor: pointer;">
                            ${currentLang === 'kk' ? 'Қайта көріңіз' : 'Попробовать снова'}
                        </button>
                    </div>
                `;
            }
        }
        
        function handleEventClick(id, category) {
            trackInteraction('event', id, 'view', category);
        }
        
        function handleBusinessClick(id, category) {
            trackInteraction('business', id, 'view', category);
        }
        
        window.addEventListener('DOMContentLoaded', async () => {
            console.log('[v0] DOM loaded, initializing platform...');
            
            try {
                await loadCategories();
                console.log('[v0] Categories loaded');
                
                await Promise.all([
                    loadEvents(),
                    loadBusinesses()
                ]);
                console.log('[v0] Initial data loaded successfully');
            } catch (error) {
                console.error('[v0] Initialization error:', error);
            }
        });
    </script>
</body>
</html>
"""

SUBMIT_TEMPLATE = """
<!DOCTYPE html>
<html lang="kk">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=5.0, user-scalable=yes">
    <title>Өтінім беру - Soyle Qyzylorda</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        :root {
            --color-background: #000000;
            --color-foreground: #ffffff;
            --color-muted: #1a1a1a;
            --color-muted-foreground: #a3a3a3;
            --color-accent: #ffffff;
            --color-accent-foreground: #000000;
            --color-border: #262626;
            --color-error: #ef4444;
            --color-success: #10b981;
            --color-secondary: #404040;
            --font-sans: -apple-system, BlinkMacSystemFont, 'SF Pro Display', 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        }
        
        body {
            font-family: var(--font-sans);
            background: var(--color-background);
            color: var(--color-foreground);
            line-height: 1.6;
            -webkit-font-smoothing: antialiased;
            -moz-osx-font-smoothing: grayscale;
        }
        
        .container {
            max-width: 700px;
            margin: 0 auto;
            padding: 0 16px;
        }
        
        .header {
            border-bottom: 1px solid var(--color-border);
            padding: 16px 0;
        }
        
        .header-content {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo-text {
            font-size: 18px;
            font-weight: 600;
            letter-spacing: -0.5px;
        }
        
        .back-button {
            color: var(--color-muted-foreground);
            text-decoration: none;
            font-size: 13px;
            transition: color 0.2s;
        }
        
        .back-button:hover {
            color: var(--color-foreground);
        }
        
        .main-content {
            padding: 40px 0;
        }
        
        .form-header {
            text-align: center;
            margin-bottom: 32px;
        }
        
        .form-header h1 {
            font-size: 32px;
            font-weight: 700;
            letter-spacing: -1.5px;
            margin-bottom: 12px;
        }
        
        .form-header p {
            color: var(--color-muted-foreground);
            font-size: 14px;
        }
        
        .type-selector {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-bottom: 32px;
        }
        
        .type-option {
            padding: 24px 16px;
            background: var(--color-muted);
            border: 2px solid var(--color-border);
            border-radius: 12px;
            cursor: pointer;
            text-align: center;
            transition: all 0.2s;
        }
        
        .type-option:active {
            transform: scale(0.98);
        }
        
        .type-option.active {
            background: var(--color-accent);
            color: var(--color-accent-foreground);
            border-color: var(--color-accent);
        }
        
        .type-option-icon {
            font-size: 32px;
            margin-bottom: 12px;
        }
        
        .type-option-title {
            font-size: 16px;
            font-weight: 600;
            margin-bottom: 6px;
        }
        
        .type-option-desc {
            font-size: 12px;
            opacity: 0.7;
        }
        
        .form-group {
            margin-bottom: 20px;
        }
        
        .form-label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            font-size: 13px;
        }
        
        .required {
            color: var(--color-error);
        }
        
        .form-input,
        .form-textarea,
        .form-select {
            width: 100%;
            padding: 12px 14px;
            background: var(--color-muted);
            border: 1px solid var(--color-border);
            border-radius: 8px;
            color: var(--color-foreground);
            font-size: 14px;
            font-family: inherit;
            transition: all 0.2s;
        }
        
        .form-input:focus,
        .form-textarea:focus,
        .form-select:focus {
            outline: none;
            border-color: var(--color-accent);
        }
        
        .form-textarea {
            min-height: 100px;
            resize: vertical;
        }
        
        .form-hint {
            font-size: 12px;
            color: var(--color-muted-foreground);
            margin-top: 6px;
        }
        
        .file-upload-wrapper {
            position: relative;
        }
        
        .file-upload-button {
            display: inline-flex;
            align-items: center;
            gap: 8px;
            padding: 12px 18px;
            background: var(--color-muted);
            border: 2px dashed var(--color-border);
            border-radius: 8px;
            color: var(--color-foreground);
            cursor: pointer;
            transition: all 0.2s;
            font-size: 13px;
            font-weight: 500;
        }
        
        .file-upload-button:hover {
            border-color: var(--color-accent);
            background: var(--color-secondary);
        }
        
        .file-upload-input {
            display: none;
        }
        
        .file-preview {
            margin-top: 12px;
            display: none;
        }
        
        .file-preview.show {
            display: block;
        }
        
        .file-preview img {
            max-width: 100%;
            max-height: 200px;
            border-radius: 8px;
            border: 1px solid var(--color-border);
        }
        
        .file-name {
            margin-top: 8px;
            font-size: 12px;
            color: var(--color-muted-foreground);
        }
        
        .submit-button {
            width: 100%;
            padding: 14px;
            background: var(--color-accent);
            color: var(--color-accent-foreground);
            border: none;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            font-family: var(--font-sans);
        }
        
        .submit-button:hover {
            opacity: 0.9;
        }
        
        .submit-button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        .alert {
            padding: 14px;
            border-radius: 8px;
            margin-bottom: 20px;
            display: none;
            font-size: 14px;
        }
        
        .alert.show {
            display: block;
        }
        
        .alert-success {
            background: rgba(16, 185, 129, 0.1);
            color: var(--color-success);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }
        
        .alert-error {
            background: rgba(239, 68, 68, 0.1);
            color: var(--color-error);
            border: 1px solid rgba(239, 68, 68, 0.3);
        }
        
        .hidden {
            display: none !important;
        }
        
        @media (min-width: 640px) {
            .container {
                padding: 0 24px;
            }
            
            .main-content {
                padding: 60px 0;
            }
            
            .form-header h1 {
                font-size: 42px;
            }
            
            .form-header p {
                font-size: 15px;
            }
            
            .type-selector {
                gap: 16px;
                margin-bottom: 40px;
            }
            
            .type-option {
                padding: 32px 20px;
            }
            
            .type-option:hover {
                border-color: var(--color-accent);
            }
        }
    </style>
</head>
<body>
    <header class="header">
        <div class="container">
            <div class="header-content">
                <div class="logo-text">Soyle Qyzylorda</div>
                <a href="/" class="back-button" data-kk="← Артқа" data-ru="← Назад">← Артқа</a>
            </div>
        </div>
    </header>

    <main class="main-content">
        <div class="container">
            <div class="form-header">
                <h1 data-kk="Қосу" data-ru="Добавить">Қосу</h1>
                <p data-kk="Өтінім дереу жарияланады" data-ru="Заявка будет опубликована сразу">Өтінім дереу жарияланады</p>
            </div>

            <div id="alert-success" class="alert alert-success">
                <span data-kk="Өтінім сәтті жарияланды!" data-ru="Заявка успешно опубликована!">Өтінім сәтті жарияланды!</span>
            </div>
            <div id="alert-error" class="alert alert-error">
                <span id="error-message"></span>
            </div>

            <div class="type-selector">
                <div class="type-option active" data-type="event">
                    <div class="type-option-icon">📅</div>
                    <div class="type-option-title" data-kk="Оқиға" data-ru="Событие">Оқиға</div>
                    <div class="type-option-desc" data-kk="Концерт, фестиваль" data-ru="Концерт, фестиваль">Концерт, фестиваль</div>
                </div>
                <div class="type-option" data-type="business">
                    <div class="type-option-icon">🏪</div>
                    <div class="type-option-title" data-kk="Бизнес" data-ru="Бизнес">Бизнес</div>
                    <div class="type-option-desc" data-kk="Дүкен, қызмет" data-ru="Магазин, услуга">Дүкен, қызмет</div>
                </div>
            </div>

            <form id="event-form" class="submission-form">
                <div class="form-group">
                    <label class="form-label">
                        <span data-kk="Оқиға атауы" data-ru="Название события">Оқиға атауы</span> <span class="required">*</span>
                    </label>
                    <input type="text" name="title" class="form-input" required 
                           data-kk="Мысалы: Халық музыкасының концерті" 
                           data-ru="Например: Концерт народной музыки"
                           placeholder="Мысалы: Халық музыкасының концерті">
                </div>

                <div class="form-group">
                    <label class="form-label">
                        <span data-kk="Категория" data-ru="Категория">Категория</span> <span class="required">*</span>
                    </label>
                    <select name="category" class="form-select" required>
                        <option value="" data-kk="Категорияны таңдаңыз" data-ru="Выберите категорию">Категорияны таңдаңыз</option>
                        <option value="Мәдениет">Мәдениет / Культура</option>
                        <option value="Музыка">Музыка / Музыка</option>
                        <option value="Білім">Білім / Образование</option>
                        <option value="Өнер">Өнер / Искусство</option>
                        <option value="Спорт">Спорт / Спорт</option>
                        <option value="Тамақ">Тамақ / Еда</option>
                        <option value="Басқа">Басқа / Другое</option>
                    </select>
                </div>

                <div class="form-group">
                    <label class="form-label">
                        <span data-kk="Сипаттама" data-ru="Описание">Сипаттама</span> <span class="required">*</span>
                    </label>
                    <textarea name="description" class="form-textarea" required
                              data-kk="Оқиға туралы толығырақ айтып беріңіз..." 
                              data-ru="Расскажите подробнее о событии..."
                              placeholder="Оқиға туралы толығырақ айтып беріңіз..."></textarea>
                </div>

                <div class="form-group">
                    <label class="form-label">
                        <span data-kk="Күн мен уақыт" data-ru="Дата и время">Күн мен уақыт</span> <span class="required">*</span>
                    </label>
                    <input type="datetime-local" name="date_time" class="form-input" required>
                </div>

                <div class="form-group">
                    <label class="form-label">
                        <span data-kk="Өткізілетін орын" data-ru="Место проведения">Өткізілетін орын</span> <span class="required">*</span>
                    </label>
                    <input type="text" name="location" class="form-input" required
                           data-kk="Мысалы: Орталық алаң" 
                           data-ru="Например: Центральная площадь"
                           placeholder="Мысалы: Орталық алаң">
                </div>

                <div class="form-group">
                    <label class="form-label">
                        <span data-kk="Оқиға суреті" data-ru="Изображение события">Оқиға суреті</span>
                    </label>
                    <div class="file-upload-wrapper">
                        <label for="event-image-input" class="file-upload-button">
                            <span>📷</span>
                            <span data-kk="Сурет таңдаңыз" data-ru="Выберите изображение">Сурет таңдаңыз</span>
                        </label>
                        <input type="file" 
                               id="event-image-input" 
                               class="file-upload-input" 
                               accept="image/*"
                               onchange="handleFileSelect(event, 'event-image-preview')">
                        <div id="event-image-preview" class="file-preview"></div>
                    </div>
                    <div class="form-hint" data-kk="Міндетті емес" data-ru="Необязательно">Міндетті емес</div>
                </div>

                <button type="submit" class="submit-button" data-kk="Жариялау" data-ru="Опубликовать">
                    Жариялау
                </button>
            </form>

            <form id="business-form" class="submission-form hidden">
                <div class="form-group">
                    <label class="form-label">
                        <span data-kk="Бизнес атауы" data-ru="Название бизнеса">Бизнес атауы</span> <span class="required">*</span>
                    </label>
                    <input type="text" name="name" class="form-input" required
                           data-kk="Мысалы: Шаңырақ кофеханасы" 
                           data-ru="Например: Кофейня Шанырак"
                           placeholder="Мысалы: Шаңырақ кофеханасы">
                </div>

                <div class="form-group">
                    <label class="form-label">
                        <span data-kk="Категория" data-ru="Категория">Категория</span> <span class="required">*</span>
                    </label>
                    <select name="category" class="form-select" required>
                        <option value="" data-kk="Категорияны таңдаңыз" data-ru="Выберите категорию">Категорияны таңдаңыз</option>
                        <option value="Кафе">Кафе / Кафе</option>
                        <option value="Сұлулық салоны">Сұлулық салоны / Салон красоты</option>
                        <option value="Дүкен">Дүкен / Магазин</option>
                        <option value="Білім">Білім / Образование</option>
                        <option value="Спорт">Спорт / Спорт</option>
                        <option value="Қызметтер">Қызметтер / Услуги</option>
                        <option value="Ойын-сауық">Ойын-сауық / Развлечения</option>
                        <option value="Басқа">Басқа / Другое</option>
                    </select>
                </div>

                <div class="form-group">
                    <label class="form-label">
                        <span data-kk="Сипаттама" data-ru="Описание">Сипаттама</span> <span class="required">*</span>
                    </label>
                    <textarea name="description" class="form-textarea" required
                              data-kk="Бизнесіңіз туралы айтып беріңіз..." 
                              data-ru="Расскажите о вашем бизнесе..."
                              placeholder="Бизнесіңіз туралы айтып беріңіз..."></textarea>
                </div>

                <div class="form-group">
                    <label class="form-label">
                        Instagram
                    </label>
                    <input type="text" name="contact_instagram" class="form-input"
                           placeholder="@username">
                    <div class="form-hint" data-kk="Міндетті емес" data-ru="Необязательно">Міндетті емес</div>
                </div>

                <div class="form-group">
                    <label class="form-label">
                        WhatsApp
                    </label>
                    <input type="tel" name="contact_whatsapp" class="form-input"
                           placeholder="+7 700 123 45 67">
                    <div class="form-hint" data-kk="Міндетті емес" data-ru="Необязательно">Міндетті емес</div>
                </div>

                <div class="form-group">
                    <label class="form-label">
                        <span data-kk="Логотип" data-ru="Логотип">Логотип</span>
                    </label>
                    <div class="file-upload-wrapper">
                        <label for="business-logo-input" class="file-upload-button">
                            <span>🖼️</span>
                            <span data-kk="Логотип таңдаңыз" data-ru="Выберите логотип">Логотип таңдаңыз</span>
                        </label>
                        <input type="file" 
                               id="business-logo-input" 
                               class="file-upload-input" 
                               accept="image/*"
                               onchange="handleFileSelect(event, 'business-logo-preview')">
                        <div id="business-logo-preview" class="file-preview"></div>
                    </div>
                    <div class="form-hint" data-kk="Міндетті емес" data-ru="Необязательно">Міндетті емес</div>
                </div>

                <button type="submit" class="submit-button" data-kk="Жариялау" data-ru="Опубликовать">
                    Жариялау
                </button>
            </form>
        </div>
    </main>

    <script>
        const typeOptions = document.querySelectorAll('.type-option');
        const eventForm = document.getElementById('event-form');
        const businessForm = document.getElementById('business-form');
        const alertSuccess = document.getElementById('alert-success');
        const alertError = document.getElementById('alert-error');
        const errorMessage = document.getElementById('error-message');
        
        let currentType = 'event';
        let eventImageData = null;
        let businessLogoData = null;
        let currentLang = localStorage.getItem('lang') || 'kk';

        function switchLanguage(lang) {
            currentLang = lang;
            
            document.querySelectorAll('[data-kk][data-ru]').forEach(el => {
                if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
                    el.placeholder = el.dataset[lang];
                } else if (el.tagName === 'OPTION') {
                    el.textContent = el.dataset[lang];
                } else {
                    el.textContent = el.dataset[lang];
                }
            });
        }
        
        switchLanguage(currentLang);

        typeOptions.forEach(option => {
            option.addEventListener('click', () => {
                const type = option.dataset.type;
                currentType = type;
                
                typeOptions.forEach(opt => opt.classList.remove('active'));
                option.classList.add('active');
                
                if (type === 'event') {
                    eventForm.classList.remove('hidden');
                    businessForm.classList.add('hidden');
                } else {
                    eventForm.classList.add('hidden');
                    businessForm.classList.remove('hidden');
                }
                
                alertSuccess.classList.remove('show');
                alertError.classList.remove('show');
            });
        });

        function handleFileSelect(event, previewId) {
            const file = event.target.files[0];
            const preview = document.getElementById(previewId);
            
            if (file) {
                const reader = new FileReader();
                reader.onload = function(e) {
                    const base64Data = e.target.result;
                    
                    if (previewId === 'event-image-preview') {
                        eventImageData = base64Data;
                    } else {
                        businessLogoData = base64Data;
                    }
                    
                    preview.innerHTML = `
                        <img src="${base64Data}" alt="Preview">
                        <div class="file-name">${file.name}</div>
                    `;
                    preview.classList.add('show');
                };
                reader.readAsDataURL(file);
            }
        }

        eventForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await handleSubmit(e.target, 'event');
        });

        businessForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            await handleSubmit(e.target, 'business');
        });

        async function handleSubmit(form, type) {
            const submitButton = form.querySelector('.submit-button');
            const formData = new FormData(form);
            const data = Object.fromEntries(formData.entries());
            
            if (type === 'event' && eventImageData) {
                data.image_data = eventImageData;
            } else if (type === 'business' && businessLogoData) {
                data.logo_data = businessLogoData;
            }
            
            alertSuccess.classList.remove('show');
            alertError.classList.remove('show');
            
            submitButton.disabled = true;
            submitButton.textContent = currentLang === 'kk' ? 'Жіберілуде...' : 'Отправка...';
            
            try {
                const response = await fetch('/api/submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ type: type, data: data })
                });
                
                const result = await response.json();
                
                if (response.ok) {
                    alertSuccess.classList.add('show');
                    form.reset();
                    eventImageData = null;
                    businessLogoData = null;
                    document.querySelectorAll('.file-preview').forEach(p => p.classList.remove('show'));
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                } else {
                    errorMessage.textContent = result.detail || (currentLang === 'kk' ? 'Қате орын алды' : 'Произошла ошибка');
                    alertError.classList.add('show');
                    window.scrollTo({ top: 0, behavior: 'smooth' });
                }
            } catch (error) {
                console.error('Submit error:', error);
                errorMessage.textContent = currentLang === 'kk' ? 'Серверге қосылу қатесі' : 'Ошибка подключения к серверу';
                alertError.classList.add('show');
            } finally {
                submitButton.disabled = false;
                submitButton.textContent = currentLang === 'kk' ? 'Жариялау' : 'Опубликовать';
            }
        }
    </script>
</body>
</html>
"""

# ============================================================================
# Қолданбаны іске қосу
# ============================================================================

if __name__ == "__main__":
    print("=" * 80)
    print("🎪 Soyle Qyzylorda - Оқиғалар мен бизнес платформасы v2.1")
    print("=" * 80)
    print("✨ Жаңа функциялар:")
    print("   • Оқиғаларға тіркелу батырмасы")
    print("   • Дерекқормен байланысты жақсартылған")
    print("   • Теріс жауаптарды өңдеу")
    print("   • Сынықтар бойынша жаңалықтар")
    print("   • Анатомдық жүйе")
    print("   • Анимацияланған галочка")
    print("   • Дереу жариялау (модерациясыз)")
    print("   • Толық қазақ/орыс локализациясы")
    print("=" * 80)
    print("📍 Сервер: http://127.0.0.1:8000")
    print("🌐 Басты бет: http://127.0.0.1:8000")
    print("📝 Өтінім: http://127.0.0.1:8000/submit")
    print("🔌 API құжаттамасы: http://127.0.0.1:8000/docs")
    print("=" * 80)
    
    uvicorn.run(app, host="127.0.0.1", port=8000)