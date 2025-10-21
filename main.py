from fastapi import FastAPI, File, UploadFile, Form, Query, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
import shutil, os, re, requests, sqlite3, hashlib, time
import easyocr
from langdetect import detect
from jose import jwt, JWTError

# --- Initialisation ---
app = FastAPI()

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://loo-wze-ia.vercel.app/"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Page d’accueil ---
@app.get("/")
def home():
    return {
        "message": "Bienvenue dans ton API Pokémon 🎴",
        "endpoints": [
            "/register",
            "/token",
            "/upload",
            "/confirm",
            "/collection/list",
            "/collection/value",
            "/collection/stats"
        ]
    }

# --- Auth config ---
SECRET_KEY = "CHANGE_ME_SECRET_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_SECONDS = 60 * 60 * 24
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# --- DB helpers ---
def get_db():
    return sqlite3.connect("collection.db")

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password_hash TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            name TEXT,
            set_name TEXT,
            number TEXT,
            rarity TEXT,
            price REAL,
            image TEXT,
            finish TEXT,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)
    conn.commit()
    conn.close()

init_db()

# --- Password hash ---
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

# --- JWT helpers ---
def create_access_token(user_id: int):
    payload = {"sub": str(user_id), "exp": int(time.time()) + ACCESS_TOKEN_EXPIRE_SECONDS}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user_id(token: str = Depends(oauth2_scheme)) -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return int(user_id)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# --- Auth endpoints ---
@app.post("/register")
def register(email: str = Form(...), password: str = Form(...)):
    conn = get_db()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (email, password_hash) VALUES (?, ?)", (email, hash_password(password)))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        raise HTTPException(status_code=400, detail="Email déjà utilisé")
    conn.close()
    return {"message": "Utilisateur créé ✅"}

@app.post("/token")
def login(form_data: OAuth2PasswordRequestForm = Depends()):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT id, password_hash FROM users WHERE email = ?", (form_data.username,))
    row = c.fetchone()
    conn.close()
    if not row or row[1] != hash_password(form_data.password):
        raise HTTPException(status_code=401, detail="Identifiants invalides")
    token = create_access_token(row[0])
    return {"access_token": token, "token_type": "bearer"}

# --- Recherche Pokémon TCG ---
def search_card(query: str):
    url = f"https://api.pokemontcg.io/v2/cards?q={query}"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        return [
            {
                "id": c.get("id"),
                "name": c.get("name"),
                "set": c.get("set", {}).get("name"),
                "number": c.get("number"),
                "rarity": c.get("rarity"),
                "image": c.get("images", {}).get("small"),
                "prices": c.get("cardmarket", {}).get("prices", {})
            }
            for c in data.get("data", [])[:5]
        ]
    return []

# --- OCR helpers ---
def clean_ocr_text(text: str):
    stopwords = {"stage", "basic", "pv", "hp", "energie", "energy"}
    words = []
    for w in text.split():
        wl = w.lower()
        if wl not in stopwords and wl.isalpha() and len(w) > 2:
            words.append(w)
    return words

# --- Upload ---
reader = easyocr.Reader(['en', 'fr', 'de', 'es', 'it'], gpu=False)

@app.post("/upload")
async def upload_card(recto: UploadFile = File(...), verso: UploadFile = File(...), user_id: int = Depends(get_current_user_id)):
    os.makedirs("uploads", exist_ok=True)

    recto_path = f"uploads/{recto.filename}"
    with open(recto_path, "wb") as buffer:
        shutil.copyfileobj(recto.file, buffer)

    verso_path = f"uploads/{verso.filename}"
    with open(verso_path, "wb") as buffer:
        shutil.copyfileobj(verso.file, buffer)

    result = reader.readtext(recto_path, detail=0)
    detected_text = " ".join(result)
    lang = detect(detected_text) if detected_text else "unknown"

    # Nettoyage OCR
    words = clean_ocr_text(detected_text)
    pokemon_name = words[0] if words else None

    # Numéro de carte
    match = re.search(r"\d+/\d+", detected_text)
    card_number = match.group(0) if match else None

    # Recherche améliorée
    suggestions = []
    if card_number and pokemon_name:
        suggestions = search_card(f"name:{pokemon_name} number:{card_number}")
    elif card_number:
        suggestions = search_card(f"number:{card_number}")
    elif pokemon_name:
        suggestions = search_card(f"name:{pokemon_name}")

    return {
        "recto_text": detected_text,
        "language": lang,
        "pokemon_name": pokemon_name,
        "card_number": card_number,
        "suggestions": suggestions,
        "status": "pending_confirmation"
    }

