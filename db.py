"""
DATABASE MANAGER PROFESSIONALE - PALAZZO FIORINI
Versione 2.1 - Corretto e Ottimizzato
"""

import sqlite3
import os
import hashlib
import platform
import shutil
import tempfile
from datetime import datetime, date
from contextlib import contextmanager
import logging
from typing import Optional, Dict, List, Any, Tuple

# ============================================================================
# CONFIGURAZIONE PERCORSO DATABASE
# ============================================================================
def get_database_path():
    """Restituisce il percorso corretto per il database in base all'ambiente"""
    if os.environ.get('STREAMLIT_CLOUD'):
        return os.path.join(tempfile.gettempdir(), "ristorante.db")
    else:
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
        
        conn = sqlite3.connect(
            DB_PATH,
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
# FUNZIONE HELPER PER QUERY RAPIDE
# ============================================================================
def esegui_query(query: str, params: tuple = (), 
                 fetchone: bool = False, fetchall: bool = False, 
                 commit: bool = False) -> Any:
    """Esegue query SQL in modo sicuro"""
    
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
            indirizzo TEXT,
            telefono TEXT,
            email TEXT,
            partita_iva TEXT,
            logo_data BLOB,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
            ordine INTEGER DEFAULT 10,       
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
    
    # 12. CONFIGURAZIONE APP
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            chiave TEXT PRIMARY KEY,
            valore TEXT,
            tipo TEXT DEFAULT 'text',
            descrizione TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 13. PRE-ORDINI CLIENTI
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
            variazioni TEXT DEFAULT '[]',
            note TEXT,
            FOREIGN KEY (preordine_id) REFERENCES preordini(id) ON DELETE CASCADE,
            FOREIGN KEY (piatto_id) REFERENCES piatti(id)
        )
    """)
    
    # 14. CLIENTI
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
        ("idx_preordini_tavolo", "preordini(tavolo_id, stato)"),
        ("idx_preordini_data", "preordini(timestamp_creazione)"),
        ("idx_preordini_dettaglio", "preordini_dettaglio(preordine_id)"),
        ("idx_piatti_categoria", "piatti(categoria_id, disponibile)"),
        ("idx_config_chiave", "config(chiave)"),
    ]
    
    for nome, definizione in indici:
        try:
            cursor.execute(f"CREATE INDEX IF NOT EXISTS {nome} ON {definizione}")
        except Exception as e:
            logger.warning(f"Errore creazione indice {nome}: {e}")
    
    logger.info("Indici creati con successo")

# ============================================================================
# DATI INIZIALI - VERSIONE SUPER ROBUSTA
# ============================================================================
def populate_initial_data(cursor):
    """Popola il database con dati di esempio - ORDINE FORZATO"""
    
    logger.info("=" * 60)
    logger.info("VERIFICA DATI INIZIALI")
    logger.info("=" * 60)
    
    # ========================================================================
    # 1. REPARTI (ASSOLUTAMENTE PRIMA DI TUTTO)
    # ========================================================================
    logger.info("📁 STEP 1: Verifica REPARTI")
    cursor.execute("SELECT COUNT(*) FROM reparti")
    count = cursor.fetchone()[0]
    logger.info(f"   Reparti trovati: {count}")
    
    if count == 0:
        logger.info("   Creazione reparti di default...")
        reparti = [
            (1, 'CUCINA', '👨‍🍳', '#e74c3c', 1),
            (2, 'BAR', '🍸', '#3498db', 2),
            (3, 'PASTICCERIA', '🍰', '#9b59b6', 3),
            (4, 'PIZZERIA', '🍕', '#e67e22', 4),
        ]
        for id, nome, icona, colore, ordine in reparti:
            try:
                cursor.execute("""
                    INSERT INTO reparti (id, nome, icona, colore, ordine, attivo)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (id, nome, icona, colore, ordine))
                logger.info(f"      ✅ {nome}")
            except Exception as e:
                logger.error(f"      ❌ Errore: {e}")
    else:
        logger.info("   ✅ Reparti già esistenti")
        # Mostra reparti esistenti
        cursor.execute("SELECT id, nome FROM reparti ORDER BY id")
        for r in cursor.fetchall():
            logger.info(f"      📋 ID {r['id']}: {r['nome']}")
    
    # ========================================================================
    # 2. CATEGORIE (DOPO REPARTI)
    # ========================================================================
    logger.info("📁 STEP 2: Verifica CATEGORIE")
    cursor.execute("SELECT COUNT(*) FROM categorie")
    count = cursor.fetchone()[0]
    logger.info(f"   Categorie trovate: {count}")
    
    if count == 0:
        logger.info("   Creazione categorie di default...")
        
        # Verifica che i reparti esistano
        cursor.execute("SELECT id FROM reparti WHERE id IN (1,2,3,4)")
        reparti_esistenti = [r['id'] for r in cursor.fetchall()]
        logger.info(f"   Reparti disponibili: {reparti_esistenti}")
        
        if len(reparti_esistenti) < 4:
            logger.error("   ❌ Reparti mancanti! Ricreazione forzata...")
            # Ricrea reparti
            for id, nome, icona, colore, ordine in [
                (1, 'CUCINA', '👨‍🍳', '#e74c3c', 1),
                (2, 'BAR', '🍸', '#3498db', 2),
                (3, 'PASTICCERIA', '🍰', '#9b59b6', 3),
                (4, 'PIZZERIA', '🍕', '#e67e22', 4),
            ]:
                cursor.execute("""
                    INSERT OR REPLACE INTO reparti (id, nome, icona, colore, ordine, attivo)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (id, nome, icona, colore, ordine))
            logger.info("   ✅ Reparti ricreati")
        
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
            try:
                cursor.execute("""
                    INSERT INTO categorie (id, nome, reparto_id, icona, ordine, attiva)
                    VALUES (?, ?, ?, ?, ?, 1)
                """, (id, nome, reparto_id, icona, ordine))
                logger.info(f"      ✅ {nome} (reparto_id: {reparto_id})")
            except Exception as e:
                logger.error(f"      ❌ Errore {nome}: {e}")
    else:
        logger.info("   ✅ Categorie già esistenti")
        cursor.execute("SELECT id, nome, reparto_id FROM categorie ORDER BY id")
        for c in cursor.fetchall():
            logger.info(f"      📋 ID {c['id']}: {c['nome']} (reparto: {c['reparto_id']})")
    
    # ========================================================================
    # 3. PIATTI (DOPO CATEGORIE)
    # ========================================================================
    logger.info("🍽️ STEP 3: Verifica PIATTI")
    cursor.execute("SELECT COUNT(*) FROM piatti")
    count = cursor.fetchone()[0]
    logger.info(f"   Piatti trovati: {count}")
    
    if count == 0:
        logger.info("   Creazione piatti di default...")
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
            try:
                cursor.execute("""
                    INSERT INTO piatti (id, nome, categoria_id, prezzo, disponibile)
                    VALUES (?, ?, ?, ?, ?)
                """, (id, nome, cat_id, prezzo, disp))
                logger.info(f"      ✅ {nome}")
            except Exception as e:
                logger.error(f"      ❌ Errore {nome}: {e}")
    else:
        logger.info(f"   ✅ Piatti già esistenti: {count}")
    
    # ========================================================================
    # 4. ALTRI DATI (BRAND, UTENTI, ecc.)
    # ========================================================================
    logger.info("🏢 STEP 4: Verifica altri dati")
    
    # Brand
    cursor.execute("SELECT COUNT(*) FROM brand")
    if cursor.fetchone()[0] == 0:
        cursor.execute("""
            INSERT INTO brand (id, nome, partita_iva) 
            VALUES (1, 'RISTORAPP', '01234567890')
        """)
        logger.info("   ✅ Brand default creato")
    
    # Utenti
    cursor.execute("SELECT COUNT(*) FROM utenti")
    if cursor.fetchone()[0] == 0:
        utenti = [
            (1, 'admin', hash_password('admin123'), 'Admin', 'Super', 'SUPERADMIN'),
            (2, 'cameriere', hash_password('123'), 'Mario', 'Rossi', 'CAMERIERE'),
            (3, 'cucina', hash_password('123'), 'Luigi', 'Verdi', 'CUCINA'),
            (4, 'bar', hash_password('123'), 'Giovanni', 'Bianchi', 'BAR'),
            (5, 'cassa', hash_password('123'), 'Anna', 'Neri', 'CASSA'),
        ]
        for id, username, pwd_hash, nome, cognome, ruolo in utenti:
            cursor.execute("""
                INSERT INTO utenti (id, username, password_hash, nome, cognome, ruolo, brand_id)
                VALUES (?, ?, ?, ?, ?, ?, 1)
            """, (id, username, pwd_hash, nome, cognome, ruolo))
        logger.info(f"   ✅ {len(utenti)} utenti creati")
    
    # Variazioni
    cursor.execute("SELECT COUNT(*) FROM variazioni")
    if cursor.fetchone()[0] == 0:
        variazioni = [
            (1, 'Mozzarella extra', 1.50, 4, 1),
            (2, 'Funghi', 1.00, 4, 2),
            (3, 'Prosciutto', 2.00, 4, 3),
            (4, 'Pomodoro extra', 0.50, 4, 4),
            (5, 'Glutine', 0.00, 1, 5),
            (6, 'Lattosio', 0.00, 1, 6),
        ]
        for id, nome, prezzo, reparto_id, ordine in variazioni:
            cursor.execute("""
                INSERT INTO variazioni (id, nome, prezzo, reparto_id, ordine)
                VALUES (?, ?, ?, ?, ?)
            """, (id, nome, prezzo, reparto_id, ordine))
        logger.info(f"   ✅ {len(variazioni)} variazioni create")
    
    logger.info("=" * 60)
    logger.info("✅ VERIFICA DATI INIZIALI COMPLETATA")
    logger.info("=" * 60)

# ============================================================================
# SERVICE LAYER
# ============================================================================

class TavoloService:
    """Gestione tavoli e sale"""
    
    @staticmethod
    def get_tutti_tavoli():
        """Restituisce tutti i tavoli con info sale"""
        return esegui_query("""
            SELECT t.*, s.nome as sala_nome, s.colore as sala_colore
            FROM tavoli t
            JOIN sale s ON t.sala_id = s.id
            ORDER BY s.ordine, t.numero
        """, fetchall=True)
    
    @staticmethod
    def get_tavoli_per_sala(sala_id):
        """Restituisce tavoli di una sala"""
        return esegui_query("""
            SELECT * FROM tavoli 
            WHERE sala_id = ? 
            ORDER BY numero
        """, (sala_id,), fetchall=True)
    
    @staticmethod
    def occupa_tavolo(tavolo_id, cameriere_id):
        """Occupare un tavolo (crea comanda)"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO comande (tavolo_id, cameriere_id, stato)
                VALUES (?, ?, 'ATTIVA')
            """, (tavolo_id, cameriere_id))
            comanda_id = cursor.lastrowid
            
            cursor.execute("""
                UPDATE tavoli SET stato = 'OCCUPATO' WHERE id = ?
            """, (tavolo_id,))
            
            return comanda_id
    
    @staticmethod
    def libera_tavolo(tavolo_id):
        """Libera un tavolo"""
        esegui_query("""
            UPDATE tavoli 
            SET stato = 'LIBERO', richiesta_conto = 0
            WHERE id = ?
        """, (tavolo_id,), commit=True)


class OrdineService:
    """Gestione ordini e comande"""
    
    @staticmethod
    def aggiungi_al_carrello(comanda_id, piatto_id, qty, variazioni=None, note=""):
        """Aggiunge piatto alla comanda"""
        piatto = esegui_query("SELECT * FROM piatti WHERE id = ?", (piatto_id,), fetchone=True)
        if not piatto:
            return False, "Piatto non trovato"
        
        # Determina reparto dalla categoria
        reparto = esegui_query("""
            SELECT reparto_id FROM categorie WHERE id = ?
        """, (piatto['categoria_id'],), fetchone=True)
        
        esegui_query("""
            INSERT INTO comandine 
            (comanda_id, piatto_id, piatto_nome, qty, prezzo_unitario, 
             note, stato, reparto_id)
            VALUES (?, ?, ?, ?, ?, ?, 'NUOVO', ?)
        """, (comanda_id, piatto_id, piatto['nome'], qty, piatto['prezzo'], 
              note or "", reparto['reparto_id']), commit=True)
        
        return True, "Piatto aggiunto"
    
    @staticmethod
    def get_comande_attive(tavolo_id):
        """Recupera comanda attiva per tavolo"""
        return esegui_query("""
            SELECT * FROM comande 
            WHERE tavolo_id = ? AND stato = 'ATTIVA'
            LIMIT 1
        """, (tavolo_id,), fetchone=True)
    
    @staticmethod
    def get_piatti_comanda(comanda_id):
        """Recupera tutti i piatti di una comanda"""
        return esegui_query("""
            SELECT c.*, p.nome as piatto_nome, r.icona as reparto_icona
            FROM comandine c
            JOIN piatti p ON c.piatto_id = p.id
            JOIN reparti r ON c.reparto_id = r.id
            WHERE c.comanda_id = ?
            ORDER BY c.timestamp_inserimento
        """, (comanda_id,), fetchall=True)
    
    @staticmethod
    def aggiorna_stato(commandina_id, nuovo_stato, operatore_id=None):
        """Aggiorna stato di una commandina"""
        timestamp_field = {
            'IN_CORSO': 'timestamp_inizio',
            'PRONTO': 'timestamp_pronto',
            'SERVITO': 'timestamp_servito'
        }.get(nuovo_stato, '')
        
        query = f"""
            UPDATE comandine 
            SET stato = ?, {timestamp_field} = CURRENT_TIMESTAMP
            WHERE id = ?
        """ if timestamp_field else """
            UPDATE comandine SET stato = ? WHERE id = ?
        """
        
        esegui_query(query, (nuovo_stato, commandina_id), commit=True)
        
        # Notifica se diventa PRONTO
        if nuovo_stato == 'PRONTO':
            cmd = esegui_query("""
                SELECT c.tavolo_id, t.numero, cmd.piatto_nome
                FROM comandine cmd
                JOIN comande c ON cmd.comanda_id = c.id
                JOIN tavoli t ON c.tavolo_id = t.id
                WHERE cmd.id = ?
            """, (commandina_id,), fetchone=True)
            
            if cmd:
                NotificaService.invia(
                    titolo=f"Tavolo {cmd['numero']}",
                    messaggio=f"{cmd['piatto_nome']} è pronto!",
                    destinatario_ruolo='CAMERIERE'
                )
    
    @staticmethod
    def get_comande_per_reparto(reparto_id, stato=None):
        """Recupera comande per reparto"""
        query = """
            SELECT c.*, t.numero as tavolo_numero, s.nome as sala_nome
            FROM comandine c
            JOIN comande co ON c.comanda_id = co.id
            JOIN tavoli t ON co.tavolo_id = t.id
            JOIN sale s ON t.sala_id = s.id
            WHERE c.reparto_id = ?
        """
        params = [reparto_id]
        
        if stato and stato != 'TUTTI':
            query += " AND c.stato = ?"
            params.append(stato)
        
        query += " ORDER BY c.timestamp_inserimento"
        
        return esegui_query(query, tuple(params), fetchall=True)


class PagamentoService:
    """Gestione pagamenti e conti"""
    
    @staticmethod
    def richiedi_conto(tavolo_id):
        """Il cameriere richiede il conto"""
        comanda = esegui_query("""
            SELECT id FROM comande 
            WHERE tavolo_id = ? AND stato = 'ATTIVA'
        """, (tavolo_id,), fetchone=True)
        
        if not comanda:
            return False, "Nessuna comanda attiva"
        
        # Verifica che tutti i piatti siano serviti
        non_serviti = esegui_query("""
            SELECT COUNT(*) as cnt FROM comandine
            WHERE comanda_id = ? AND stato != 'SERVITO'
        """, (comanda['id'],), fetchone=True)
        
        if non_serviti['cnt'] > 0:
            return False, f"Ancora {non_serviti['cnt']} piatti da servire"
        
        esegui_query("""
            UPDATE comande SET richiesta_conto = 1,
                timestamp_richiesta_conto = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (comanda['id'],), commit=True)
        
        esegui_query("""
            UPDATE tavoli SET richiesta_conto = 1 WHERE id = ?
        """, (tavolo_id,), commit=True)
        
        # Notifica la cassa
        NotificaService.invia(
            titolo=f"Tavolo {tavolo_id}",
            messaggio="Richiesto conto",
            destinatario_ruolo='CASSA'
        )
        
        return True, "Conto richiesto"
    
    @staticmethod
    def get_conti_richiesti():
        """Lista tavoli che hanno richiesto il conto"""
        return esegui_query("""
            SELECT 
                c.id as comanda_id,
                t.id as tavolo_id,
                t.numero as tavolo_numero,
                s.nome as sala_nome,
                SUM(cmd.qty * cmd.prezzo_unitario) as totale,
                COUNT(cmd.id) as piatti_totali,
                c.timestamp_richiesta_conto
            FROM comande c
            JOIN tavoli t ON c.tavolo_id = t.id
            JOIN sale s ON t.sala_id = s.id
            LEFT JOIN comandine cmd ON c.id = cmd.comanda_id
            WHERE c.richiesta_conto = 1 AND c.stato = 'ATTIVA'
            GROUP BY c.id
            ORDER BY c.timestamp_richiesta_conto
        """, fetchall=True)
    
    @staticmethod
    def registra_pagamento(comanda_id, metodo, contanti=0, carta=0, 
                          bancomat=0, altri=0, operatore_id=None):
        """Registra pagamento e libera tavolo"""
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Calcola totale
            totale = cursor.execute("""
                SELECT SUM(qty * prezzo_unitario) as tot
                FROM comandine WHERE comanda_id = ?
            """, (comanda_id,)).fetchone()['tot'] or 0
            
            importo_totale = contanti + carta + bancomat + altri
            resto = max(0, importo_totale - totale)
            
            # Registra pagamento
            cursor.execute("""
                INSERT INTO pagamenti 
                (comanda_id, totale, contanti, carta, bancomat, altri, 
                 resto, metodo, operatore_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (comanda_id, totale, contanti, carta, bancomat, altri, 
                  resto, metodo, operatore_id))
            
            # Chiudi comanda
            cursor.execute("""
                UPDATE comande 
                SET stato = 'CHIUSA', totale = ?, metodo_pagamento = ?,
                    importo_pagato = ?, resto = ?, timestamp_chiusura = CURRENT_TIMESTAMP,
                    richiesta_conto = 0
                WHERE id = ?
            """, (totale, metodo, importo_totale, resto, comanda_id))
            
            # Libera tavolo
            cursor.execute("""
                UPDATE tavoli 
                SET stato = 'LIBERO', richiesta_conto = 0
                WHERE id = (SELECT tavolo_id FROM comande WHERE id = ?)
            """, (comanda_id,))
            
            return True


class NotificaService:
    """Gestione notifiche in tempo reale"""
    
    @staticmethod
    def invia(titolo, messaggio, destinatario_id=None, destinatario_ruolo=None):
        """Invia una notifica"""
        esegui_query("""
            INSERT INTO notifiche (tipo, titolo, messaggio, destinatario_id, destinatario_ruolo)
            VALUES ('INFO', ?, ?, ?, ?)
        """, (titolo, messaggio, destinatario_id, destinatario_ruolo), commit=True)
    
    @staticmethod
    def get_non_lette(utente_id, ruolo):
        """Recupera notifiche non lette"""
        return esegui_query("""
            SELECT * FROM notifiche 
            WHERE letto = 0 AND (destinatario_id = ? OR destinatario_ruolo = ?)
            ORDER BY timestamp_creazione DESC
        """, (utente_id, ruolo), fetchall=True)
    
    @staticmethod
    def segna_letta(notifica_id):
        """Segna notifica come letta"""
        esegui_query("""
            UPDATE notifiche SET letto = 1, timestamp_lettura = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (notifica_id,), commit=True)


