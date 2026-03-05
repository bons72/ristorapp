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
    
    # ============================================================================
    # STORICO E REPORTISTICA (NUOVE TABELLE - DA 9 A 11)
    # ============================================================================
    
    # 9. STORICO COMANDE PER TAVOLO
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS storico_comande (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            comanda_id INTEGER NOT NULL,
            tavolo_id INTEGER NOT NULL,
            tavolo_numero INTEGER NOT NULL,
            sala_nome TEXT NOT NULL,
            data_apertura TIMESTAMP NOT NULL,
            data_chiusura TIMESTAMP,
            cameriere_nome TEXT,
            totale_comanda REAL DEFAULT 0,
            numero_piatti INTEGER DEFAULT 0,
            stato TEXT DEFAULT 'COMPLETATA',
            FOREIGN KEY (comanda_id) REFERENCES comande(id),
            FOREIGN KEY (tavolo_id) REFERENCES tavoli(id)
        )
    """)
    
    # 10. STORICO REPARTI (produttività)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS storico_reparti (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reparto_id INTEGER NOT NULL,
            reparto_nome TEXT NOT NULL,
            data DATE NOT NULL,
            ora TIME,
            piatti_preparati INTEGER DEFAULT 0,
            tempo_medio_preparazione INTEGER DEFAULT 0,
            picco_ordini INTEGER DEFAULT 0,
            FOREIGN KEY (reparto_id) REFERENCES reparti(id)
        )
    """)
    
    # 11. STORICO GIORNALIERO CASSA
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS storico_cassa (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            data DATE NOT NULL UNIQUE,
            incasso_contanti REAL DEFAULT 0,
            incasso_carta REAL DEFAULT 0,
            incasso_bancomat REAL DEFAULT 0,
            incasso_altri REAL DEFAULT 0,
            totale_incasso REAL DEFAULT 0,
            numero_scontrini INTEGER DEFAULT 0,
            scontrino_medio REAL DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 12. GIORNALE DI CASSA (era 9, ora 12)
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
    
    # 13. CONFIGURAZIONE STAMPANTI (era 10, ora 13)
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
    
    # 14. LOG STAMPE (era 11, ora 14)
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
    
    # 15. CONFIGURAZIONE APP (era 12, ora 15)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            chiave TEXT PRIMARY KEY,
            valore TEXT,
            tipo TEXT DEFAULT 'text',
            descrizione TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 16. PRE-ORDINI CLIENTI (era 13, ora 16)
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
    
    # 17. CLIENTI (era 14, ora 17)
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
# DATI INIZIALI - VERSIONE MINIMALE E ROBUSTA
# ============================================================================
def populate_initial_data(cursor, conn):
    """Popola il database con dati essenziali - VERSIONE MINIMALE"""
    
    logger.info("=" * 60)
    logger.info("POPOLAMENTO DATI INIZIALI (VERSIONE MINIMALE)")
    logger.info("=" * 60)
    
    try:
        # ========================================================================
        # 1. REPARTI
        # ========================================================================
        logger.info("📁 Creazione REPARTI...")
        cursor.execute("DELETE FROM reparti")
        reparti = [
            (1, 'CUCINA', '👨‍🍳', '#e74c3c', 1),
            (2, 'BAR', '🍸', '#3498db', 2),
            (3, 'PASTICCERIA', '🍰', '#9b59b6', 3),
            (4, 'PIZZERIA', '🍕', '#e67e22', 4),
        ]
        for id, nome, icona, colore, ordine in reparti:
            cursor.execute("""
                INSERT OR REPLACE INTO reparti (id, nome, icona, colore, ordine, attivo)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (id, nome, icona, colore, ordine))
            logger.info(f"   ✅ Reparto {id}: {nome}")
        conn.commit()
        logger.info("   ✅ Commit reparti OK")
        
        # ========================================================================
        # 2. CATEGORIE (minime)
        # ========================================================================
        logger.info("📁 Creazione CATEGORIE minime...")
        cursor.execute("DELETE FROM categorie")
        categorie = [
            (1, 'ANTIPASTI', 1, '🥗', 1),
            (2, 'PRIMI', 1, '🍝', 2),
            (3, 'SECONDI', 1, '🥩', 3),
        ]
        for id, nome, reparto_id, icona, ordine in categorie:
            cursor.execute("""
                INSERT OR REPLACE INTO categorie (id, nome, reparto_id, icona, ordine, attiva)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (id, nome, reparto_id, icona, ordine))
            logger.info(f"   ✅ Categoria {id}: {nome}")
        conn.commit()
        logger.info("   ✅ Commit categorie OK")
        
        # ========================================================================
        # 3. PIATTI (minimi)
        # ========================================================================
        logger.info("🍽️ Creazione PIATTI minimi...")
        cursor.execute("DELETE FROM piatti")
        piatti = [
            (1, 'Bruschetta', 1, 6.50),
            (2, 'Spaghetti', 2, 12.00),
            (3, 'Bistecca', 3, 18.00),
        ]
        for id, nome, cat_id, prezzo in piatti:
            cursor.execute("""
                INSERT OR REPLACE INTO piatti (id, nome, categoria_id, prezzo, disponibile)
                VALUES (?, ?, ?, ?, 1)
            """, (id, nome, cat_id, prezzo))
            logger.info(f"   ✅ Piatto {id}: {nome}")
        conn.commit()
        logger.info("   ✅ Commit piatti OK")
        
        # ========================================================================
        # 4. SALE (AGGIUNTO - MANCAVA!)
        # ========================================================================
        logger.info("🏛️ Creazione SALE...")
        cursor.execute("DELETE FROM sale")
        sale = [
            (1, 'SALA PRINCIPALE', '#2ecc71', 1),
            (2, 'TERRAZZA', '#f1c40f', 2),
            (3, 'SALA PRIVATA', '#9b59b6', 3),
        ]
        for id, nome, colore, ordine in sale:
            cursor.execute("""
                INSERT OR REPLACE INTO sale (id, nome, colore, ordine, attiva)
                VALUES (?, ?, ?, ?, 1)
            """, (id, nome, colore, ordine))
            logger.info(f"   ✅ Sala {id}: {nome}")
        conn.commit()
        logger.info("   ✅ Commit sale OK")
        
        # ========================================================================
        # 5. TAVOLI (AGGIUNTO - MANCAVA!)
        # ========================================================================
        logger.info("🪑 Creazione TAVOLI...")
        cursor.execute("DELETE FROM tavoli")
        tavoli_per_sala = {1: 8, 2: 6, 3: 4}
        tavoli_creati = 0
        for sala_id, num_tavoli in tavoli_per_sala.items():
            for i in range(1, num_tavoli + 1):
                cursor.execute("""
                    INSERT INTO tavoli (numero, sala_id, capienza, stato)
                    VALUES (?, ?, ?, 'LIBERO')
                """, (i, sala_id, 4))
                tavoli_creati += 1
        logger.info(f"   ✅ {tavoli_creati} tavoli creati")
        conn.commit()
        logger.info("   ✅ Commit tavoli OK")
        
        # ========================================================================
        # 6. BRAND (ERA 4, ora 6)
        # ========================================================================
        logger.info("🏢 Creazione BRAND...")
        cursor.execute("DELETE FROM brand WHERE id = 1")
        cursor.execute("""
            INSERT OR REPLACE INTO brand (id, nome, partita_iva) 
            VALUES (1, 'RISTORAPP', '01234567890')
        """)
        conn.commit()
        logger.info("   ✅ Brand OK")
        
        # ========================================================================
        # 7. UTENTI (ERA 5, ora 7)
        # ========================================================================
        logger.info("👥 Creazione UTENTI...")
        cursor.execute("DELETE FROM utenti WHERE id IN (1,2,3,4,5)")
        utenti = [
            (1, 'admin', hash_password('admin123'), 'Admin', 'Super', 'SUPERADMIN'),
            (2, 'cameriere', hash_password('123'), 'Mario', 'Rossi', 'CAMERIERE'),
        ]
        for id, username, pwd_hash, nome, cognome, ruolo in utenti:
            cursor.execute("""
                INSERT OR REPLACE INTO utenti (id, username, password_hash, nome, cognome, ruolo, brand_id, attivo)
                VALUES (?, ?, ?, ?, ?, ?, 1, 1)
            """, (id, username, pwd_hash, nome, cognome, ruolo))
            logger.info(f"   ✅ Utente {id}: {username}")
        conn.commit()
        logger.info("   ✅ Commit utenti OK")
        
        logger.info("=" * 60)
        logger.info("✅ POPOLAMENTO DATI INIZIALI COMPLETATO CON SUCCESSO")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"❌ ERRORE DURANTE IL POPOLAMENTO: {e}")
        import traceback
        traceback.print_exc()
        raise

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
    
    # ============================================================================
    # NUOVI METODI PER STORICO (da aggiungere)
    # ============================================================================
    
    @staticmethod
    def archivia_comanda(comanda_id):
        """Archivia una comanda chiusa nello storico"""
        try:
            # Recupera i dati della comanda
            comanda = esegui_query("""
                SELECT c.*, t.numero as tavolo_numero, s.nome as sala_nome, 
                       u.nome as cameriere_nome, u.cognome as cameriere_cognome
                FROM comande c
                JOIN tavoli t ON c.tavolo_id = t.id
                JOIN sale s ON t.sala_id = s.id
                LEFT JOIN utenti u ON c.cameriere_id = u.id
                WHERE c.id = ?
            """, (comanda_id,), fetchone=True)
            
            if not comanda:
                logger.error(f"Comanda {comanda_id} non trovata")
                return False
            
            # Calcola totale e numero piatti
            piatti = esegui_query("""
                SELECT 
                    COUNT(*) as num_piatti,
                    COALESCE(SUM(qty * prezzo_unitario), 0) as totale
                FROM comandine
                WHERE comanda_id = ?
            """, (comanda_id,), fetchone=True)
            
            # Inserisci nello storico
            esegui_query("""
                INSERT OR REPLACE INTO storico_comande 
                (comanda_id, tavolo_id, tavolo_numero, sala_nome, 
                 data_apertura, data_chiusura, cameriere_nome,
                 totale_comanda, numero_piatti, stato)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'COMPLETATA')
            """, (
                comanda_id,
                comanda['tavolo_id'],
                comanda['tavolo_numero'],
                comanda['sala_nome'],
                comanda['timestamp_apertura'] or datetime.now(),
                datetime.now(),
                f"{comanda.get('cameriere_nome', '')} {comanda.get('cameriere_cognome', '')}".strip(),
                piatti['totale'] or 0,
                piatti['num_piatti'] or 0
            ), commit=True)
            
            logger.info(f"✅ Comanda {comanda_id} archiviata nello storico")
            return True
            
        except Exception as e:
            logger.error(f"❌ Errore archiviazione comanda {comanda_id}: {e}")
            return False
    
    @staticmethod
    def get_storico_tavolo(tavolo_id, giorni=30):
        """Recupera storico comande per un tavolo"""
        try:
            return esegui_query("""
                SELECT * FROM storico_comande
                WHERE tavolo_id = ? AND data_apertura >= datetime('now', ?)
                ORDER BY data_apertura DESC
            """, (tavolo_id, f'-{giorni} days'), fetchall=True)
        except Exception as e:
            logger.error(f"Errore recupero storico tavolo {tavolo_id}: {e}")
            return []


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
        
        # Gestisci i valori None (quando non ci sono pagamenti)
        return {
            'totale_scontrini': stats['totale_scontrini'] or 0,
            'incasso_totale': stats['incasso_totale'] or 0,
            'media_scontrino': stats['media_scontrino'] or 0
        }
    
    # ============================================================================
    # NUOVI METODI PER REPORTISTICA (da aggiungere)
    # ============================================================================
    
    @staticmethod
    def aggiorna_storico_cassa():
        """Aggiorna lo storico giornaliero della cassa"""
        try:
            oggi = date.today().isoformat()
            
            # Calcola statistiche del giorno
            stats = esegui_query("""
                SELECT 
                    COALESCE(SUM(CASE WHEN metodo = 'CONTANTI' THEN totale ELSE 0 END), 0) as contanti,
                    COALESCE(SUM(CASE WHEN metodo = 'CARTA' THEN totale ELSE 0 END), 0) as carta,
                    COALESCE(SUM(CASE WHEN metodo = 'BANCOMAT' THEN totale ELSE 0 END), 0) as bancomat,
                    COALESCE(SUM(CASE WHEN metodo NOT IN ('CONTANTI', 'CARTA', 'BANCOMAT') THEN totale ELSE 0 END), 0) as altri,
                    COUNT(*) as scontrini,
                    COALESCE(AVG(totale), 0) as media
                FROM pagamenti
                WHERE date(timestamp_pagamento) = date('now')
            """, fetchone=True)
            
            if not stats:
                stats = {
                    'contanti': 0, 'carta': 0, 'bancomat': 0,
                    'altri': 0, 'scontrini': 0, 'media': 0
                }
            
            totale = stats['contanti'] + stats['carta'] + stats['bancomat'] + stats['altri']
            
            # Inserisci o aggiorna storico cassa
            esegui_query("""
                INSERT OR REPLACE INTO storico_cassa 
                (data, incasso_contanti, incasso_carta, incasso_bancomat, 
                 incasso_altri, totale_incasso, numero_scontrini, scontrino_medio)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                oggi,
                stats['contanti'],
                stats['carta'],
                stats['bancomat'],
                stats['altri'],
                totale,
                stats['scontrini'],
                stats['media'] or 0
            ), commit=True)
            
            logger.info(f"✅ Storico cassa aggiornato per {oggi}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Errore aggiornamento storico cassa: {e}")
            return False
    
    @staticmethod
    def get_storico_cassa(giorni=7):
        """Recupera storico cassa degli ultimi giorni"""
        try:
            return esegui_query("""
                SELECT * FROM storico_cassa
                WHERE data >= date('now', ?)
                ORDER BY data DESC
            """, (f'-{giorni} days',), fetchall=True)
        except Exception as e:
            logger.error(f"Errore recupero storico cassa: {e}")
            return []
    
    @staticmethod
    def get_statistiche_reparti(giorni=30):
        """Recupera statistiche di produttività per reparto"""
        try:
            return esegui_query("""
                SELECT 
                    r.nome as reparto,
                    r.icona,
                    COUNT(cmd.id) as piatti_preparati,
                    SUM(cmd.qty) as quantita_totale,
                    COUNT(DISTINCT date(cmd.timestamp_pronto)) as giorni_lavorativi,
                    ROUND(AVG(cmd.minuti_consegna), 0) as tempo_medio_minuti
                FROM comandine cmd
                JOIN reparti r ON cmd.reparto_id = r.id
                WHERE cmd.timestamp_pronto IS NOT NULL
                    AND date(cmd.timestamp_pronto) >= date('now', ?)
                GROUP BY r.id, r.nome, r.icona
                ORDER BY piatti_preparati DESC
            """, (f'-{giorni} days',), fetchall=True)
        except Exception as e:
            logger.error(f"Errore recupero statistiche reparti: {e}")
            return []
    
    @staticmethod
    def get_report_giornaliero(data_inizio, data_fine):
        """Genera report giornaliero per un periodo"""
        try:
            return esegui_query("""
                SELECT 
                    date(timestamp_pagamento) as data,
                    COUNT(*) as scontrini,
                    SUM(totale) as incasso_totale,
                    AVG(totale) as scontrino_medio,
                    SUM(CASE WHEN metodo = 'CONTANTI' THEN totale ELSE 0 END) as contanti,
                    SUM(CASE WHEN metodo = 'CARTA' THEN totale ELSE 0 END) as carta,
                    SUM(CASE WHEN metodo = 'BANCOMAT' THEN totale ELSE 0 END) as bancomat,
                    SUM(CASE WHEN metodo NOT IN ('CONTANTI', 'CARTA', 'BANCOMAT') THEN totale ELSE 0 END) as altri
                FROM pagamenti
                WHERE date(timestamp_pagamento) BETWEEN ? AND ?
                GROUP BY date(timestamp_pagamento)
                ORDER BY data DESC
            """, (data_inizio, data_fine), fetchall=True)
        except Exception as e:
            logger.error(f"Errore generazione report giornaliero: {e}")
            return []

# ============================================================================
# SERVIZIO STAMPANTI - CON RICERCA AUTOMATICA
# ============================================================================
import socket
import threading
import queue
import time
import subprocess
import sys
import re
import glob
import os

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
        
        # Se è una stampante reale, invia il comando
        if printer_config and printer_config.get('interfaccia') == 'network':
            try:
                ip = printer_config['indirizzo_ip']
                port = printer_config.get('porta', 9100)
                
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(5)
                sock.connect((ip, port))
                sock.send(content.encode('utf-8', errors='ignore'))
                sock.close()
                esito = 'INVIATO'
                print(f"✅ Stampato {tipo} su {ip}:{port}")
            except Exception as e:
                esito = f'ERRORE: {e}'
                print(f"❌ Errore stampa su rete: {e}")
        
        elif printer_config and printer_config.get('interfaccia') == 'usb':
            try:
                device = printer_config['device_path']
                with open(device, 'wb') as f:
                    f.write(content.encode('utf-8', errors='ignore'))
                esito = 'INVIATO'
                print(f"✅ Stampato {tipo} su {device}")
            except Exception as e:
                esito = f'ERRORE: {e}'
                print(f"❌ Errore stampa su USB: {e}")
        
        else:
            # Stampa simulata
            print(f"\n🖨️ SIMULAZIONE STAMPA - {tipo}")
            print(content)
            print("-" * 40)
            esito = 'SIMULATO'
        
        # Log successo
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO log_stampe (tipo, reparto_id, comanda_id, contenuto, esito)
                VALUES (?, ?, ?, ?, ?)
            """, (tipo, reparto_id, comanda_id, content[:200], esito))
            conn.commit()
            conn.close()
        except:
            pass
        
    except Exception as e:
        print(f"❌ Errore stampa: {e}")


