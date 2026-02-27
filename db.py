"""
DATABASE MANAGER PROFESSIONALE - PALAZZO FIORINI
Versione 2.0 - Ottimizzato per performance e affidabilità
"""

import sqlite3
import os
import hashlib
import platform
import shutil
import tempfile  # <--- IMPORTANTE: aggiunto per Streamlit Cloud
from datetime import datetime, date
from contextlib import contextmanager
import logging
from typing import Optional, Dict, List, Any, Tuple

# ============================================================================
# CONFIGURAZIONE PERCORSO DATABASE (AGGIUNTO PER STREAMLIT CLOUD)
# ============================================================================
def get_database_path():
    """Restituisce il percorso corretto per il database in base all'ambiente"""
    if os.environ.get('STREAMLIT_CLOUD'):
        # Su Streamlit Cloud, usa la cartella temporanea (scrivibile)
        return os.path.join(tempfile.gettempdir(), "ristorante.db")
    else:
        # In locale, usa la cartella corrente
        return "ristorante.db"

DB_PATH = get_database_path()

# ============================================================================
# CONFIGURAZIONE LOGGING
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ristorante.log' if not os.environ.get('STREAMLIT_CLOUD') else '/tmp/ristorante.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURAZIONE DATETIME PER SQLITE
# ============================================================================
def adapt_datetime(dt):
    return dt.isoformat()

def convert_datetime(s):
    if isinstance(s, bytes):
        s = s.decode()
    return datetime.fromisoformat(s)

sqlite3.register_adapter(datetime, adapt_datetime)
sqlite3.register_converter("TIMESTAMP", convert_datetime)
sqlite3.register_adapter(date, lambda d: d.isoformat())
sqlite3.register_converter("DATE", lambda s: date.fromisoformat(s.decode()))