class ReportService:
    """Statistiche e report"""
    
    @staticmethod
    def incasso_oggi():
        """Incasso giornaliero"""
        return esegui_query("""
            SELECT COALESCE(SUM(totale), 0) as totale
            FROM pagamenti
            WHERE date(timestamp_pagamento) = date('now')
        """, fetchone=True)['totale']
    
    @staticmethod
    def ordini_in_corso():
        """Numero ordini in preparazione"""
        return esegui_query("""
            SELECT COUNT(*) as cnt FROM comandine
            WHERE stato IN ('NUOVO', 'IN_CORSO')
        """, fetchone=True)['cnt']
    
    @staticmethod
    def tavoli_occupati():
        """Numero tavoli occupati"""
        return esegui_query("""
            SELECT COUNT(*) as cnt FROM tavoli
            WHERE stato = 'OCCUPATO'
        """, fetchone=True)['cnt']
    
    @staticmethod
    def piatti_piu_venduti(limite=10):
        """Top piatti più venduti"""
        return esegui_query("""
            SELECT piatto_nome, SUM(qty) as totale
            FROM comandine
            WHERE date(timestamp_inserimento) >= date('now', '-30 days')
            GROUP BY piatto_nome
            ORDER BY totale DESC
            LIMIT ?
        """, (limite,), fetchall=True)
    
    @staticmethod
    def incassi_per_metodo_oggi():
        """Incassi suddivisi per metodo di pagamento per oggi"""
        return esegui_query("""
            SELECT 
                metodo,
                COUNT(*) as numero_transazioni,
                SUM(totale) as totale
            FROM pagamenti
            WHERE date(timestamp_pagamento) = date('now')
            GROUP BY metodo
            ORDER BY metodo
        """, fetchall=True)
    
    @staticmethod
    def statistiche_complete_oggi():
        """Statistiche complete della giornata"""
        stats = esegui_query("""
            SELECT 
                COUNT(*) as totale_scontrini,
                SUM(totale) as incasso_totale,
                AVG(totale) as media_scontrino
            FROM pagamenti
            WHERE date(timestamp_pagamento) = date('now')
        """, fetchone=True)
        
        if not stats:
            return {
                'totale_scontrini': 0,
                'incasso_totale': 0,
                'media_scontrino': 0
            }
        return stats