def scan_usb_printers():
    """
    Scansiona le porte USB per trovare stampanti termiche collegate
    Restituisce una lista di stampanti trovate
    """
    printers = []
    
    try:
        if sys.platform == 'linux':
            # Su Linux, controlla /dev/usb/lp*
            usb_devices = glob.glob('/dev/usb/lp*') + glob.glob('/dev/lp*')
            
            for dev in usb_devices:
                # Prova a leggere le info del dispositivo
                try:
                    # Usa lsusb per trovare il vendor/product ID
                    result = subprocess.run(['lsusb'], capture_output=True, text=True)
                    lines = result.stdout.split('\n')
                    
                    # Cerca corrispondenze con device comuni per stampanti termiche
                    for line in lines:
                        if 'Printer' in line or 'Thermal' in line or 'POS' in line:
                            # Estrai ID (formato: Bus XXX Device YYY: ID 1234:5678 Nome)
                            match = re.search(r'ID (\w+):(\w+)', line)
                            if match:
                                vendor_id = int(match.group(1), 16)
                                product_id = int(match.group(2), 16)
                                
                                printers.append({
                                    'nome': f"Stampante USB {dev}",
                                    'tipo': 'TERMICA',
                                    'interfaccia': 'usb',
                                    'device_path': dev,
                                    'vendor_id': vendor_id,
                                    'product_id': product_id,
                                    'descrizione': line.strip()
                                })
                except:
                    pass
        
        elif sys.platform == 'win32':
            # Su Windows, prova a importare serial.tools.list_ports
            try:
                import serial.tools.list_ports
                ports = serial.tools.list_ports.comports()
                
                for port in ports:
                    if 'USB' in port.description or 'COM' in port.description:
                        printers.append({
                            'nome': f"Stampante {port.description}",
                            'tipo': 'TERMICA',
                            'interfaccia': 'serial',
                            'porta': port.device,
                            'vendor_id': port.vid,
                            'product_id': port.pid,
                            'descrizione': port.description
                        })
            except ImportError:
                print("⚠️ pyserial non installato. Installa: pip install pyserial")
    
    except Exception as e:
        logger.error(f"Errore scansione USB: {e}")
    
    return printers


