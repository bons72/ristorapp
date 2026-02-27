"""
Inizializzazione database per Streamlit Cloud
Versione 1.0 - Gestisce la creazione automatica del database
"""

import sqlite3
import os
import tempfile
import hashlib
from datetime import datetime

def init_database():
    """Inizializza il database se non esiste"""
    
    # Determina il percorso del database
    if os.environ.get('STREAMLIT_CLOUD'):
        db_path = os.path.join(tempfile.gettempdir(), "ristorante.db")
    else:
        db_path = "ristorante.db"
    
    print(f"📦 Database path: {db_path}")
    
    # Verifica se il database esiste già
    db_exists = os.path.exists(db_path)
    
    if not db_exists:
        print("🔄 Database non trovato. Creazione in corso...")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # ====================================================================
        # CREAZIONE TABELLE
        # ====================================================================
        
        # 1. BRAND
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS brand (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                logo_path TEXT,
                indirizzo TEXT,
                telefono TEXT,
                email TEXT,
                partita_iva TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 2. UTENTI
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS utenti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                nome TEXT NOT NULL,
                cognome TEXT NOT NULL,
                ruolo TEXT NOT NULL CHECK(ruolo IN ('SUPERADMIN', 'ADMIN', 'CAMERIERE', 'CUCINA', 'BAR', 'CASSA')),
                brand_id INTEGER DEFAULT 1,
                attivo INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (brand_id) REFERENCES brand(id)
            )
        """)
        
        # 3. SALE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sale (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                descrizione TEXT,
                colore TEXT DEFAULT '#3498db',
                ordine INTEGER DEFAULT 999,
                attiva INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 4. TAVOLI
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tavoli (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero INTEGER NOT NULL,
                nome_tavolo TEXT,
                sala_id INTEGER NOT NULL,
                capienza INTEGER DEFAULT 4,
                posizione_x INTEGER DEFAULT 0,
                posizione_y INTEGER DEFAULT 0,
                stato TEXT DEFAULT 'LIBERO' CHECK(stato IN ('LIBERO', 'OCCUPATO', 'PRENOTATO', 'DA_PULIRE')),
                richiesta_conto INTEGER DEFAULT 0,
                ultima_modifica TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (sala_id) REFERENCES sale(id) ON DELETE CASCADE,
                UNIQUE(sala_id, numero)
            )
        """)
        
        # 5. REPARTI
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reparti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                icona TEXT DEFAULT '👨‍🍳',
                colore TEXT DEFAULT '#3498db',
                ordine INTEGER DEFAULT 999,
                attivo INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 6. CATEGORIE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categorie (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                descrizione TEXT,
                reparto_id INTEGER NOT NULL,
                icona TEXT DEFAULT '🍽️',
                ordine INTEGER DEFAULT 999,
                attiva INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reparto_id) REFERENCES reparti(id)
            )
        """)
        
        # 7. PIATTI
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS piatti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                categoria_id INTEGER NOT NULL,
                descrizione_pubblica TEXT,
                descrizione_privata TEXT,
                prezzo REAL NOT NULL CHECK(prezzo >= 0),
                disponibile INTEGER DEFAULT 1,
                tempo_preparazione INTEGER DEFAULT 10,
                foto_path TEXT DEFAULT NULL,
                foto_data BLOB DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (categoria_id) REFERENCES categorie(id) ON DELETE CASCADE
            )
        """)
        
        # 8. VARIAZIONI
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS variazioni (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                prezzo REAL DEFAULT 0,
                reparto_id INTEGER NOT NULL,
                attivo INTEGER DEFAULT 1,
                ordine INTEGER DEFAULT 999,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reparto_id) REFERENCES reparti(id)
            )
        """)
        
        # 9. COMANDE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comande (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tavolo_id INTEGER NOT NULL,
                cameriere_id INTEGER,
                numero_persone INTEGER DEFAULT 1,
                totale REAL DEFAULT 0,
                stato TEXT DEFAULT 'ATTIVA' CHECK(stato IN ('ATTIVA', 'CHIUSA', 'ANNULLATA')),
                richiesta_conto INTEGER DEFAULT 0,
                timestamp_richiesta_conto TIMESTAMP,
                metodo_pagamento TEXT,
                importo_pagato REAL DEFAULT 0,
                resto REAL DEFAULT 0,
                note TEXT,
                timestamp_apertura TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                timestamp_chiusura TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tavolo_id) REFERENCES tavoli(id),
                FOREIGN KEY (cameriere_id) REFERENCES utenti(id)
            )
        """)
        
        # 10. COMANDINE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS comandine (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comanda_id INTEGER NOT NULL,
                piatto_id INTEGER,
                piatto_nome TEXT NOT NULL,
                qty INTEGER DEFAULT 1,
                prezzo_unitario REAL NOT NULL,
                note TEXT,
                stato TEXT DEFAULT 'NUOVO' CHECK(stato IN ('NUOVO', 'IN_CORSO', 'PRONTO', 'SERVITO', 'ANNULLATO')),
                reparto_id INTEGER NOT NULL,
                priorita INTEGER DEFAULT 1,
                tempo_consegna TEXT DEFAULT 'TEMPO2' CHECK(tempo_consegna IN ('TEMPO1', 'TEMPO2', 'TEMPO3', 'TEMPO4')),
                minuti_consegna INTEGER DEFAULT 0,
                timestamp_richiesto TIMESTAMP,
                timestamp_inserimento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                timestamp_inizio TIMESTAMP,
                timestamp_pronto TIMESTAMP,
                timestamp_servito TIMESTAMP,
                operatore_id INTEGER,
                FOREIGN KEY (comanda_id) REFERENCES comande(id) ON DELETE CASCADE,
                FOREIGN KEY (piatto_id) REFERENCES piatti(id),
                FOREIGN KEY (reparto_id) REFERENCES reparti(id),
                FOREIGN KEY (operatore_id) REFERENCES utenti(id)
            )
        """)
        
        # 11. PAGAMENTI
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pagamenti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comanda_id INTEGER NOT NULL,
                totale REAL NOT NULL,
                contanti REAL DEFAULT 0,
                carta REAL DEFAULT 0,
                bancomat REAL DEFAULT 0,
                altri REAL DEFAULT 0,
                resto REAL DEFAULT 0,
                metodo TEXT NOT NULL,
                note TEXT,
                operatore_id INTEGER,
                timestamp_pagamento TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (comanda_id) REFERENCES comande(id),
                FOREIGN KEY (operatore_id) REFERENCES utenti(id)
            )
        """)
        
        # 12. NOTIFICHE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifiche (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                titolo TEXT NOT NULL,
                messaggio TEXT NOT NULL,
                destinatario_id INTEGER,
                destinatario_ruolo TEXT,
                letto INTEGER DEFAULT 0,
                timestamp_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                timestamp_lettura TIMESTAMP,
                FOREIGN KEY (destinatario_id) REFERENCES utenti(id)
            )
        """)
        
        # 13. GIORNALE CASSA
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS giornale_cassa (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data DATE NOT NULL UNIQUE,
                operatore_apertura_id INTEGER,
                operatore_chiusura_id INTEGER,
                apertura_at TIMESTAMP,
                chiusura_at TIMESTAMP,
                fondo_iniziale REAL DEFAULT 200.0,
                totale_contanti REAL DEFAULT 0,
                totale_carte REAL DEFAULT 0,
                totale_bancomat REAL DEFAULT 0,
                totale_altri REAL DEFAULT 0,
                totale_incassi REAL DEFAULT 0,
                numero_scontrini INTEGER DEFAULT 0,
                differenza REAL DEFAULT 0,
                note TEXT,
                stato TEXT DEFAULT 'APERTA' CHECK(stato IN ('APERTA', 'CHIUSA')),
                FOREIGN KEY (operatore_apertura_id) REFERENCES utenti(id),
                FOREIGN KEY (operatore_chiusura_id) REFERENCES utenti(id)
            )
        """)
        
        # 14. STAMPANTI
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stampanti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                reparto_id INTEGER NOT NULL,
                tipo TEXT DEFAULT 'TERMICA' CHECK(tipo IN ('TERMICA', 'FISCALE', 'ETICHETTE')),
                indirizzo_ip TEXT,
                porta INTEGER DEFAULT 9100,
                usb_vendor_id INTEGER,
                usb_product_id INTEGER,
                caratteri_per_riga INTEGER DEFAULT 42,
                stampa_automatica INTEGER DEFAULT 1,
                attivo INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reparto_id) REFERENCES reparti(id)
            )
        """)
        
        # 15. LOG STAMPE
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS log_stampe (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                reparto_id INTEGER,
                comanda_id INTEGER,
                contenuto TEXT,
                esito TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (reparto_id) REFERENCES reparti(id),
                FOREIGN KEY (comanda_id) REFERENCES comande(id)
            )
        """)
        
        # 16. PREORDINI
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preordini (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tavolo_id INTEGER NOT NULL,
                cliente_nome TEXT,
                stato TEXT DEFAULT 'IN_ATTESA' CHECK(stato IN ('IN_ATTESA', 'REVISIONATO', 'CONFERMATO', 'ANNULLATO')),
                timestamp_creazione TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                timestamp_revisione TIMESTAMP,
                cameriere_id INTEGER,
                note TEXT,
                FOREIGN KEY (tavolo_id) REFERENCES tavoli(id),
                FOREIGN KEY (cameriere_id) REFERENCES utenti(id)
            )
        """)
        
        # 17. PREORDINI DETTAGLIO
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preordini_dettaglio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                preordine_id INTEGER NOT NULL,
                piatto_id INTEGER NOT NULL,
                piatto_nome TEXT NOT NULL,
                qty INTEGER DEFAULT 1,
                prezzo_unitario REAL NOT NULL,
                variazioni TEXT,
                note TEXT,
                FOREIGN KEY (preordine_id) REFERENCES preordini(id) ON DELETE CASCADE,
                FOREIGN KEY (piatto_id) REFERENCES piatti(id)
            )
        """)
        
        # 18. CLIENTI
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS clienti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider_id TEXT UNIQUE,
                provider TEXT,
                email TEXT,
                nome TEXT,
                ultimo_accesso TIMESTAMP,
                tavolo_id INTEGER,
                ordini_totali INTEGER DEFAULT 0,
                spesa_totale REAL DEFAULT 0
            )
        """)
        
        # ====================================================================
        # INDICI
        # ====================================================================
        indici = [
            ("idx_comande_tavolo_stato", "comande(tavolo_id, stato)"),
            ("idx_comande_richiesta_conto", "comande(richiesta_conto)"),
            ("idx_comandine_comanda", "comandine(comanda_id)"),
            ("idx_comandine_stato_reparto", "comandine(stato, reparto_id)"),
            ("idx_tavoli_sala_stato", "tavoli(sala_id, stato)"),
        ]
        
        for nome, definizione in indici:
            try:
                cursor.execute(f"CREATE INDEX IF NOT EXISTS {nome} ON {definizione}")
            except Exception as e:
                print(f"⚠️ Errore creazione indice {nome}: {e}")
        
        # ====================================================================
        # DATI INIZIALI
        # ====================================================================
        
        # Brand
        cursor.execute("""
            INSERT OR IGNORE INTO brand (id, nome, partita_iva) 
            VALUES (1, 'PALAZZO FIORINI', '01234567890')
        """)
        
        # Reparti
        reparti = [
            (1, 'CUCINA', '👨‍🍳', '#e74c3c', 1),
            (2, 'BAR', '🍸', '#3498db', 2),
            (3, 'PASTICCERIA', '🍰', '#9b59b6', 3),
            (4, 'PIZZERIA', '🍕', '#e67e22', 4),
        ]
        for id, nome, icona, colore, ordine in reparti:
            cursor.execute("""
                INSERT OR IGNORE INTO reparti (id, nome, icona, colore, ordine)
                VALUES (?, ?, ?, ?, ?)
            """, (id, nome, icona, colore, ordine))
        
        # Utenti
        def hash_password(password):
            return hashlib.sha256(password.encode()).hexdigest()
        
        utenti = [
            (1, 'admin', hash_password('admin123'), 'Admin', 'Super', 'SUPERADMIN'),
            (2, 'cameriere', hash_password('123'), 'Mario', 'Rossi', 'CAMERIERE'),
            (3, 'cucina', hash_password('123'), 'Luigi', 'Verdi', 'CUCINA'),
            (4, 'bar', hash_password('123'), 'Giovanni', 'Bianchi', 'BAR'),
            (5, 'cassa', hash_password('123'), 'Anna', 'Neri', 'CASSA'),
        ]
        for id, username, pwd_hash, nome, cognome, ruolo in utenti:
            cursor.execute("""
                INSERT OR IGNORE INTO utenti (id, username, password_hash, nome, cognome, ruolo, brand_id)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (id, username, pwd_hash, nome, cognome, ruolo))
        
        # Sale
        sale = [
            (1, 'SALA PRINCIPALE', '#2ecc71', 1),
            (2, 'TERRAZZA', '#f1c40f', 2),
            (3, 'SALA PRIVATA', '#9b59b6', 3),
        ]
        for id, nome, colore, ordine in sale:
            cursor.execute("""
                INSERT OR IGNORE INTO sale (id, nome, colore, ordine)
                VALUES (?, ?, ?, ?)
            """, (id, nome, colore, ordine))
        
        # Tavoli
        tavoli_per_sala = {1: 8, 2: 6, 3: 4}
        for sala_id, num_tavoli in tavoli_per_sala.items():
            for i in range(1, num_tavoli + 1):
                cursor.execute("""
                    INSERT OR IGNORE INTO tavoli (numero, sala_id, capienza, stato)
                    VALUES (?, ?, ?, 'LIBERO')
                """, (i, sala_id, 4))
        
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
                INSERT OR IGNORE INTO categorie (id, nome, reparto_id, icona, ordine)
                VALUES (?, ?, ?, ?, ?)
            """, (id, nome, reparto_id, icona, ordine))
        
        # Piatti
        piatti = [
            (1, 'Bruschetta', 1, 6.50, 1),
            (2, 'Spaghetti Carbonara', 2, 12.00, 1),
            (3, 'Tagliata di Manzo', 3, 18.00, 1),
            (4, 'Patate al Forno', 4, 5.00, 1),
            (5, 'Tiramisù', 5, 7.00, 1),
            (6, 'Acqua 1L', 6, 2.50, 1),
            (7, 'Pizza Margherita', 7, 8.00, 1),
        ]
        for id, nome, cat_id, prezzo, disp in piatti:
            cursor.execute("""
                INSERT OR IGNORE INTO piatti (id, nome, categoria_id, prezzo, disponibile)
                VALUES (?, ?, ?, ?, ?)
            """, (id, nome, cat_id, prezzo, disp))
        
        # Variazioni
        variazioni = [
            (1, 'Glutine', 0.50, 1, 1),
            (2, 'Lattosio', 0.50, 1, 2),
            (3, 'Mozzarella extra', 1.50, 1, 3),
            (4, 'Funghi', 1.00, 4, 4),
            (5, 'Crostino', 0.30, 1, 5),
        ]
        for id, nome, prezzo, reparto_id, ordine in variazioni:
            cursor.execute("""
                INSERT OR IGNORE INTO variazioni (id, nome, prezzo, reparto_id, ordine)
                VALUES (?, ?, ?, ?, ?)
            """, (id, nome, prezzo, reparto_id, ordine))
        
        conn.commit()
        conn.close()
        
        print("✅ Database creato e inizializzato con successo!")
    else:
        print("✅ Database già esistente")
    
    return db_path

# Se eseguito direttamente
if __name__ == "__main__":
    print("=" * 60)
    print("🔄 INIZIALIZZAZIONE DATABASE")
    print("=" * 60)
    db_path = init_database()
    print(f"📦 Database pronto in: {db_path}")