# ============================================================================
# SERVIZIO STAMPANTI
# ============================================================================
import socket
import threading
import queue
import time

# Variabili globali per il thread di stampa
_print_queue = queue.Queue()
_print_thread = None
_print_running = False

def start_print_worker():
    """Avvia il thread per la stampa asincrona"""
    global _print_thread, _print_running
    if _print_thread is None or not _print_thread.is_alive():
        _print_running = True
        _print_thread = threading.Thread(target=_print_worker, daemon=True)
        _print_thread.start()
        print("🖨️ Servizio stampanti avviato")

def stop_print_worker():
    """Ferma il thread di stampa"""
    global _print_running
    _print_running = False
    if _print_thread:
        _print_thread.join(timeout=2)

def _print_worker():
    """Worker per stampa asincrona"""
    global _print_running
    while _print_running:
        try:
            job = _print_queue.get(timeout=1)
            _execute_print(job)
        except queue.Empty:
            continue
        except Exception as e:
            print(f"Errore nel worker stampa: {e}")

def _execute_print(job):
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

class StampanteService:
    """Gestione stampanti termiche per reparti"""
    
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
        global _print_queue
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
            _print_queue.put(job)
            
            return True
        except Exception as e:
            print(f"Errore stampa_comanda: {e}")
            return False