# ============================================================================
# UTILITIES
# ============================================================================
def hash_password(password: str) -> str:
    """Hash sicuro per le password"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(stored_hash: str, password: str) -> bool:
    """Verifica password"""
    return stored_hash == hash_password(password)

def dict_factory(cursor, row):
    """Factory per risultati come dizionari"""
    return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

# ============================================================================
# CONNESSIONE DATABASE
# ============================================================================
@contextmanager
def get_db_connection(init_mode: bool = False):
    """
    Gestione connessione thread-safe con context manager
    """
    conn = None
    try:
        timeout = 60 if init_mode else 30
        journal_mode = "DELETE" if init_mode else "WAL"
        
        # Usa il percorso dinamico
        conn = sqlite3.connect(
            DB_PATH,  # <--- USATO IL PERCORSO DINAMICO
            check_same_thread=False,
            timeout=timeout,
            detect_types=sqlite3.PARSE_DECLTYPES,
            isolation_level=None if init_mode else "DEFERRED"
        )
        conn.row_factory = dict_factory
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute(f"PRAGMA journal_mode = {journal_mode}")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute(f"PRAGMA busy_timeout = {10000 if init_mode else 5000}")
        
        yield conn
    except sqlite3.Error as e:
        logger.error(f"Database error: {e}")
        raise
    finally:
        if conn:
            try:
                if not init_mode:
                    conn.execute("PRAGMA optimize")
                conn.commit()
            except:
                pass
            finally:
                conn.close()

# ============================================================================
# FUNZIONE HELPER PER QUERY RAPIDE (CORRETTA)
# ============================================================================
def esegui_query(query: str, params: tuple = (), 
                 fetchone: bool = False, fetchall: bool = False, 
                 commit: bool = False) -> Any:
    """Esegue query SQL in modo sicuro"""
    
    # Usa il percorso dinamico
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = dict_factory
    cursor = conn.cursor()
    
    try:
        cursor.execute(query, params)
        if commit:
            conn.commit()
            lastrowid = cursor.lastrowid
            conn.close()
            return lastrowid
        elif fetchone:
            result = cursor.fetchone()
            conn.close()
            return result
        elif fetchall:
            result = cursor.fetchall()
            conn.close()
            return result
        conn.close()
        return cursor
    except sqlite3.Error as e:
        conn.close()
        logger.error(f"Query error: {e}\nQuery: {query[:100]}...\nParams: {params}")
        raise

# ============================================================================
# CREAZIONE TABELLE
# ============================================================================
def create_tables(cursor):
    """Crea tutte le tabelle con struttura ottimizzata"""
    
    logger.info("Creazione tabelle...")
    
    # 1. UTENTI E BRAND
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
    
    # 2. SALE E TAVOLI
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
    
    # 3. REPARTI
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
    
    # 4. MENU
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
    
    # 5. VARIAZIONI
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
    
    # 6. COMANDE
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
    
    # 7. PAGAMENTI
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
    
    # 8. NOTIFICHE
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
    
    # 9. GIORNALE DI CASSA
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
    
    # 10. CONFIGURAZIONE STAMPANTI
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
    
    # 11. LOG STAMPE
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
    
    # 12. PRE-ORDINI CLIENTI
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
    
    # 13. CLIENTI (AGGIUNTO PER LOGIN SOCIALE)
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

    logger.info("Tabelle create con successo")

# ============================================================================
# INDICI PER PERFORMANCE
# ============================================================================
def create_indexes(cursor):
    """Crea indici per ottimizzare le query frequenti"""
    
    logger.info("Creazione indici...")
    
    indici = [
        ("idx_comande_tavolo_stato", "comande(tavolo_id, stato)"),
        ("idx_comande_richiesta_conto", "comande(richiesta_conto)"),
        ("idx_comandine_comanda", "comandine(comanda_id)"),
        ("idx_comandine_stato_reparto", "comandine(stato, reparto_id)"),
        ("idx_comandine_timestamps", "comandine(timestamp_inserimento)"),
        ("idx_pagamenti_comanda", "pagamenti(comanda_id)"),
        ("idx_pagamenti_data", "pagamenti(date(timestamp_pagamento))"),
        ("idx_notifiche_destinatario", "notifiche(destinatario_id, letto)"),
        ("idx_tavoli_sala_stato", "tavoli(sala_id, stato)"),
    ]
    
    for nome, definizione in indici:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {nome} ON {definizione}")
        except Exception as e:
            logger.warning(f"Errore creazione indice {nome}: {e}")
    
    logger.info("Indici creati con successo")

# ============================================================================
# DATI INIZIALI
# ============================================================================
def populate_initial_data(cursor):
    """Popola il database con dati di esempio"""
    
    logger.info("Popolamento dati iniziali...")
    
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
    
    logger.info("Dati iniziali caricati con successo")

# ============================================================================
# INIZIALIZZAZIONE DATABASE
# ============================================================================
def init_db(force=False):
    """Inizializza il database completo"""
    
    print("=" * 60)
    print("🔄 INIZIALIZZAZIONE DATABASE")
    print("=" * 60)
    print(f"📦 Database path: {DB_PATH}")
    
    try:
        # Assicurati che la directory esista
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
        
        with get_db_connection(init_mode=True) as conn:
            cursor = conn.cursor()
            
            if force:
                cursor.execute("DROP TABLE IF EXISTS log_stampe")
                cursor.execute("DROP TABLE IF EXISTS stampanti")
                cursor.execute("DROP TABLE IF EXISTS notifiche")
                cursor.execute("DROP TABLE IF EXISTS pagamenti")
                cursor.execute("DROP TABLE IF EXISTS comandine")
                cursor.execute("DROP TABLE IF EXISTS comande")
                cursor.execute("DROP TABLE IF EXISTS variazioni")
                cursor.execute("DROP TABLE IF EXISTS piatti")
                cursor.execute("DROP TABLE IF EXISTS categorie")
                cursor.execute("DROP TABLE IF EXISTS reparti")
                cursor.execute("DROP TABLE IF EXISTS tavoli")
                cursor.execute("DROP TABLE IF EXISTS sale")
                cursor.execute("DROP TABLE IF EXISTS utenti")
                cursor.execute("DROP TABLE IF EXISTS brand")
                cursor.execute("DROP TABLE IF EXISTS giornale_cassa")
                cursor.execute("DROP TABLE IF EXISTS preordini")
                cursor.execute("DROP TABLE IF EXISTS preordini_dettaglio")
                cursor.execute("DROP TABLE IF EXISTS clienti")
            
            create_tables(cursor)
            create_indexes(cursor)
            populate_initial_data(cursor)
        
        print("✅ Database inizializzato con successo!")
        
        # Backup automatico solo in locale
        if not os.environ.get('STREAMLIT_CLOUD'):
            backup_automatico()
        
        return True
        
    except Exception as e:
        print(f"❌ Errore inizializzazione: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# BACKUP E MANUTENZIONE
# ============================================================================
def backup_automatico():
    """Crea backup automatico del database (solo in locale)"""
    try:
        backup_dir = "backup"
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"ristorante_backup_{timestamp}.db")
        
        shutil.copy2(DB_PATH, backup_path)
        print(f"✅ Backup creato: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ Errore backup: {e}")
        return None

# ============================================================================
# SERVIZIO STAMPANTI (solo parte essenziale)
# ============================================================================
import socket
import threading
import queue
import time

class StampanteService:
    """Gestione stampanti termiche per reparti"""
    
    _print_queue = queue.Queue()
    _print_thread = None
    _running = False
    
    @classmethod
    def start_print_worker(cls):
        """Avvia il thread per la stampa asincrona"""
        if cls._print_thread is None or not cls._print_thread.is_alive():
            cls._running = True
            cls._print_thread = threading.Thread(target=cls._print_worker, daemon=True)
            cls._print_thread.start()
            print("🖨️ Servizio stampanti avviato")
    
    @classmethod
    def stop_print_worker(cls):
        """Ferma il thread di stampa"""
        cls._running = False
        if cls._print_thread:
            cls._print_thread.join(timeout=2)
    
    @classmethod
    def _print_worker(cls):
        """Worker per stampa asincrona"""
        while cls._running:
            try:
                job = cls._print_queue.get(timeout=1)
                cls._execute_print(job)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Errore nel worker stampa: {e}")
    
    @classmethod
    def _execute_print(cls, job):
        """Esegue effettivamente la stampa"""
        try:
            printer_config = job['printer']
            content = job['content']
            tipo = job['tipo']
            comanda_id = job.get('comanda_id')
            reparto_id = job.get('reparto_id')
            
            # Stampa simulata
            print(f"\n🖨️ SIMULAZIONE STAMPA - {tipo}")
            print(content)
            print("-" * 40)
            
            # Log successo
            try:
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO log_stampe (tipo, reparto_id, comanda_id, contenuto, esito)
                    VALUES (?, ?, ?, ?, ?)
                """, (tipo, reparto_id, comanda_id, content[:100], 'SIMULATO'))
                conn.commit()
                conn.close()
            except:
                pass
            
            print(f"✅ Stampato {tipo} per comanda {comanda_id} (SIMULATO)")
            
        except Exception as e:
            print(f"❌ Errore stampa: {e}")
    
    @staticmethod
    def get_stampanti_per_reparto(reparto_id):
        """Recupera le stampanti attive per un reparto"""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM stampanti 
                WHERE reparto_id = ? AND attivo = 1
                ORDER BY id
            """, (reparto_id,))
            result = cursor.fetchall()
            conn.close()
            return result
        except:
            return []
    
    @staticmethod
    def stampa_comanda(comanda_id, reparto_id, piatti):
        """Prepara e accoda la stampa di una comanda"""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT c.*, t.numero as tavolo_numero, s.nome as sala_nome
                FROM comande c
                JOIN tavoli t ON c.tavolo_id = t.id
                JOIN sale s ON t.sala_id = s.id
                WHERE c.id = ?
            """, (comanda_id,))
            comanda = cursor.fetchone()
            conn.close()
            
            if not comanda:
                return False
            
            content = []
            content.append("=" * 42)
            content.append(f"  TAVOLO: {comanda['tavolo_numero']} - {comanda['sala_nome']}")
            content.append(f"  DATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            content.append("-" * 42)
            content.append(" QTA DESCRIZIONE")
            content.append("-" * 42)
            
            for p in piatti:
                nome = p['piatto_nome'][:28] if len(p['piatto_nome']) > 28 else p['piatto_nome']
                content.append(f" {p['qty']:2}  {nome}")
                if p.get('note'):
                    content.append(f"     -> {p['note'][:30]}")
            
            content.append("-" * 42)
            content.append("")
            content.append("\n" * 3)
            
            content_str = "\n".join(content)
            
            job = {
                'printer': {'nome': 'Stampante Virtuale'},
                'content': content_str,
                'tipo': 'COMANDA',
                'comanda_id': comanda_id,
                'reparto_id': reparto_id
            }
            cls._print_queue.put(job)
            
            return True
        except Exception as e:
            print(f"Errore stampa_comanda: {e}")
            return False

# Avvia il worker all'avvio
StampanteService.start_print_worker()

# ============================================================================
# MAIN
# ============================================================================
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--force":
            init_db(force=True)
        elif sys.argv[1] == "--backup":
            backup_automatico()
        elif sys.argv[1] == "--help":
            print("""
Utilizzo:
  python db.py              Inizializzazione normale
  python db.py --force      Re-inizializza tutto (perde dati)
  python db.py --backup     Crea backup
  python db.py --help       Mostra questo help
            """)
        else:
            print("Comando non riconosciuto. Usa --help per aiuto.")
    else:
        init_db()