def scan_network_printers(subnet=None, timeout=0.5):
    """
    Scansiona la rete locale per trovare stampanti di rete (porta 9100)
    """
    printers = []
    
    try:
        # Se non specificato, usa la subnet locale
        if not subnet:
            # Ottieni l'IP locale
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            
            # Assumi /24 subnet
            subnet = '.'.join(local_ip.split('.')[:-1]) + '.'
        
        # Porte comuni per stampanti
        ports = [9100, 515, 631]  # 9100=raw, 515=lpd, 631=ipp
        
        print(f"🔍 Scansione rete {subnet}0/24 in corso...")
        
        # Scansiona IP da .1 a .254
        found = 0
        for i in range(1, 255):
            ip = f"{subnet}{i}"
            
            for port in ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(timeout)
                    result = sock.connect_ex((ip, port))
                    sock.close()
                    
                    if result == 0:
                        # Porta aperta, probabile stampante
                        try:
                            # Tenta di ottenere il nome host
                            host = socket.gethostbyaddr(ip)[0]
                        except:
                            host = ip
                        
                        printers.append({
                            'nome': f"Stampante {host}",
                            'tipo': 'TERMICA',
                            'interfaccia': 'network',
                            'indirizzo_ip': ip,
                            'porta': port,
                            'descrizione': f"Stampante di rete ({ip}:{port})"
                        })
                        found += 1
                        print(f"  ✅ Trovata stampante: {ip}:{port}")
                        break  # Esci dal loop porte se ne trovi una aperta
                except:
                    pass
            
            # Aggiornamento ogni 10 IP per non bloccare
            if i % 10 == 0:
                print(f"  Scansione in corso... {i}/254")
    
    except Exception as e:
        logger.error(f"Errore scansione rete: {e}")
    
    print(f"✅ Scansione completata. Trovate {found} stampanti.")
    return printers