# Avvia il worker all'avvio
start_print_worker()

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
# CONFIGURAZIONE APP - GESTIONE URL PUBBLICO
# ============================================================================
def salva_url_pubblico(url):
    """Salva l'URL pubblico nel database"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Crea tabella config se non esiste (già fatta, ma per sicurezza)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                chiave TEXT PRIMARY KEY,
                valore TEXT,
                tipo TEXT DEFAULT 'text',
                descrizione TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Inserisci o aggiorna l'URL
        cursor.execute("""
            INSERT OR REPLACE INTO config (chiave, valore, tipo, updated_at)
            VALUES ('public_url', ?, 'text', CURRENT_TIMESTAMP)
        """, (url,))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Errore salvataggio URL: {e}")
        return False
    finally:
        if conn:
            conn.close()

def carica_url_pubblico():
    """Carica l'URL pubblico dal database"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Crea tabella config se non esiste (per sicurezza)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                chiave TEXT PRIMARY KEY,
                valore TEXT,
                tipo TEXT DEFAULT 'text',
                descrizione TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        
        # Recupera l'URL
        cursor.execute("SELECT valore FROM config WHERE chiave = 'public_url'")
        risultato = cursor.fetchone()
        
        if risultato:
            return risultato[0]
        else:
            return "http://localhost:8501"
    except Exception as e:
        print(f"❌ Errore caricamento URL: {e}")
        return "http://localhost:8501"
    finally:
        if conn:
            conn.close()