# --- Confirm ---
@app.post("/confirm")
async def confirm_card(
    name: str = Form(...),
    set_name: str = Form(...),
    number: str = Form(...),
    rarity: str = Form(...),
    price: float = Form(...),
    image: str = Form(None),
    finish: str = Form("Normal"),
    user_id: int = Depends(get_current_user_id)
):
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        INSERT INTO cards (user_id, name, set_name, number, rarity, price, image, finish)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (user_id, name, set_name, number, rarity, price, image, finish))
    conn.commit()
    conn.close()
    return {"message": f"Carte {name} ({finish}) ajoutée ✅"}

# --- Liste avec filtres ---
@app.get("/collection/list")
def collection_list(
    set_name: str = Query(None),
    rarity: str = Query(None),
    finish: str = Query(None),
    min_price: float = Query(None),
    max_price: float = Query(None),
    user_id: int = Depends(get_current_user_id)
):
    conn = get_db()
    c = conn.cursor()
    query = "SELECT id, name, set_name, number, rarity, price, image, finish FROM cards WHERE user_id = ?"
    params = [user_id]
    if set_name:
        query += " AND set_name = ?"
        params.append(set_name)
    if rarity:
        query += " AND rarity = ?"
        params.append(rarity)
    if finish:
        query += " AND finish = ?"
        params.append(finish)
    if min_price is not None:
        query += " AND price >= ?"
        params.append(min_price)
    if max_price is not None:
        query += " AND price <= ?"
        params.append(max_price)
    c.execute(query, params)
    rows = c.fetchall()
    conn.close()
    return [
        {"id": r[0], "name": r[1], "set": r[2], "number": r[3], "rarity": r[4], "price": r[5], "image": r[6], "finish": r[7]}
        for r in rows
    ]

# --- Valeur totale ---
@app.get("/collection/value")
def collection_value(user_id: int = Depends(get_current_user_id)):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT SUM(price) FROM cards WHERE user_id = ?", (user_id,))
    total = c.fetchone()[0]
    conn.close()
    return {"total_value": total or 0.0}

# --- Stats avec top 5 ---
@app.get("/collection/stats")
def collection_stats(user_id: int = Depends(get_current_user_id)):
    conn = get_db()
    c = conn.cursor()

    # Statistiques globales
    c.execute("SELECT COUNT(*), AVG(price), MAX(price), MIN(price) FROM cards WHERE user_id = ?", (user_id,))
    count, avg_price, max_price, min_price = c.fetchone()

    # Carte la plus chère
    c.execute("SELECT name, set_name, price, finish FROM cards WHERE user_id = ? ORDER BY price DESC LIMIT 1", (user_id,))
    most_expensive = c.fetchone()

    # Top 5 cartes
    c.execute("SELECT name, set_name, price, finish FROM cards WHERE user_id = ? ORDER BY price DESC LIMIT 5", (user_id,))
    top5 = c.fetchall()

    conn.close()
    return {
        "count": count or 0,
        "avg_price": avg_price or 0.0,
        "max_price": max_price or 0.0,
        "min_price": min_price or 0.0,
        "most_expensive": {
            "name": most_expensive[0],
            "set": most_expensive[1],
            "price": most_expensive[2],
            "finish": most_expensive[3]
        } if most_expensive else None,
        "top5": [
            {"name": r[0], "set": r[1], "price": r[2], "finish": r[3]} for r in top5
        ]
    }