def test_printer_connection(printer_config):
    """
    Testa la connessione a una stampante
    """
    try:
        if printer_config.get('interfaccia') == 'network':
            ip = printer_config['indirizzo_ip']
            port = printer_config.get('porta', 9100)
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex((ip, port))
            sock.close()
            
            return result == 0, "Connessione OK" if result == 0 else f"Timeout su {ip}:{port}"
        
        elif printer_config.get('interfaccia') == 'usb':
            if sys.platform == 'linux':
                device = printer_config.get('device_path')
                if device and os.path.exists(device):
                    # Prova a scrivere un byte di test
                    try:
                        with open(device, 'wb') as f:
                            f.write(b'\x0a')
                        return True, f"Dispositivo {device} accessibile"
                    except:
                        return True, f"Dispositivo {device} trovato (sola lettura?)"
                else:
                    return False, f"Dispositivo {device} non trovato"
        
        elif printer_config.get('interfaccia') == 'serial':
            try:
                import serial
                port = printer_config.get('porta')
                ser = serial.Serial(port, timeout=1)
                ser.close()
                return True, f"Porta {port} accessibile"
            except ImportError:
                return False, "Libreria pyserial non installata"
            except Exception as e:
                return False, f"Errore porta {port}: {e}"
    
    except Exception as e:
        return False, str(e)
    
    return False, "Tipo interfaccia non supportato"