# ============================================================================
# FUNZIONE DI VERIFICA DATABASE
# ============================================================================
def verifica_database():
    """Verifica che tutte le tabelle e i dati essenziali esistano"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Lista tabelle richieste
        tabelle_richieste = [
            'brand', 'utenti', 'sale', 'tavoli', 'reparti',
            'categorie', 'piatti', 'variazioni', 'comande',
            'comandine', 'pagamenti', 'notifiche', 'preordini',
            'preordini_dettaglio', 'config'
        ]
        
        mancanti = []
        for tabella in tabelle_richieste:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tabella}'")
            if not cursor.fetchone():
                mancanti.append(tabella)
        
        conn.close()
        
        if mancanti:
            print(f"⚠️ Tabelle mancanti: {', '.join(mancanti)}")
            return False
        else:
            print("✅ Database verificato: tutte le tabelle presenti")
            return True
    except Exception as e:
        print(f"❌ Errore verifica database: {e}")
        return False

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
        os.makedirs(os.path.dirname(os.path.abspath(DB_PATH)) if os.path.dirname(DB_PATH) else '.', exist_ok=True)
        
        with get_db_connection(init_mode=True) as conn:
            cursor = conn.cursor()
            
            if force:
                print("⚠️ Forzatura: eliminazione tabelle esistenti...")
                
                # Disabilita temporaneamente i foreign keys
                cursor.execute("PRAGMA foreign_keys = OFF")
                
                # Lista tabelle in ordine inverso (prima quelle con dipendenze)
                tabelle = [
                    'log_stampe',
                    'stampanti',
                    'notifiche',
                    'pagamenti',
                    'comandine',
                    'comande',
                    'preordini_dettaglio',
                    'preordini',
                    'variazioni',
                    'piatti',
                    'categorie',
                    'tavoli',
                    'sale',
                    'reparti',
                    'utenti',
                    'giornale_cassa',
                    'clienti',
                    'config',
                    'brand'
                ]
                
                for tabella in tabelle:
                    try:
                        cursor.execute(f"DROP TABLE IF EXISTS {tabella}")
                        print(f"   ✅ Tabella {tabella} eliminata")
                    except Exception as e:
                        print(f"   ⚠️ Tabella {tabella} non eliminata: {e}")
                
                # Riabilita foreign keys
                cursor.execute("PRAGMA foreign_keys = ON")
                print("✅ Eliminazione tabelle completata")
            
            # Crea le tabelle
            create_tables(cursor)
            print("✅ Tabelle create")
            
            # Crea indici
            create_indexes(cursor)
            print("✅ Indici creati")
            
            # Popola dati iniziali
            populate_initial_data(cursor)
            print("✅ Dati iniziali caricati")
        
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
# MAIN
# ============================================================================
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--force":
            init_db(force=True)
        elif sys.argv[1] == "--backup":
            backup_automatico()
        elif sys.argv[1] == "--verify":
            verifica_database()
        elif sys.argv[1] == "--help":
            print("""
Utilizzo:
  python db.py              Inizializzazione normale
  python db.py --force      Re-inizializza tutto (perde dati)
  python db.py --backup     Crea backup
  python db.py --verify     Verifica integrità database
  python db.py --help       Mostra questo help
            """)
        else:
            print("Comando non riconosciuto. Usa --help per aiuto.")
    else:
        init_db()