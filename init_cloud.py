"""
Script per inizializzare il database su Streamlit Cloud con dati permanenti
Versione 1.0 - Include tutti i piatti del menu
"""

import sqlite3
import os
import tempfile
from pathlib import Path
import json
import hashlib

def hash_password(password: str) -> str:
    """Hash sicuro per le password"""
    return hashlib.sha256(password.encode()).hexdigest()

def init_cloud_database():
    """Inizializza il database con i dati del menu"""
    
    # Percorso database in cloud
    db_path = os.path.join(tempfile.gettempdir(), "ristorante.db")
    
    print("=" * 60)
    print("🍽️  INIZIALIZZAZIONE DATABASE CLOUD")
    print("=" * 60)
    print(f"📦 Database path: {db_path}")
    
    # Elimina se esiste (per ricrearlo pulito)
    if os.path.exists(db_path):
        os.remove(db_path)
        print("✅ Database esistente eliminato")
    
    # Crea connessione
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # ========================================================================
    # CREA TABELLE
    # ========================================================================
    print("📁 Creazione tabelle...")
    
    # Brand
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS brand (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Reparti
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reparti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            icona TEXT DEFAULT '👨‍🍳',
            colore TEXT DEFAULT '#3498db',
            ordine INTEGER DEFAULT 999,
            attivo INTEGER DEFAULT 1
        )
    """)
    
    # Sale
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sale (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            colore TEXT DEFAULT '#3498db',
            ordine INTEGER DEFAULT 999,
            attiva INTEGER DEFAULT 1
        )
    """)
    
    # Tavoli
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tavoli (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            numero INTEGER NOT NULL,
            sala_id INTEGER NOT NULL,
            capienza INTEGER DEFAULT 4,
            stato TEXT DEFAULT 'LIBERO',
            richiesta_conto INTEGER DEFAULT 0,
            FOREIGN KEY (sala_id) REFERENCES sale(id)
        )
    """)
    
    # Utenti
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS utenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            nome TEXT NOT NULL,
            cognome TEXT NOT NULL,
            ruolo TEXT NOT NULL,
            attivo INTEGER DEFAULT 1
        )
    """)
    
    # Categorie
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS categorie (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            reparto_id INTEGER NOT NULL,
            icona TEXT DEFAULT '🍽️',
            ordine INTEGER DEFAULT 999,
            attiva INTEGER DEFAULT 1,
            FOREIGN KEY (reparto_id) REFERENCES reparti(id)
        )
    """)
    
    # Piatti
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS piatti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE NOT NULL,
            categoria_id INTEGER NOT NULL,
            descrizione_pubblica TEXT,
            prezzo REAL NOT NULL,
            disponibile INTEGER DEFAULT 1,
            tempo_preparazione INTEGER DEFAULT 10,
            foto_data BLOB,
            ordine INTEGER DEFAULT 10,
            FOREIGN KEY (categoria_id) REFERENCES categorie(id)
        )
    """)
    
    # Variazioni
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS variazioni (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            prezzo REAL DEFAULT 0,
            reparto_id INTEGER NOT NULL,
            attivo INTEGER DEFAULT 1,
            ordine INTEGER DEFAULT 999,
            FOREIGN KEY (reparto_id) REFERENCES reparti(id)
        )
    """)
    
    # Comande
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comande (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tavolo_id INTEGER NOT NULL,
            cameriere_id INTEGER,
            stato TEXT DEFAULT 'ATTIVA',
            richiesta_conto INTEGER DEFAULT 0,
            timestamp_richiesta_conto TIMESTAMP,
            FOREIGN KEY (tavolo_id) REFERENCES tavoli(id),
            FOREIGN KEY (cameriere_id) REFERENCES utenti(id)
        )
    """)
    
    # Comandine
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS comandine (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comanda_id INTEGER NOT NULL,
            piatto_id INTEGER,
            piatto_nome TEXT NOT NULL,
            qty INTEGER DEFAULT 1,
            prezzo_unitario REAL NOT NULL,
            note TEXT,
            stato TEXT DEFAULT 'NUOVO',
            reparto_id INTEGER NOT NULL,
            tempo_consegna TEXT DEFAULT 'TEMPO2',
            timestamp_inserimento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (comanda_id) REFERENCES comande(id),
            FOREIGN KEY (piatto_id) REFERENCES piatti(id),
            FOREIGN KEY (reparto_id) REFERENCES reparti(id)
        )
    """)
    
    # Pagamenti
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pagamenti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comanda_id INTEGER NOT NULL,
            totale REAL NOT NULL,
            metodo TEXT NOT NULL,
            operatore_id INTEGER,
            timestamp_pagamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (comanda_id) REFERENCES comande(id),
            FOREIGN KEY (operatore_id) REFERENCES utenti(id)
        )
    """)
    
    # Notifiche
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS notifiche (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titolo TEXT NOT NULL,
            messaggio TEXT NOT NULL,
            destinatario_ruolo TEXT,
            letto INTEGER DEFAULT 0,
            timestamp_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # Preordini
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS preordini (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tavolo_id INTEGER NOT NULL,
            stato TEXT DEFAULT 'IN_ATTESA',
            timestamp_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            timestamp_revisione TIMESTAMP,
            cameriere_id INTEGER,
            note TEXT,
            FOREIGN KEY (tavolo_id) REFERENCES tavoli(id),
            FOREIGN KEY (cameriere_id) REFERENCES utenti(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS preordini_dettaglio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            preordine_id INTEGER NOT NULL,
            piatto_id INTEGER NOT NULL,
            piatto_nome TEXT NOT NULL,
            qty INTEGER DEFAULT 1,
            prezzo_unitario REAL NOT NULL,
            variazioni TEXT DEFAULT '[]',
            note TEXT,
            FOREIGN KEY (preordine_id) REFERENCES preordini(id),
            FOREIGN KEY (piatto_id) REFERENCES piatti(id)
        )
    """)
    
    # Config
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            chiave TEXT PRIMARY KEY,
            valore TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    print("✅ Tabelle create")
    
    # ========================================================================
    # POPOLA DATI INIZIALI
    # ========================================================================
    print("📊 Popolamento dati...")
    
    # Brand
    cursor.execute("INSERT OR IGNORE INTO brand (id, nome) VALUES (1, 'PALAZZO FIORINI')")
    
    # Reparti
    reparti = [
        (1, 'CUCINA', '👨‍🍳', '#e74c3c', 1),
        (2, 'BAR', '🍸', '#3498db', 2),
        (3, 'PASTICCERIA', '🍰', '#9b59b6', 3),
        (4, 'PIZZERIA', '🍕', '#e67e22', 4),
    ]
    for id, nome, icona, colore, ordine in reparti:
        cursor.execute("""
            INSERT OR IGNORE INTO reparti (id, nome, icona, colore, ordine, attivo)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (id, nome, icona, colore, ordine))
    print(f"   ✅ {len(reparti)} reparti")
    
    # Utenti (password: admin123, 123)
    utenti = [
        (1, 'admin', hash_password('admin123'), 'Admin', 'Super', 'SUPERADMIN'),
        (2, 'cameriere', hash_password('123'), 'Mario', 'Rossi', 'CAMERIERE'),
        (3, 'cucina', hash_password('123'), 'Luigi', 'Verdi', 'CUCINA'),
        (4, 'bar', hash_password('123'), 'Giovanni', 'Bianchi', 'BAR'),
        (5, 'cassa', hash_password('123'), 'Anna', 'Neri', 'CASSA'),
    ]
    for id, username, pwd, nome, cognome, ruolo in utenti:
        cursor.execute("""
            INSERT OR IGNORE INTO utenti (id, username, password_hash, nome, cognome, ruolo, attivo)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """, (id, username, pwd, nome, cognome, ruolo))
    print(f"   ✅ {len(utenti)} utenti")
    
    # Sale
    sale = [
        (1, 'SALA PRINCIPALE', '#2ecc71', 1),
        (2, 'TERRAZZA', '#f1c40f', 2),
        (3, 'SALA PRIVATA', '#9b59b6', 3),
    ]
    for id, nome, colore, ordine in sale:
        cursor.execute("""
            INSERT OR IGNORE INTO sale (id, nome, colore, ordine, attiva)
            VALUES (?, ?, ?, ?, 1)
        """, (id, nome, colore, ordine))
    print(f"   ✅ {len(sale)} sale")
    
    # Tavoli
    tavoli_per_sala = {1: 8, 2: 6, 3: 4}
    tavoli_inseriti = 0
    for sala_id, num_tavoli in tavoli_per_sala.items():
        for i in range(1, num_tavoli + 1):
            cursor.execute("""
                INSERT OR IGNORE INTO tavoli (numero, sala_id, capienza, stato)
                VALUES (?, ?, ?, 'LIBERO')
            """, (i, sala_id, 4))
            tavoli_inseriti += 1
    print(f"   ✅ {tavoli_inseriti} tavoli")
    
    # Categorie
    categorie = [
        (1, 'ANTIPASTI', 1, '🥗', 1),
        (2, 'PRIMI', 1, '🍝', 2),
        (3, 'SECONDI', 1, '🥩', 3),
        (4, 'CONTORNI', 1, '🥦', 4),
        (5, 'DOLCI', 3, '🍰', 5),
        (6, 'BEVANDE', 2, '🥤', 6),
        (7, 'PIZZE', 4, '🍕', 7),
    ]
    for id, nome, reparto_id, icona, ordine in categorie:
        cursor.execute("""
            INSERT OR IGNORE INTO categorie (id, nome, reparto_id, icona, ordine, attiva)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (id, nome, reparto_id, icona, ordine))
    print(f"   ✅ {len(categorie)} categorie")
    
    # PIATTI - QUESTO È CIÒ CHE VEDRANNO I CLIENTI!
    piatti = [
        # ANTIPASTI (categoria 1)
        (1, 'Bruschetta Classica', 1, 6.50, 'Pane tostato con pomodoro, aglio, origano e olio EVO'),
        (2, 'Tagliere di Salumi Misti', 1, 12.00, 'Prosciutto crudo, salame, coppa e mortadella'),
        (3, 'Calamari Fritti', 1, 9.00, 'Calamari freschi fritti con salsa tartara'),
        (4, 'Polpo alla Griglia', 1, 11.00, 'Polpo tenero grigliato con patate e prezzemolo'),
        
        # PRIMI (categoria 2)
        (5, 'Spaghetti Carbonara', 2, 12.00, 'Uova, pecorino romano, guanciale e pepe nero'),
        (6, 'Lasagna alla Bolognese', 2, 13.00, 'Sfoglie all\'uovo, ragù di carne, besciamella e parmigiano'),
        (7, 'Risotto ai Funghi Porcini', 2, 14.00, 'Riso carnaroli con funghi porcini freschi'),
        (8, 'Gnocchi di Patate al Pesto', 2, 11.00, 'Gnocchi fatti in casa con pesto alla genovese'),
        
        # SECONDI (categoria 3)
        (9, 'Tagliata di Manzo', 3, 18.00, 'Manzo con rucola, scaglie di grana e aceto balsamico'),
        (10, 'Branzino al Forno', 3, 16.00, 'Branzino con patate, rosmarino e pomodorini'),
        (11, 'Cotoletta alla Milanese', 3, 15.00, 'Cotoletta di vitello impanata e fritta'),
        (12, 'Hamburger di Chianina', 3, 14.00, 'Chianina con bacon, cheddar, lattuga e pomodoro'),
        
        # CONTORNI (categoria 4)
        (13, 'Patate al Forno', 4, 5.00, 'Patate con rosmarino, aglio e olio EVO'),
        (14, 'Insalata Mista', 4, 4.50, 'Lattuga, pomodorini, carote e mais'),
        (15, 'Verdure Grigliate', 4, 6.00, 'Zucchine, melanzane, peperoni e cipolle'),
        
        # DOLCI (categoria 5)
        (16, 'Tiramisù', 5, 7.00, 'Mascarpone, caffè, savoiardi e cacao amaro'),
        (17, 'Panna Cotta', 5, 6.00, 'Panna cotta con salsa ai frutti di bosco'),
        (18, 'Cannolo Siciliano', 5, 5.00, 'Cannolo con ricotta fresca e gocce di cioccolato'),
        
        # BEVANDE (categoria 6)
        (19, 'Acqua 1L', 6, 2.50, 'Acqua naturale o frizzante'),
        (20, 'Coca Cola', 6, 3.00, 'Coca Cola in lattina 33cl'),
        (21, 'Birra alla Spina', 6, 4.00, 'Birra chiara 40cl'),
        (22, 'Vino della Casa', 6, 5.00, 'Vino rosso o bianco della casa (250ml)'),
        
        # PIZZE (categoria 7)
        (23, 'Pizza Margherita', 7, 8.00, 'Pomodoro, mozzarella, basilico e olio EVO'),
        (24, 'Pizza Diavola', 7, 9.00, 'Pomodoro, mozzarella e salame piccante'),
        (25, 'Pizza Quattro Stagioni', 7, 10.00, 'Carciofi, olive, prosciutto cotto e funghi'),
        (26, 'Pizza Capricciosa', 7, 10.00, 'Pomodoro, mozzarella, funghi, carciofi e prosciutto cotto'),
    ]
    
    for id, nome, cat_id, prezzo, descrizione in piatti:
        cursor.execute("""
            INSERT OR IGNORE INTO piatti (id, nome, categoria_id, prezzo, descrizione_pubblica, disponibile, tempo_preparazione, ordine)
            VALUES (?, ?, ?, ?, ?, 1, 15, ?)
        """, (id, nome, cat_id, prezzo, descrizione, id))
    print(f"   ✅ {len(piatti)} piatti nel menu")
    
    # Variazioni
    variazioni = [
        (1, 'Mozzarella extra', 1.50, 4, 1),
        (2, 'Funghi', 1.00, 4, 2),
        (3, 'Prosciutto', 2.00, 4, 3),
        (4, 'Pomodoro extra', 0.50, 4, 4),
        (5, 'Senza Glutine', 0.00, 1, 5),
        (6, 'Senza Lattosio', 0.00, 1, 6),
        (7, 'Ben cotto', 0.00, 1, 7),
        (8, 'Al sangue', 0.00, 1, 8),
    ]
    for id, nome, prezzo, reparto_id, ordine in variazioni:
        cursor.execute("""
            INSERT OR IGNORE INTO variazioni (id, nome, prezzo, reparto_id, attivo, ordine)
            VALUES (?, ?, ?, ?, 1, ?)
        """, (id, nome, prezzo, reparto_id, ordine))
    print(f"   ✅ {len(variazioni)} variazioni")
    
    # Config
    cursor.execute("""
        INSERT OR IGNORE INTO config (chiave, valore)
        VALUES ('public_url', 'https://bons72-ristorapp.streamlit.app')
    """)
    
    conn.commit()
    conn.close()
    
    print("=" * 60)
    print("✅ DATABASE CLOUD INIZIALIZZATO CON SUCCESSO!")
    print(f"📊 Riepilogo:")
    print(f"   - {len(piatti)} piatti nel menu")
    print(f"   - {len(categorie)} categorie")
    print(f"   - {len(reparti)} reparti")
    print(f"   - {tavoli_inseriti} tavoli")
    print(f"   - {len(utenti)} utenti")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    init_cloud_database()