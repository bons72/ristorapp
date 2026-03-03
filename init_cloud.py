"""
Script per inizializzare il database su Streamlit Cloud - VERSIONE CHE MANTIENE I DATI
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
    """Inizializza il database SOLO SE NON ESISTE, mantenendo i dati esistenti"""
    
    db_path = os.path.join(tempfile.gettempdir(), "ristorante.db")
    
    print("=" * 60)
    print("🍽️  VERIFICA DATABASE CLOUD")
    print("=" * 60)
    print(f"📦 Database path: {db_path}")
    
    # === DEBUG: Mostra se il database esiste ===
    if os.path.exists(db_path):
        print(f"✅ Database esiste. Dimensione: {os.path.getsize(db_path)} bytes")
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM piatti")
            count = cursor.fetchone()[0]
            print(f"📊 Piatti nel database esistente: {count}")
            
            cursor.execute("SELECT COUNT(*) FROM brand WHERE logo_data IS NOT NULL")
            logo_count = cursor.fetchone()[0]
            print(f"📊 Brand con logo: {logo_count}")
            
            conn.close()
        except Exception as e:
            print(f"⚠️ Errore lettura database: {e}")
    else:
        print("❌ Database NON esiste, verrà creato nuovo")
    # === FINE DEBUG ===
    
    # Se il database esiste già, non fare nulla
    if os.path.exists(db_path):
        print("✅ Database esistente trovato. Nessuna modifica effettuata.")
        return True
    
    print("🔄 Database non trovato. Creazione nuovo database...")
    
    # Crea connessione
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # ========================================================================
    # CREA TABELLE (SOLO SE NON ESISTONO)
    # ========================================================================
    print("📁 Creazione tabelle...")
    
    # Brand
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS brand (
            id INTEGER PRIMARY KEY DEFAULT 1,
            nome TEXT NOT NULL,
            indirizzo TEXT,
            telefono TEXT,
            email TEXT,
            partita_iva TEXT,
            logo_data BLOB,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    
    # Comande, preordini, ecc...
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
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            chiave TEXT PRIMARY KEY,
            valore TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # ========================================================================
    # POPOLA SOLO I DATI INIZIALI ESSENZIALI (SE LE TABELLE SONO VUOTE)
    # ========================================================================
    print("📊 Verifica e popolamento dati essenziali...")
    
    # Brand default (solo se non esiste)
    cursor.execute("SELECT COUNT(*) FROM brand")
    if cursor.fetchone()[0] == 0:
        cursor.execute("INSERT INTO brand (id, nome) VALUES (1, 'PALAZZO FIORINI')")
        print("   ✅ Brand default creato")
    
    # Reparti (solo se non esistono)
    cursor.execute("SELECT COUNT(*) FROM reparti")
    if cursor.fetchone()[0] == 0:
        reparti = [
            (1, 'CUCINA', '👨‍🍳', '#e74c3c', 1),
            (2, 'BAR', '🍸', '#3498db', 2),
            (3, 'PASTICCERIA', '🍰', '#9b59b6', 3),
            (4, 'PIZZERIA', '🍕', '#e67e22', 4),
        ]
        for id, nome, icona, colore, ordine in reparti:
            cursor.execute("""
                INSERT INTO reparti (id, nome, icona, colore, ordine, attivo)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (id, nome, icona, colore, ordine))
        print(f"   ✅ {len(reparti)} reparti creati")
    
    # Utenti (solo se non esistono)
    cursor.execute("SELECT COUNT(*) FROM utenti")
    if cursor.fetchone()[0] == 0:
        utenti = [
            (1, 'admin', hash_password('admin123'), 'Admin', 'Super', 'SUPERADMIN'),
            (2, 'cameriere', hash_password('123'), 'Mario', 'Rossi', 'CAMERIERE'),
            (3, 'cucina', hash_password('123'), 'Luigi', 'Verdi', 'CUCINA'),
            (4, 'bar', hash_password('123'), 'Giovanni', 'Bianchi', 'BAR'),
            (5, 'cassa', hash_password('123'), 'Anna', 'Neri', 'CASSA'),
        ]
        for id, username, pwd, nome, cognome, ruolo in utenti:
            cursor.execute("""
                INSERT INTO utenti (id, username, password_hash, nome, cognome, ruolo, attivo)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (id, username, pwd, nome, cognome, ruolo))
        print(f"   ✅ {len(utenti)} utenti creati")
    
    # Sale (solo se non esistono)
    cursor.execute("SELECT COUNT(*) FROM sale")
    if cursor.fetchone()[0] == 0:
        sale = [
            (1, 'SALA PRINCIPALE', '#2ecc71', 1),
            (2, 'TERRAZZA', '#f1c40f', 2),
            (3, 'SALA PRIVATA', '#9b59b6', 3),
        ]
        for id, nome, colore, ordine in sale:
            cursor.execute("""
                INSERT INTO sale (id, nome, colore, ordine, attiva)
                VALUES (?, ?, ?, ?, 1)
            """, (id, nome, colore, ordine))
        print(f"   ✅ {len(sale)} sale create")
    
    # Tavoli (solo se non esistono)
    cursor.execute("SELECT COUNT(*) FROM tavoli")
    if cursor.fetchone()[0] == 0:
        tavoli_per_sala = {1: 8, 2: 6, 3: 4}
        tavoli_inseriti = 0
        for sala_id, num_tavoli in tavoli_per_sala.items():
            for i in range(1, num_tavoli + 1):
                cursor.execute("""
                    INSERT INTO tavoli (numero, sala_id, capienza, stato)
                    VALUES (?, ?, ?, 'LIBERO')
                """, (i, sala_id, 4))
                tavoli_inseriti += 1
        print(f"   ✅ {tavoli_inseriti} tavoli creati")
    
    # Categorie (solo se non esistono)
    cursor.execute("SELECT COUNT(*) FROM categorie")
    if cursor.fetchone()[0] == 0:
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
                INSERT INTO categorie (id, nome, reparto_id, icona, ordine, attiva)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (id, nome, reparto_id, icona, ordine))
        print(f"   ✅ {len(categorie)} categorie create")
    
    # PIATTI DI DEFAULT (solo se non esistono)
    cursor.execute("SELECT COUNT(*) FROM piatti")
    if cursor.fetchone()[0] == 0:
        piatti = [
            (1, 'Bruschetta', 1, 6.50, 'Pane tostato con pomodoro, aglio e origano'),
            (2, 'Spaghetti Carbonara', 2, 12.00, 'Uova, pecorino, guanciale e pepe'),
            (3, 'Tagliata di Manzo', 3, 18.00, 'Manzo con rucola, grana e aceto balsamico'),
            (4, 'Patate al Forno', 4, 5.00, 'Patate con rosmarino e aglio'),
            (5, 'Tiramisù', 5, 7.00, 'Mascarpone, caffè, savoiardi e cacao'),
            (6, 'Acqua 1L', 6, 2.50, 'Acqua naturale o frizzante'),
            (7, 'Pizza Margherita', 7, 8.00, 'Pomodoro, mozzarella e basilico'),
        ]
        for id, nome, cat_id, prezzo, descrizione in piatti:
            cursor.execute("""
                INSERT INTO piatti (id, nome, categoria_id, prezzo, descrizione_pubblica, disponibile, tempo_preparazione, ordine)
                VALUES (?, ?, ?, ?, ?, 1, 15, ?)
            """, (id, nome, cat_id, prezzo, descrizione, id))
        print(f"   ✅ {len(piatti)} piatti di default creati")
    
    # Config
    cursor.execute("SELECT COUNT(*) FROM config WHERE chiave = 'public_url'")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO config (chiave, valore)
            VALUES ('public_url', 'https://bons72-ristorapp.streamlit.app')
        """)
        print("   ✅ URL pubblico configurato")
    
    conn.commit()
    conn.close()
    
    print("=" * 60)
    print("✅ DATABASE INIZIALIZZATO CON SUCCESSO!")
    print("=" * 60)
    
    return True

if __name__ == "__main__":
    init_cloud_database()