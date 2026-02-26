"""
DATABASE MANAGER PROFESSIONALE - PALAZZO FIORINI
Versione 2.0 - Ottimizzato per performance e affidabilità
"""

import sqlite3
import os
import hashlib
import platform
import shutil
from datetime import datetime, date
from contextlib import contextmanager
import logging
from typing import Optional, Dict, List, Any, Tuple

# ============================================================================
# CONFIGURAZIONE LOGGING
# ============================================================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ristorante.log'),
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
            "ristorante.db",
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

# Funzione helper per query rapide
def esegui_query(query: str, params: tuple = (), 
                 fetchone: bool = False, fetchall: bool = False, 
                 commit: bool = False) -> Any:
    """Esegue query SQL in modo sicuro"""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(query, params)
            if commit:
                lastrowid = cursor.lastrowid
                return lastrowid
            elif fetchone:
                return cursor.fetchone()
            elif fetchall:
                return cursor.fetchall()
            return cursor
        except sqlite3.Error as e:
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
        descrizione_pubblica TEXT,  -- Visibile a tutti (menu)
        descrizione_privata TEXT,   -- Ricetta segreta (solo staff)
        prezzo REAL NOT NULL CHECK(prezzo >= 0),
        disponibile INTEGER DEFAULT 1,
        tempo_preparazione INTEGER DEFAULT 10,
        foto_path TEXT DEFAULT NULL,  -- Percorso locale
        foto_data BLOB DEFAULT NULL,  -- Per salvare direttamente nel DB
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

    logger.info("Tabelle create con successo")

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
            variazioni TEXT, -- JSON con variazioni selezionate
            note TEXT,
            FOREIGN KEY (preordine_id) REFERENCES preordini(id) ON DELETE CASCADE,
            FOREIGN KEY (piatto_id) REFERENCES piatti(id)
        )
    """)

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
    
    # ============================================================================
    # NUOVI METODI PER STATISTICHE CASSA
    # ============================================================================
    
    @staticmethod
    def incassi_per_metodo_oggi():
        """Incassi suddivisi per metodo di pagamento per oggi"""
        return esegui_query("""
            SELECT 
                metodo,
                COUNT(*) as numero_transazioni,
                SUM(totale) as totale,
                SUM(contanti) as totale_contanti,
                SUM(carta) as totale_carta,
                SUM(bancomat) as totale_bancomat,
                SUM(altri) as totale_altri
            FROM pagamenti
            WHERE date(timestamp_pagamento) = date('now')
            GROUP BY metodo
            ORDER BY 
                CASE metodo
                    WHEN 'CONTANTI' THEN 1
                    WHEN 'CARTA' THEN 2
                    WHEN 'BANCOMAT' THEN 3
                    WHEN 'MISTO' THEN 4
                    ELSE 5
                END
        """, fetchall=True)
    
    @staticmethod
    def incassi_per_metodo_settimana():
        """Incassi suddivisi per metodo di pagamento per gli ultimi 7 giorni"""
        return esegui_query("""
            SELECT 
                metodo,
                COUNT(*) as numero_transazioni,
                SUM(totale) as totale,
                SUM(contanti) as totale_contanti,
                SUM(carta) as totale_carta,
                SUM(bancomat) as totale_bancomat,
                SUM(altri) as totale_altri
            FROM pagamenti
            WHERE date(timestamp_pagamento) >= date('now', '-7 days')
            GROUP BY metodo
            ORDER BY 
                CASE metodo
                    WHEN 'CONTANTI' THEN 1
                    WHEN 'CARTA' THEN 2
                    WHEN 'BANCOMAT' THEN 3
                    WHEN 'MISTO' THEN 4
                    ELSE 5
                END
        """, fetchall=True)
    
    @staticmethod
    def andamento_giornaliero_per_metodo(giorni=7):
        """Andamento giornaliero degli incassi per metodo"""
        return esegui_query("""
            SELECT 
                date(timestamp_pagamento) as giorno,
                SUM(CASE WHEN metodo = 'CONTANTI' THEN totale ELSE 0 END) as contanti,
                SUM(CASE WHEN metodo = 'CARTA' THEN totale ELSE 0 END) as carta,
                SUM(CASE WHEN metodo = 'BANCOMAT' THEN totale ELSE 0 END) as bancomat,
                SUM(CASE WHEN metodo = 'MISTO' THEN totale ELSE 0 END) as misto,
                SUM(CASE WHEN metodo NOT IN ('CONTANTI', 'CARTA', 'BANCOMAT', 'MISTO') THEN totale ELSE 0 END) as altro,
                SUM(totale) as totale_giorno
            FROM pagamenti
            WHERE date(timestamp_pagamento) >= date('now', ? || ' days')
            GROUP BY date(timestamp_pagamento)
            ORDER BY giorno DESC
        """, (f'-{giorni}',), fetchall=True)
    
    @staticmethod
    def statistiche_complete_oggi():
        """Statistiche complete della giornata"""
        stats = esegui_query("""
            SELECT 
                COUNT(*) as totale_scontrini,
                SUM(totale) as incasso_totale,
                SUM(CASE WHEN metodo = 'CONTANTI' THEN totale ELSE 0 END) as incasso_contanti,
                SUM(CASE WHEN metodo = 'CARTA' THEN totale ELSE 0 END) as incasso_carta,
                SUM(CASE WHEN metodo = 'BANCOMAT' THEN totale ELSE 0 END) as incasso_bancomat,
                SUM(CASE WHEN metodo = 'MISTO' THEN totale ELSE 0 END) as incasso_misto,
                SUM(CASE WHEN metodo NOT IN ('CONTANTI', 'CARTA', 'BANCOMAT', 'MISTO') THEN totale ELSE 0 END) as incasso_altro,
                AVG(totale) as media_scontrino
            FROM pagamenti
            WHERE date(timestamp_pagamento) = date('now')
        """, fetchone=True)
        
        if not stats:
            return {
                'totale_scontrini': 0,
                'incasso_totale': 0,
                'incasso_contanti': 0,
                'incasso_carta': 0,
                'incasso_bancomat': 0,
                'incasso_misto': 0,
                'incasso_altro': 0,
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

class StampanteService:
    """Gestione stampanti termiche per reparti"""
    
    # Coda per stampa asincrona
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
                # Prendi un lavoro dalla coda (timeout 1 secondo)
                job = cls._print_queue.get(timeout=1)
                
                # Esegui la stampa
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
            
            # Prova a importare escpos (opzionale)
            try:
                from escpos.printer import Network, Usb, File
                
                # Inizializza stampante in base alla configurazione
                if printer_config.get('indirizzo_ip'):
                    # Stampante di rete
                    printer = Network(
                        printer_config['indirizzo_ip'],
                        port=printer_config.get('porta', 9100)
                    )
                elif printer_config.get('usb_vendor_id') and printer_config.get('usb_product_id'):
                    # Stampante USB
                    printer = Usb(
                        printer_config['usb_vendor_id'],
                        printer_config['usb_product_id']
                    )
                else:
                    # Stampante virtuale (solo log)
                    print(f"\n🖨️ SIMULAZIONE STAMPA - {tipo}")
                    print(content)
                    print("-" * 40)
                    
                    # Log successo
                    esegui_query("""
                        INSERT INTO log_stampe (tipo, reparto_id, comanda_id, contenuto, esito)
                        VALUES (?, ?, ?, ?, 'SIMULATO')
                    """, (tipo, reparto_id, comanda_id, content[:100]), commit=True)
                    
                    print(f"✅ Stampato {tipo} per comanda {comanda_id} (SIMULATO)")
                    return
                
                # Stampa reale
                printer.text(content)
                printer.cut()
                printer.close()
                
            except ImportError:
                print("⚠️ Libreria escpos non installata - stampa simulata")
                print(f"\n🖨️ SIMULAZIONE STAMPA - {tipo}")
                print(content)
                print("-" * 40)
            
            # Log successo
            esegui_query("""
                INSERT INTO log_stampe (tipo, reparto_id, comanda_id, contenuto, esito)
                VALUES (?, ?, ?, ?, 'SUCCESSO')
            """, (tipo, reparto_id, comanda_id, content[:100]), commit=True)
            
            print(f"✅ Stampato {tipo} per comanda {comanda_id}")
            
        except Exception as e:
            print(f"❌ Errore stampa: {e}")
            # Log errore
            try:
                esegui_query("""
                    INSERT INTO log_stampe (tipo, reparto_id, comanda_id, contenuto, esito)
                    VALUES (?, ?, ?, ?, ?)
                """, (tipo, reparto_id, comanda_id, str(e), f'ERRORE: {str(e)}'), commit=True)
            except:
                pass
    
    @staticmethod
    def get_stampanti_per_reparto(reparto_id):
        """Recupera le stampanti attive per un reparto"""
        return esegui_query("""
            SELECT * FROM stampanti 
            WHERE reparto_id = ? AND attivo = 1
            ORDER BY id
        """, (reparto_id,), fetchall=True)
    
    @staticmethod
    def stampa_comanda(comanda_id, reparto_id, piatti):
        """Prepara e accoda la stampa di una comanda"""
        
        # Recupera info comanda
        comanda = esegui_query("""
            SELECT c.*, t.numero as tavolo_numero, s.nome as sala_nome
            FROM comande c
            JOIN tavoli t ON c.tavolo_id = t.id
            JOIN sale s ON t.sala_id = s.id
            WHERE c.id = ?
        """, (comanda_id,), fetchone=True)
        
        if not comanda:
            print(f"Comanda {comanda_id} non trovata")
            return False
        
        # Recupera stampanti del reparto
        stampanti = StampanteService.get_stampanti_per_reparto(reparto_id)
        
        if not stampanti:
            print(f"Nessuna stampante configurata per reparto {reparto_id}")
            return False
        
        # Formatta contenuto comanda
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
        content.append("\n" * 3)  # Taglio carta
        
        content_str = "\n".join(content)
        
        # Accoda per ogni stampante del reparto
        for stampante in stampanti:
            job = {
                'printer': stampante,
                'content': content_str,
                'tipo': 'COMANDA',
                'comanda_id': comanda_id,
                'reparto_id': reparto_id
            }
            StampanteService._print_queue.put(job)
        
        return True
    
    @staticmethod
    def stampa_preconto(comanda_id):
        """Stampa il preconto per la cassa"""
        
        # Recupera dati comanda
        comanda = esegui_query("""
            SELECT c.*, t.numero as tavolo_numero, s.nome as sala_nome
            FROM comande c
            JOIN tavoli t ON c.tavolo_id = t.id
            JOIN sale s ON t.sala_id = s.id
            WHERE c.id = ?
        """, (comanda_id,), fetchone=True)
        
        if not comanda:
            return False, "Comanda non trovata"
        
        # Recupera piatti
        piatti = esegui_query("""
            SELECT piatto_nome, qty, prezzo_unitario, note
            FROM comandine
            WHERE comanda_id = ?
        """, (comanda_id,), fetchall=True)
        
        if not piatti:
            return False, "Nessun piatto in comanda"
        
        # Calcola totale
        totale = sum(p['qty'] * p['prezzo_unitario'] for p in piatti)
        
        # Recupera stampante della cassa (reparto_id = 5 o speciale)
        stampanti = StampanteService.get_stampanti_per_reparto(5)  # ID 5 = CASSA
        
        if not stampanti:
            # Se non c'è stampante cassa, usa la prima disponibile
            stampanti = esegui_query("""
                SELECT * FROM stampanti WHERE attivo = 1 LIMIT 1
            """, fetchall=True)
        
        if not stampanti:
            print("Nessuna stampante configurata per la cassa")
            return False, "Nessuna stampante configurata"
        
        # Formatta scontrino
        content = []
        content.append("=" * 42)
        content.append("         PRECONTO")
        content.append("=" * 42)
        content.append(f"TAVOLO: {comanda['tavolo_numero']} - {comanda['sala_nome']}")
        content.append(f"DATA: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        content.append("-" * 42)
        content.append(" QTA DESCRIZIONE          IMPORTO")
        content.append("-" * 42)
        
        for p in piatti:
            nome = p['piatto_nome'][:22] if len(p['piatto_nome']) > 22 else p['piatto_nome']
            importo = p['qty'] * p['prezzo_unitario']
            content.append(f" {p['qty']:2}  {nome:22} €{importo:7.2f}")
            if p.get('note'):
                content.append(f"     -> {p['note'][:30]}")
        
        content.append("-" * 42)
        content.append(f"{'TOTALE:':35} €{totale:7.2f}")
        content.append("=" * 42)
        content.append("   *** NON FISCALE ***")
        content.append("=" * 42)
        content.append("\n" * 3)
        
        content_str = "\n".join(content)
        
        # Accoda stampa
        for stampante in stampanti:
            job = {
                'printer': stampante,
                'content': content_str,
                'tipo': 'PRECONTO',
                'comanda_id': comanda_id,
                'reparto_id': 5  # CASSA
            }
            StampanteService._print_queue.put(job)
        
        return True, "Preconto in stampa"
    
    @staticmethod
    def test_stampante(printer_id):
        """Stampa una pagina di test"""
        stampante = esegui_query("SELECT * FROM stampanti WHERE id = ?", (printer_id,), fetchone=True)
        
        if not stampante:
            return False, "Stampante non trovata"
        
        content = []
        content.append("=" * 42)
        content.append("      PAGINA DI TEST")
        content.append("=" * 42)
        content.append(f"Stampante: {stampante['nome']}")
        content.append(f"Data: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        content.append("-" * 42)
        content.append("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        content.append("abcdefghijklmnopqrstuvwxyz")
        content.append("0123456789!@#$%^&*()")
        content.append("-" * 42)
        content.append("€ 10,00 - € 100,00 - € 1.000,00")
        content.append("=" * 42)
        content.append("TEST COMPLETATO")
        content.append("=" * 42)
        content.append("\n" * 3)
        
        content_str = "\n".join(content)
        
        job = {
            'printer': stampante,
            'content': content_str,
            'tipo': 'TEST',
            'reparto_id': stampante['reparto_id']
        }
        StampanteService._print_queue.put(job)
        
        return True, "Test in stampa"

# Avvia il worker all'avvio
StampanteService.start_print_worker()


# ============================================================================
# BACKUP E MANUTENZIONE
# ============================================================================
def backup_automatico():
    """Crea backup automatico del database"""
    try:
        backup_dir = "backup"
        os.makedirs(backup_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(backup_dir, f"ristorante_backup_{timestamp}.db")
        
        shutil.copy2("ristorante.db", backup_path)
        print(f"✅ Backup creato: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"❌ Errore backup: {e}")
        return None


# ============================================================================
# INIZIALIZZAZIONE DATABASE
# ============================================================================
def init_db(force=False):
    """Inizializza il database completo"""
    
    print("=" * 60)
    print("🔄 INIZIALIZZAZIONE DATABASE")
    print("=" * 60)
    
    try:
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
            
            create_tables(cursor)
            create_indexes(cursor)
            populate_initial_data(cursor)
        
        print("✅ Database inizializzato con successo!")
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