def get_printer_status(printer_id):
    """
    Ottiene lo stato di una stampante dal database
    """
    try:
        printer = esegui_query("SELECT * FROM stampanti WHERE id = ?", (printer_id,), fetchone=True)
        if not printer:
            return None
        
        # Test connessione
        connected, message = test_printer_connection(printer)
        
        return {
            'id': printer['id'],
            'nome': printer['nome'],
            'connected': connected,
            'message': message,
            'attivo': printer['attivo']
        }
    except Exception as e:
        logger.error(f"Errore get_printer_status: {e}")
        return None


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
    def get_tutte_stampanti():
        """Recupera tutte le stampanti configurate"""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = dict_factory
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.*, r.nome as reparto_nome, r.icona as reparto_icona
                FROM stampanti s
                LEFT JOIN reparti r ON s.reparto_id = r.id
                ORDER BY s.reparto_id, s.nome
            """)
            result = cursor.fetchall()
            conn.close()
            return result
        except:
            return []
    
    @staticmethod
    def aggiungi_stampante(nome, reparto_id, tipo, indirizzo_ip=None, porta=9100, 
                           device_path=None, vendor_id=None, product_id=None):
        """Aggiunge una nuova stampante al database"""
        try:
            esegui_query("""
                INSERT INTO stampanti 
                (nome, reparto_id, tipo, indirizzo_ip, porta, device_path, 
                 usb_vendor_id, usb_product_id, attivo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (nome, reparto_id, tipo, indirizzo_ip, porta, device_path,
                  vendor_id, product_id), commit=True)
            return True
        except Exception as e:
            logger.error(f"Errore aggiunta stampante: {e}")
            return False
    
    @staticmethod
    def aggiorna_stampante(printer_id, **kwargs):
        """Aggiorna i dati di una stampante"""
        try:
            campi = []
            valori = []
            for key, value in kwargs.items():
                if value is not None:
                    campi.append(f"{key} = ?")
                    valori.append(value)
            
            if not campi:
                return False
            
            query = f"UPDATE stampanti SET {', '.join(campi)} WHERE id = ?"
            valori.append(printer_id)
            
            esegui_query(query, tuple(valori), commit=True)
            return True
        except Exception as e:
            logger.error(f"Errore aggiornamento stampante: {e}")
            return False
    
    @staticmethod
    def elimina_stampante(printer_id):
        """Elimina una stampante"""
        try:
            esegui_query("DELETE FROM stampanti WHERE id = ?", (printer_id,), commit=True)
            return True
        except Exception as e:
            logger.error(f"Errore eliminazione stampante: {e}")
            return False
    
    @staticmethod
    def stampa_comanda(comanda_id, reparto_id, piatti, stampante_specifica=None):
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
            
            # Se specificata una stampante, usa quella, altrimenti cerca per reparto
            if stampante_specifica:
                cursor.execute("SELECT * FROM stampanti WHERE id = ?", (stampante_specifica,))
            else:
                cursor.execute("""
                    SELECT * FROM stampanti 
                    WHERE reparto_id = ? AND attivo = 1
                    ORDER BY id LIMIT 1
                """, (reparto_id,))
            
            stampante = cursor.fetchone()
            conn.close()
            
            if not comanda:
                return False
            
            # Crea contenuto della stampa
            content_lines = []
            content_lines.append("=" * 42)
            content_lines.append(f"  TAVOLO: {comanda['tavolo_numero']} - {comanda['sala_nome']}")
            content_lines.append(f"  DATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            content_lines.append("-" * 42)
            content_lines.append(" QTA DESCRIZIONE")
            content_lines.append("-" * 42)
            
            for p in piatti:
                nome = p['piatto_nome'][:28] if len(p['piatto_nome']) > 28 else p['piatto_nome']
                content_lines.append(f" {p['qty']:2}  {nome}")
                if p.get('note'):
                    # Se le note sono in formato JSON, estrai solo il testo
                    if p['note'].startswith('{'):
                        try:
                            note_data = json.loads(p['note'])
                            if note_data.get('note'):
                                content_lines.append(f"     -> {note_data['note'][:30]}")
                        except:
                            content_lines.append(f"     -> {p['note'][:30]}")
                    else:
                        content_lines.append(f"     -> {p['note'][:30]}")
            
            content_lines.append("-" * 42)
            content_lines.append("")
            content_lines.append("\n" * 3)
            
            content_str = "\n".join(content_lines)
            
            # Se non c'è stampante configurata, usa stampante virtuale
            if not stampante:
                stampante = {'nome': 'Stampante Virtuale (simulata)'}
            
            job = {
                'printer': stampante,
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
# BACKUP AUTOMATICO E GESTIONE BACKUP (PASSO 7 - DA INSERIRE QUI)
# ============================================================================
import json
import glob
import re
from datetime import datetime, timedelta

def get_backup_list():
    """Restituisce la lista dei backup disponibili"""
    backup_dir = "backup"
    if not os.path.exists(backup_dir):
        return []
    
    backup_files = glob.glob(os.path.join(backup_dir, "ristorante_backup_*.db"))
    backup_list = []
    
    for file in backup_files:
        filename = os.path.basename(file)
        # Estrai timestamp dal nome file
        match = re.search(r'backup_(\d{8}_\d{6})', filename)
        if match:
            timestamp_str = match.group(1)
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                size = os.path.getsize(file)
                backup_list.append({
                    'filename': filename,
                    'path': file,
                    'timestamp': timestamp,
                    'size': size,
                    'size_str': f"{size/1024:.1f} KB" if size < 1024*1024 else f"{size/(1024*1024):.1f} MB"
                })
            except:
                pass
    
    # Ordina per data (più recenti prima)
    backup_list.sort(key=lambda x: x['timestamp'], reverse=True)
    return backup_list

def crea_backup_manual():
    """Crea un backup manuale"""
    return backup_automatico()

def ripristina_backup(backup_path):
    """Ripristina un backup"""
    try:
        # Verifica che il file esista
        if not os.path.exists(backup_path):
            return False, "File backup non trovato"
        
        # Crea un backup di sicurezza prima di ripristinare
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safety_path = os.path.join("backup", f"pre_restore_{timestamp}.db")
        shutil.copy2(DB_PATH, safety_path)
        
        # Ripristina il backup
        shutil.copy2(backup_path, DB_PATH)
        
        return True, f"Backup ripristinato da {os.path.basename(backup_path)}"
    except Exception as e:
        return False, str(e)

def elimina_backup(backup_path):
    """Elimina un file di backup"""
    try:
        if os.path.exists(backup_path):
            os.remove(backup_path)
            return True, "Backup eliminato"
        return False, "File non trovato"
    except Exception as e:
        return False, str(e)

def configura_backup_automatico(interval_hours=24, max_backups=10):
    """Configura il backup automatico (salva le impostazioni in config)"""
    try:
        # Salva configurazione nel database
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Assicurati che la tabella config esista
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                chiave TEXT PRIMARY KEY,
                valore TEXT,
                tipo TEXT DEFAULT 'text',
                descrizione TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Salva impostazioni
        cursor.execute("""
            INSERT OR REPLACE INTO config (chiave, valore, tipo, descrizione)
            VALUES (?, ?, ?, ?)
        """, ('backup_interval', str(interval_hours), 'number', 'Ore tra backup automatici'))
        
        cursor.execute("""
            INSERT OR REPLACE INTO config (chiave, valore, tipo, descrizione)
            VALUES (?, ?, ?, ?)
        """, ('backup_max', str(max_backups), 'number', 'Numero massimo di backup da mantenere'))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Errore configurazione backup: {e}")
        return False

def carica_config_backup():
    """Carica la configurazione dei backup"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT valore FROM config WHERE chiave = 'backup_interval'")
        interval = cursor.fetchone()
        
        cursor.execute("SELECT valore FROM config WHERE chiave = 'backup_max'")
        max_backups = cursor.fetchone()
        
        conn.close()
        
        return {
            'interval': int(interval[0]) if interval else 24,
            'max_backups': int(max_backups[0]) if max_backups else 10
        }
    except:
        return {'interval': 24, 'max_backups': 10}

def pulizia_backup_automatica(max_backups=10):
    """Mantiene solo gli ultimi N backup"""
    try:
        backup_list = get_backup_list()
        if len(backup_list) <= max_backups:
            return 0
        
        # Elimina i backup più vecchi
        eliminati = 0
        for backup in backup_list[max_backups:]:
            if os.path.exists(backup['path']):
                os.remove(backup['path'])
                eliminati += 1
        
        return eliminati
    except Exception as e:
        print(f"Errore pulizia backup: {e}")
        return 0

def avvia_scheduler_backup():
    """Avvia il thread per backup automatico"""
    import threading
    import time
    
    def backup_worker():
        while True:
            try:
                config = carica_config_backup()
                # Crea backup
                backup_path = backup_automatico()
                if backup_path:
                    # Pulisci backup vecchi
                    eliminati = pulizia_backup_automatica(config['max_backups'])
                    print(f"✅ Backup automatico completato. Eliminati {eliminati} backup vecchi.")
                
                # Aspetta l'intervallo configurato
                time.sleep(config['interval'] * 3600)
            except Exception as e:
                print(f"❌ Errore backup automatico: {e}")
                time.sleep(3600)  # Riprova tra un'ora
    
    # Avvia thread
    thread = threading.Thread(target=backup_worker, daemon=True)
    thread.start()
    
    # 🔥 NUOVO: Avvia anche il programma di pulizia avanzata
    programma_pulizia_backup()
    
    return thread


# ============================================================================
# PASSO 7C - PULIZIA AUTOMATICA BACKUP AVANZATA
# ============================================================================
def pulizia_backup_automatica_avanzata(mantenere=10, giorni_vecchi=30, comprimi=True):
    """
    Pulizia avanzata dei backup:
    - Mantiene solo gli ultimi N backup
    - Elimina backup più vecchi di X giorni
    - Opzionalmente comprime i backup vecchi ma da mantenere
    """
    try:
        backup_dir = "backup"
        if not os.path.exists(backup_dir):
            return 0, 0, 0
        
        backup_files = glob.glob(os.path.join(backup_dir, "ristorante_backup_*.db"))
        backup_files += glob.glob(os.path.join(backup_dir, "ristorante_backup_*.db.gz"))
        
        if not backup_files:
            return 0, 0, 0
        
        # Estrai info dai file
        backups = []
        for file in backup_files:
            filename = os.path.basename(file)
            match = re.search(r'backup_(\d{8}_\d{6})', filename)
            if match:
                timestamp_str = match.group(1)
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    is_compressed = filename.endswith('.gz')
                    backups.append({
                        'path': file,
                        'filename': filename,
                        'timestamp': timestamp,
                        'size': os.path.getsize(file),
                        'compressed': is_compressed,
                        'giorni': (datetime.now() - timestamp).days
                    })
                except:
                    pass
        
        # Ordina per data (più recenti prima)
        backups.sort(key=lambda x: x['timestamp'], reverse=True)
        
        eliminati = 0
        compressi = 0
        risparmiati = 0
        
        # 1. Mantieni solo gli ultimi N backup
        if len(backups) > mantenere:
            for vecchio in backups[mantenere:]:
                try:
                    # Se è vecchio e non compresso, prima comprimi se richiesto
                    if comprimi and not vecchio['compressed'] and vecchio['giorni'] > 7:
                        if comprimi_backup(vecchio['path']):
                            compressi += 1
                            risparmiati += vecchio['size'] - os.path.getsize(vecchio['path'] + '.gz')
                            continue  # Non eliminare, è stato compresso
                    
                    # Altrimenti elimina
                    os.remove(vecchio['path'])
                    eliminati += 1
                    logger.info(f"🗑️ Backup eliminato: {vecchio['filename']}")
                except Exception as e:
                    logger.error(f"Errore eliminazione {vecchio['filename']}: {e}")
        
        # 2. Elimina backup più vecchi di giorni_vecchi (se non già coperti)
        soglia = datetime.now() - timedelta(days=giorni_vecchi)
        for backup in backups[:mantenere]:  # Solo tra quelli mantenuti
            if backup['timestamp'] < soglia:
                try:
                    os.remove(backup['path'])
                    eliminati += 1
                    logger.info(f"🗑️ Backup vecchio eliminato: {backup['filename']} ({backup['giorni']} giorni)")
                except Exception as e:
                    logger.error(f"Errore eliminazione {backup['filename']}: {e}")
        
        return eliminati, compressi, risparmiati
        
    except Exception as e:
        logger.error(f"Errore pulizia backup avanzata: {e}")
        return 0, 0, 0


def comprimi_backup(file_path):
    """Comprime un file di backup in .gz"""
    try:
        import gzip
        
        output_path = file_path + '.gz'
        
        # Se già esiste compresso, salta
        if os.path.exists(output_path):
            return False
        
        # Comprimi
        with open(file_path, 'rb') as f_in:
            with gzip.open(output_path, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        
        # Verifica che il file compresso sia più piccolo
        original_size = os.path.getsize(file_path)
        compressed_size = os.path.getsize(output_path)
        
        if compressed_size < original_size * 0.8:  # Risparmio almeno 20%
            # Elimina originale
            os.remove(file_path)
            logger.info(f"📦 Backup compresso: {os.path.basename(file_path)} -> {compressed_size/1024:.1f} KB (risparmio {((original_size-compressed_size)/original_size*100):.1f}%)")
            return True
        else:
            # Se non conviene, elimina il compresso
            os.remove(output_path)
            return False
            
    except Exception as e:
        logger.error(f"Errore compressione {file_path}: {e}")
        return False


def programma_pulizia_backup():
    """Avvia schedulazione pulizia backup (da chiamare all'avvio)"""
    import threading
    import time
    
    def worker_pulizia():
        while True:
            try:
                config = carica_config_pulizia()
                
                # Esegui pulizia una volta al giorno (controlla ogni ora)
                if datetime.now().hour == 3:  # Alle 3 di notte
                    logger.info("🔄 Avvio pulizia backup automatica...")
                    
                    eliminati, compressi, risparmiati = pulizia_backup_automatica_avanzata(
                        mantenere=config.get('max_backups', 10),
                        giorni_vecchi=30,
                        comprimi=True
                    )
                    
                    if eliminati > 0 or compressi > 0:
                        logger.info(f"✅ Pulizia completata: {eliminati} eliminati, {compressi} compressi, {risparmiati/1024:.1f} KB risparmiati")
                    
                    # Aspetta 24 ore prima di ricontrollare
                    time.sleep(24 * 3600)
                else:
                    # Controlla ogni ora
                    time.sleep(3600)
                    
            except Exception as e:
                logger.error(f"Errore nel worker pulizia: {e}")
                time.sleep(3600)
    
    # Avvia thread
    thread = threading.Thread(target=worker_pulizia, daemon=True)
    thread.start()
    logger.info("⏰ Programma pulizia backup avviato (esecuzione alle 3:00)")
    return thread


def configura_pulizia_backup(mantenere=10, giorni_vecchi=30, auto_compress=True):
    """Configura i parametri di pulizia automatica"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Assicurati che la tabella config esista
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                chiave TEXT PRIMARY KEY,
                valore TEXT,
                tipo TEXT DEFAULT 'text',
                descrizione TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Salva impostazioni
        configurazioni = [
            ('backup_mantieni', str(mantenere), 'number', 'Numero di backup da mantenere'),
            ('backup_giorni_vecchi', str(giorni_vecchi), 'number', 'Giorni dopo cui eliminare backup'),
            ('backup_auto_compress', str(auto_compress), 'boolean', 'Comprimi automaticamente backup vecchi')
        ]
        
        for chiave, valore, tipo, descrizione in configurazioni:
            cursor.execute("""
                INSERT OR REPLACE INTO config (chiave, valore, tipo, descrizione)
                VALUES (?, ?, ?, ?)
            """, (chiave, valore, tipo, descrizione))
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Configurazione pulizia backup salvata: mantieni={mantenere}, giorni={giorni_vecchi}, compress={auto_compress}")
        return True
        
    except Exception as e:
        logger.error(f"Errore configurazione pulizia backup: {e}")
        return False


def carica_config_pulizia():
    """Carica la configurazione di pulizia backup"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        config = {
            'mantenere': 10,
            'giorni_vecchi': 30,
            'auto_compress': True
        }
        
        cursor.execute("SELECT chiave, valore FROM config WHERE chiave IN ('backup_mantieni', 'backup_giorni_vecchi', 'backup_auto_compress')")
        for chiave, valore in cursor.fetchall():
            if chiave == 'backup_mantieni':
                config['mantenere'] = int(valore)
            elif chiave == 'backup_giorni_vecchi':
                config['giorni_vecchi'] = int(valore)
            elif chiave == 'backup_auto_compress':
                config['auto_compress'] = valore.lower() == 'true'
        
        conn.close()
        return config
        
    except Exception as e:
        logger.error(f"Errore caricamento config pulizia: {e}")
        return {'mantenere': 10, 'giorni_vecchi': 30, 'auto_compress': True}


def esegui_pulizia_manuale(mantenere=None, giorni_vecchi=None, comprimi=None):
    """Esegue pulizia manuale dei backup"""
    config = carica_config_pulizia()
    
    eliminati, compressi, risparmiati = pulizia_backup_automatica_avanzata(
        mantenere=mantenere if mantenere is not None else config['mantenere'],
        giorni_vecchi=giorni_vecchi if giorni_vecchi is not None else config['giorni_vecchi'],
        comprimi=comprimi if comprimi is not None else config['auto_compress']
    )
    
    return {
        'eliminati': eliminati,
        'compressi': compressi,
        'risparmiati_kb': risparmiati / 1024,
        'messaggio': f"Pulizia completata: {eliminati} backup eliminati, {compressi} backup compressi, {risparmiati/1024:.1f} KB risparmiati"
    }

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
        
        if risultato and risultato[0]:
            url = risultato[0]
            # Se siamo in Streamlit Cloud e l'URL è locale, correggi
            if os.environ.get('STREAMLIT_CLOUD') and 'localhost' in url:
                # Forza l'URL corretto per il cloud
                return "https://ristorapp-bons72.streamlit.app"
            return url
        else:
            # Se non c'è URL salvato, usa il default in base all'ambiente
            if os.environ.get('STREAMLIT_CLOUD'):
                return "https://ristorapp-bons72.streamlit.app"
            return "http://localhost:8501"
            
    except Exception as e:
        print(f"❌ Errore caricamento URL: {e}")
        # In caso di errore, restituisci il default corretto per l'ambiente
        if os.environ.get('STREAMLIT_CLOUD'):
            return "https://ristorapp-bons72.streamlit.app"
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
            
            # Popola dati iniziali - PASSANDO ANCHE LA CONNESSIONE per i commit intermedi
            populate_initial_data(cursor, conn)  # <-- MODIFICATO: aggiunto conn
            print("✅ Dati iniziali caricati")
            
            # Commit finale per sicurezza
            conn.commit()
        
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
