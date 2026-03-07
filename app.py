"""
PALAZZO FIORINI - Sistema di Gestione Ristorante
Versione 2.0 - Professionale e Ottimizzata
"""

import streamlit as st
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
import time
import hashlib
import os
from streamlit_autorefresh import st_autorefresh
import qrcode
from PIL import Image
from io import BytesIO
import base64
import json

# ============================================================================
# CONFIGURAZIONE PAGINA (DEVE ESSERE LA PRIMA CHIAMATA STREAMLIT!)
# ============================================================================
st.set_page_config(
    page_title="RISTORAPP - Staff",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================================================
# DEBUG INIZIALE - CATTURA TUTTI GLI ERRORI
# ============================================================================
import sys
import traceback
from datetime import datetime

# Crea un file di log nella cartella temp (UNA SOLA DEFINIZIONE)
DEBUG_LOG = '/tmp/debug_ristorante.log'

def write_debug(message, error=None):
    """Scrive messaggi di debug nel file di log (UNA SOLA FUNZIONE)"""
    try:
        with open(DEBUG_LOG, 'a') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"\n[{timestamp}] {message}")
            if error:
                f.write(f"\nERROR: {error}")
                f.write(f"\n{traceback.format_exc()}")
            f.flush()
    except:
        pass

# Log iniziale
write_debug("=" * 60)
write_debug("🚀 AVVIO APPLICAZIONE")
write_debug("=" * 60)
write_debug(f"Python version: {sys.version}")
write_debug(f"Current directory: {os.getcwd()}")
write_debug(f"Files in directory: {os.listdir('.')}")
write_debug(f"STREAMLIT_CLOUD env: {os.environ.get('STREAMLIT_CLOUD', 'NOT SET')}")

# ============================================================================
# IMPORT DAL DB.PY (AGGIUNTO QUI)
# ============================================================================
try:
    from db import (
        get_db_connection, esegui_query, verify_password, hash_password,
        TavoloService, OrdineService, PagamentoService,
        NotificaService, ReportService,
        get_database_path, create_tables, create_indexes, 
        populate_initial_data,
        # PASSO 7C - Funzioni backup
        get_backup_list, 
        esegui_pulizia_manuale,
        configura_pulizia_backup,
        carica_config_pulizia,
        comprimi_backup,
        crea_backup_manual,
        elimina_backup,
        ripristina_backup,
        carica_config_backup,
        configura_backup_automatico
    )
    write_debug("✅ Import da db.py riuscito!")
    
    # Verifica che le classi esistano
    write_debug(f"✅ TavoloService: {TavoloService}")
    write_debug(f"✅ OrdineService: {OrdineService}")
    write_debug(f"✅ PagamentoService: {PagamentoService}")
    write_debug(f"✅ NotificaService: {NotificaService}")
    write_debug(f"✅ ReportService: {ReportService}")
    
except Exception as e:
    write_debug("❌ ERRORE IMPORT da db.py", e)
    st.error(f"Errore di importazione: {e}")
    st.stop()

# ============================================================================
# INIZIALIZZAZIONE DATABASE (PER STREAMLIT CLOUD)
# ============================================================================
import tempfile

# ============================================================================
# ROUTING PRIORITARIO PER PAGINA CLIENTE (SENZA LOGIN)
# ============================================================================

# Verifica SUBITO se siamo in modalità cliente (prima di qualsiasi altra cosa)
query_params = st.query_params
tavolo_id = query_params.get('tavolo', [None])
if isinstance(tavolo_id, list):
    tavolo_id = tavolo_id[0] if tavolo_id else None
mode = query_params.get('mode', [None])
if isinstance(mode, list):
    mode = mode[0] if mode else None

# SE SIAMO IN MODALITÀ CLIENTE, CARICHIAMO DIRETTAMENTE LA PAGINA CLIENTE
if tavolo_id and mode == 'cliente':
    try:
        write_debug("🚀 Modalità cliente rilevata, caricamento pagina cliente")
        # Non facciamo nessun login, andiamo direttamente alla pagina cliente
        from cliente import show_cliente_page
        show_cliente_page()
        st.stop()  # Ferma l'esecuzione qui - IMPORTANTE!
    except Exception as e:
        write_debug(f"❌ Errore nel caricamento della pagina cliente: {e}", e)
        st.error(f"Errore nel caricamento del menu: {e}")
        st.stop()

# ============================================================================
# INIZIALIZZAZIONE DATABASE (solo per lo staff)
# ============================================================================
def init_database():
    """Inizializza il database se non esiste"""
    try:
        from db import get_database_path, create_tables, create_indexes, populate_initial_data, get_db_connection
        write_debug("✅ Import funzioni db riuscito in init_database")
    except Exception as e:
        write_debug("❌ ERRORE import funzioni db in init_database", e)
        return None
    
    try:
        db_path = get_database_path()
        write_debug(f"📦 Database path: {db_path}")
        
        # Verifica se il database esiste già e se ha le tabelle
        conn_check = sqlite3.connect(db_path)
        cursor_check = conn_check.cursor()
        cursor_check.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='utenti'")
        table_exists = cursor_check.fetchone()
        conn_check.close()
        
        if not table_exists:
            write_debug("🔄 Database non inizializzato. Creazione tabelle...")
            with get_db_connection(init_mode=True) as conn:
                cursor = conn.cursor()
                create_tables(cursor)
                create_indexes(cursor)
                
                # Popola i dati iniziali con gestione errori
                try:
                    write_debug("🔄 Popolamento dati iniziali...")
                    # CHIAMATA CORRETTA CON 2 PARAMETRI
                    populate_initial_data(cursor, conn)
                    write_debug("✅ Dati iniziali popolati con successo")
                    
                    # Commit esplicito dopo il popolamento
                    conn.commit()
                    write_debug("✅ Commit completato")
                    
                except Exception as e:
                    write_debug(f"❌ ERRORE nel popolamento dati iniziali: {e}", e)
                    # Non blocchiamo l'avvio, ma mostriamo avviso
                    import streamlit as st
                    st.warning(f"⚠️ Errore nel popolamento dati: {e}")
                    
                    # Tenta un rollback per sicurezza
                    try:
                        conn.rollback()
                    except:
                        pass
            
            write_debug("✅ Database inizializzato con successo!")
        else:
            write_debug("✅ Database già esistente e funzionante")
            
            # Verifica rapida che i reparti esistano
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM reparti")
                reparti_count = cursor.fetchone()[0]
                conn.close()
                write_debug(f"📊 Reparti presenti: {reparti_count}")
                if reparti_count == 0:
                    write_debug("⚠️ Nessun reparto trovato nel database esistente!")
                    
                    # Tenta di popolare solo i reparti
                    try:
                        write_debug("🔄 Tentativo di creazione reparti in database esistente...")
                        with get_db_connection() as conn:
                            cursor = conn.cursor()
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
                            conn.commit()
                            write_debug("✅ Reparti creati con successo!")
                    except Exception as e2:
                        write_debug(f"⚠️ Errore creazione reparti: {e2}")
                        
            except Exception as e:
                write_debug(f"⚠️ Errore verifica reparti: {e}")
        
        return db_path
    except Exception as e:
        write_debug(f"❌ Errore inizializzazione database: {e}", e)
        return None

# Inizializza il database all'avvio
db_path = init_database()

# ============================================================================
# VERIFICA INTEGRITA' DATABASE (PASSO 4)
# ============================================================================
def verifica_integrita_db():
    """Verifica che tutte le tabelle necessarie esistano"""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        tabelle_necessarie = [
            'utenti', 'brand', 'reparti', 'categorie', 'piatti',
            'sale', 'tavoli', 'comande', 'comandine', 'pagamenti',
            'storico_comande', 'storico_reparti', 'storico_cassa'
        ]
        
        mancanti = []
        for tabella in tabelle_necessarie:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tabella}'")
            if not cursor.fetchone():
                mancanti.append(tabella)
        
        conn.close()
        
        if mancanti:
            write_debug(f"⚠️ Tabelle mancanti: {', '.join(mancanti)}")
            return False
        return True
    except Exception as e:
        write_debug(f"❌ Errore verifica integrità: {e}")
        return False

# Esegui verifica
if not verifica_integrita_db():
    st.warning("⚠️ Alcune tabelle del database sono mancanti. Esegui 'python db.py --force' per ricreare.")
    write_debug("⚠️ Database incompleto - tabelle mancanti")
else:
    write_debug("✅ Verifica integrità database superata")

if db_path:
    os.environ['DB_PATH'] = db_path
    write_debug(f"✅ DB_PATH impostato a: {db_path}")
else:
    write_debug("❌ Inizializzazione database fallita")
    st.error("❌ Errore critico: impossibile inizializzare il database")
    st.stop()

# ============================================================================
# INIZIALIZZAZIONE DATABASE PER STREAMLIT CLOUD (AGGIUNTA QUI)
# ============================================================================
import os
import tempfile

# In Streamlit Cloud, usa database temporaneo ma con inizializzazione
if os.environ.get('STREAMLIT_CLOUD'):
    cloud_db_path = os.path.join(tempfile.gettempdir(), "ristorante.db")
    os.environ['DB_PATH'] = cloud_db_path
    
    # Inizializza se non esiste
    if not os.path.exists(cloud_db_path):
        try:
            from init_cloud import init_cloud_database
            init_cloud_database()
            write_debug("✅ Database cloud inizializzato da app.py")
        except Exception as e:
            write_debug(f"❌ Errore inizializzazione cloud: {e}")
            print(f"❌ Errore inizializzazione cloud: {e}")

# ============================================================================
# ROUTING PER PAGINA CLIENTE (funzione di supporto)
# ============================================================================
def check_cliente_mode():
    """Verifica se siamo in modalità cliente (QR code)"""
    query_params = st.query_params
    tavolo = query_params.get('tavolo', None)
    mode = query_params.get('mode', None)
    if isinstance(tavolo, list):
        tavolo = tavolo[0] if tavolo else None
    if isinstance(mode, list):
        mode = mode[0] if mode else None
    return tavolo is not None and mode == 'cliente'

# ============================================================================
# AUTO-REFRESH CON GESTIONE ERRORI (CORRETTO)
# ============================================================================
try:
    from streamlit_autorefresh import st_autorefresh
    count = st_autorefresh(interval=3000, key="autorefresh")
    write_debug("✅ Auto-refresh component loaded")
except Exception as e:
    write_debug(f"⚠️ Auto-refresh component error: {e}")
    # Fallback: usa timer Python
    if 'last_refresh' not in st.session_state:
        st.session_state.last_refresh = time.time()
    
    if time.time() - st.session_state.last_refresh > 3:
        st.session_state.last_refresh = time.time()
        st.rerun()
    
    st.caption("🔄 Aggiornamento automatico")

# ============================================================================
# INIZIALIZZAZIONE SESSION STATE
# ============================================================================
def init_session_state():
    """Inizializza tutte le variabili di sessione"""
    defaults = {
        'logged_in': False,
        'user_id': None,
        'username': None,
        'user_role': None,
        'pagina_corrente': None,
        'brand_name': 'RISTORAPP',  # <-- MODIFICATO da PALAZZO FIORINI a RISTORAPP
        
        # Sala
        'tavolo_attivo': None,
        'carrello': [],
        'categoria_selezionata': None,
        'variazioni_temp': {},
        'piatto_in_elaborazione': None,
        'comanda_attiva_id': None,
        
        # Cassa
        'tavolo_selezionato_cassa': None,
        'pagamento_in_corso': None,
        'input_prezzo': "",
        'carrello_cassa': [],
        'importi_pagamento': {'contanti': 0, 'carta': 0, 'bancomat': 0, 'altri': 0},
        'metodo_selezionato': 'Contanti',
        
        # UI
        'ultimo_aggiornamento': datetime.now(),
        'notifiche_lette': set(),
        
        # Pre-ordini e revisione
        'preordine_in_revisione': None,
        'rev_carrello': [],
        'rev_cat_selezionata': None,
        
        # Amministrazione
        'edit_piatto_id': None,
        'edit_var_id': None,
        'temp_foto': None,
        
        # Cliente
        'cliente_carrello': [],
        
        # Variabili per preconto (AGGIUNTE)
        'preconto_show': False,
        'preconto_html': None,
        'preconto_comanda_id': None,
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()


# ============================================================================
# FUNZIONE PER OTTENERE IL NOME DEL BRAND
# ============================================================================
@st.cache_data(ttl=60)
def get_brand_name():
    """Restituisce il nome del ristorante dal database"""
    try:
        brand = esegui_query("SELECT nome FROM brand WHERE id = 1", fetchone=True)
        if brand and brand.get('nome'):
            # Aggiorna anche la sessione
            st.session_state.brand_name = brand['nome']
            return brand['nome']
        else:
            return st.session_state.brand_name
    except Exception as e:
        write_debug(f"Errore get_brand_name: {e}")
        return st.session_state.brand_name


# ============================================================================
# CARICA IL BRAND ALL'AVVIO
# ============================================================================
# Prova a caricare il brand dal database
try:
    brand = esegui_query("SELECT nome FROM brand WHERE id = 1", fetchone=True)
    if brand and brand.get('nome'):
        st.session_state.brand_name = brand['nome']
        write_debug(f"✅ Brand caricato: {brand['nome']}")
except Exception as e:
    write_debug(f"⚠️ Brand non caricato: {e}")
    # Usa il default già impostato
    pass

# ============================================================================
# FUNZIONI DI UTILITY
# ============================================================================
def format_currency(amount):
    """Formatta importo in euro - gestisce anche None"""
    if amount is None:
        return "€ 0.00"
    try:
        return f"€ {float(amount):.2f}"
    except (ValueError, TypeError):
        return "€ 0.00"

def get_stato_colore(stato):
    """Restituisce colore per stato piatto"""
    colori = {
        'NUOVO': '#3498db',
        'IN_CORSO': '#f39c12',
        'PRONTO': '#27ae60',
        'SERVITO': '#7f8c8d',
        'ANNULLATO': '#e74c3c'
    }
    return colori.get(stato, '#95a5a6')

def get_stato_icona(stato):
    """Restituisce icona per stato piatto"""
    icone = {
        'NUOVO': '🆕',
        'IN_CORSO': '👨‍🍳',
        'PRONTO': '🔔',
        'SERVITO': '✅',
        'ANNULLATO': '❌'
    }
    return icone.get(stato, '❓')

# ============================================================================
# FUNZIONE PER VARIAZIONI PIATTI
# ============================================================================
def get_variazioni_per_piatto(piatto_id):
    """Recupera le variazioni disponibili per un piatto"""
    try:
        piatto = esegui_query("SELECT categoria_id FROM piatti WHERE id = ?", (piatto_id,), fetchone=True)
        if not piatto:
            return []
        
        categoria = esegui_query("SELECT reparto_id FROM categorie WHERE id = ?", (piatto['categoria_id'],), fetchone=True)
        if not categoria:
            return []
        
        variazioni = esegui_query("""
            SELECT * FROM variazioni 
            WHERE reparto_id = ? AND attivo = 1
            ORDER BY ordine, nome
        """, (categoria['reparto_id'],), fetchall=True)
        
        return variazioni
    except Exception as e:
        write_debug(f"Errore in get_variazioni_per_piatto: {e}", e)
        return []

# ============================================================================
# PAGINA DI LOGIN CON CREAZIONE PRIMO ACCOUNT
# ============================================================================
def show_login():
    """Schermata di login - Crea il primo account se non esistono utenti"""
    
    # === IMPORT DELLE FUNZIONI NECESSARIE ===
    from db import esegui_query, verify_password, hash_password
    # ========================================
    
    # Verifica se esistono utenti nel database
    try:
        # Prova a contare gli utenti
        users = esegui_query("SELECT COUNT(*) as count FROM utenti", fetchone=True)
        users_count = users['count'] if users else 0
    except Exception as e:
        # Se la tabella non esiste o altro errore, assumiamo 0 utenti
        write_debug(f"Errore verifica utenti: {e}")
        users_count = 0
    
    st.markdown("""
        <div style='text-align: center; padding: 2rem;'>
            <h1>🏢 PALAZZO FIORINI</h1>
            <p style='color: #7f8c8d;'>Sistema di Gestione Ristorante</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Se non ci sono utenti, mostra form di registrazione primo account
    if users_count == 0:
        st.info("📋 **Benvenuto!** Non ci sono ancora utenti nel sistema. Crea il primo account amministratore.")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("primo_account_form", clear_on_submit=True):
                st.markdown("### 👑 Crea Amministratore")
                
                col_nome1, col_nome2 = st.columns(2)
                with col_nome1:
                    nome = st.text_input("Nome *", placeholder="Mario", value="Admin")
                with col_nome2:
                    cognome = st.text_input("Cognome *", placeholder="Rossi", value="Super")
                
                username = st.text_input("Username *", placeholder="admin", value="admin", help="Scegli un username per l'accesso")
                password = st.text_input("Password *", type="password", placeholder="Crea una password", value="admin123", help="Scegli una password sicura")
                conferma = st.text_input("Conferma Password *", type="password", placeholder="Conferma password", value="admin123")
                
                st.markdown("---")
                
                if st.form_submit_button("🚀 CREA ACCOUNT", type="primary", use_container_width=True):
                    if not nome or not cognome or not username or not password:
                        st.error("❌ Tutti i campi sono obbligatori")
                    elif password != conferma:
                        st.error("❌ Le password non coincidono")
                    elif len(password) < 3:
                        st.error("❌ La password deve essere almeno di 3 caratteri")
                    else:
                        try:
                            # Assicurati che la tabella utenti esista
                            esegui_query("""
                                CREATE TABLE IF NOT EXISTS utenti (
                                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                                    username TEXT UNIQUE NOT NULL,
                                    password_hash TEXT NOT NULL,
                                    nome TEXT NOT NULL,
                                    cognome TEXT NOT NULL,
                                    ruolo TEXT NOT NULL,
                                    brand_id INTEGER DEFAULT 1,
                                    attivo INTEGER DEFAULT 1,
                                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                                )
                            """, commit=True)
                            
                            # Hash della password
                            from db import hash_password
                            password_hash = hash_password(password)
                            
                            # Crea l'utente amministratore
                            esegui_query("""
                                INSERT INTO utenti (username, password_hash, nome, cognome, ruolo, attivo)
                                VALUES (?, ?, ?, ?, 'SUPERADMIN', 1)
                            """, (username, password_hash, nome, cognome), commit=True)
                            
                            st.success("✅ **Account creato con successo!** Ora puoi fare login.")
                            st.balloons()
                            time.sleep(2)
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Errore durante la creazione: {e}")
                            write_debug(f"Errore creazione primo account: {e}", e)
    
    # Login normale (se ci sono già utenti)
    else:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form", clear_on_submit=True):
                st.markdown("### 🔐 Accedi")
                username = st.text_input("Username", placeholder="Inserisci username")
                password = st.text_input("Password", type="password", placeholder="Inserisci password")
                
                if st.form_submit_button("ACCEDI", type="primary", use_container_width=True):
                    try:
                        user = esegui_query(
                            "SELECT * FROM utenti WHERE username = ? AND attivo = 1",
                            (username,), fetchone=True
                        )
                        
                        if user and verify_password(user['password_hash'], password):
                            st.session_state.logged_in = True
                            st.session_state.user_id = user['id']
                            st.session_state.username = user['username']
                            st.session_state.user_role = user['ruolo']
                            write_debug(f"✅ Login riuscito: {username}")
                            st.rerun()
                        else:
                            write_debug(f"❌ Login fallito: {username}")
                            st.error("❌ Credenziali non valide")
                    except Exception as e:
                        write_debug(f"❌ Errore durante login: {e}", e)
                        st.error(f"Errore: {e}")
            
            st.markdown("---")
            st.caption("💡 Se hai dimenticato le credenziali, contatta l'amministratore")

# ============================================================================
# SIDEBAR
# ============================================================================
def show_sidebar():
    """Menu laterale dinamico"""
    with st.sidebar:
        st.markdown(f"""
            <div style='text-align: center; padding: 1rem;'>
                <h2>🏢 {st.session_state.get('brand_name', 'RISTORAPP')}</h2>  # <-- Default RISTORAPP
                <p>👤 {st.session_state.username}</p>
                <p style='color: #7f8c8d;'>{st.session_state.user_role}</p>
            </div>
        """, unsafe_allow_html=True)
        
        st.divider()
        
        # Menu basato sul ruolo
        menu_items = []
        
        if st.session_state.user_role in ['SUPERADMIN', 'ADMIN']:
            menu_items = [
                ("📊 DASHBOARD", "dashboard"),
                ("🍽️ SALA", "sala"),
                ("👨‍🍳 CUCINA", "cucina"),
                ("🍰 PASTICCERIA", "pasticceria"),
                ("🍕 PIZZERIA", "pizzeria"),
                ("🍸 BAR", "bar"),
                ("💰 CASSA", "cassa"),
                ("📊 STATS", "stats"),
                ("📋 NOTIFICHE", "notifiche"),
                ("💾 BACKUP", "backup"),
                ("🧹 PULIZIA BACKUP", "pulizia_backup"),
                ("🔍 DEBUG ESTREMO", "debug_estremo"),
                ("⚙️ AMMINISTRAZIONE", "admin")
            ]
        elif st.session_state.user_role == 'CAMERIERE':
            menu_items = [
                ("🍽️ SALA", "sala"),
                ("📋 PROMEMORIA CLIENTI", "promemoria"),  # NUOVO
                ("📋 PRE-ORDINI", "preordini"),
                ("📋 NOTIFICHE", "notifiche")
            ]
        elif st.session_state.user_role == 'CUCINA':
            menu_items = [
                ("👨‍🍳 CUCINA", "cucina"),
                ("🍰 PASTICCERIA", "pasticceria"),
                ("🍕 PIZZERIA", "pizzeria"),
            ]
        elif st.session_state.user_role == 'BAR':
            menu_items = [
                ("🍸 BAR", "bar")
            ]
        elif st.session_state.user_role == 'CASSA':
            menu_items = [
                ("💰 CASSA", "cassa"),
                ("📊 STATS", "stats")
            ]
        
        # Notifiche non lette
        try:
            notifiche = NotificaService.get_non_lette(
                st.session_state.user_id,
                st.session_state.user_role
            )
            
            if notifiche:
                st.error(f"🔔 {len(notifiche)} notifiche")
                with st.expander("📬 Notifiche"):
                    for n in notifiche:
                        with st.container():
                            st.markdown(f"**{n['titolo']}**")
                            st.caption(n['messaggio'])
                            if st.button("✓", key=f"notifica_{n['id']}"):
                                NotificaService.segna_letta(n['id'])
                                st.rerun()
        except Exception as e:
            write_debug(f"❌ Errore notifiche: {e}", e)
        
        # Menu principale
        for label, page in menu_items:
            if st.button(label, use_container_width=True,
                        type="primary" if st.session_state.get('pagina_corrente') == page else "secondary"):
                st.session_state.pagina_corrente = page
                st.rerun()
        
        st.divider()
        
        if st.button("🚪 LOGOUT", use_container_width=True):
            st.session_state.clear()
            st.rerun()

# ============================================================================
# MODULO DASHBOARD
# ============================================================================
def show_dashboard():
    st.title("📊 Dashboard")
    
    # KPI principali
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        incasso = ReportService.incasso_oggi()
        st.metric("💰 Incasso Oggi", format_currency(incasso))
    
    with col2:
        ordini = ReportService.ordini_in_corso()
        st.metric("👨‍🍳 Ordini in Corso", ordini)
    
    with col3:
        tavoli = ReportService.tavoli_occupati()
        st.metric("🪑 Tavoli Occupati", tavoli)
    
    with col4:
        st.metric("📈 Performance", "+12%", "vs ieri")
    
    st.divider()
    
    # CORREZIONE 2 - Statistiche reparto (AGGIUNTA QUI)
    show_statistiche_reparto()
    
    st.divider()
    
    # Grafico vendite
    st.subheader("📈 Andamento Vendite Oggi")
    
    vendite_ore = esegui_query("""
        SELECT strftime('%H:00', timestamp_pagamento) as ora,
               COUNT(*) as scontrini,
               SUM(totale) as incasso
        FROM pagamenti
        WHERE date(timestamp_pagamento) = date('now')
        GROUP BY strftime('%H', timestamp_pagamento)
        ORDER BY ora
    """, fetchall=True)
    
    if vendite_ore:
        df = pd.DataFrame(vendite_ore)
        st.bar_chart(df.set_index('ora')['incasso'])
    else:
        st.info("Nessun dato per oggi")
    
    st.divider()
    
    # Top piatti
    col_p1, col_p2 = st.columns(2)
    
    with col_p1:
        st.subheader("🏆 Top Piatti del Giorno")
        top_piatti = ReportService.piatti_piu_venduti(5)
        if top_piatti:
            for i, p in enumerate(top_piatti, 1):
                st.markdown(f"{i}. **{p['piatto_nome']}** - {p['totale']} ordini")
        else:
            st.info("Nessun dato")
    
    with col_p2:
        st.subheader("🕒 Ultime Attività")
        ultimi_pagamenti = esegui_query("""
            SELECT p.timestamp_pagamento, t.numero, p.totale
            FROM pagamenti p
            JOIN comande c ON p.comanda_id = c.id
            JOIN tavoli t ON c.tavolo_id = t.id
            ORDER BY p.timestamp_pagamento DESC
            LIMIT 5
        """, fetchall=True)
        
        if ultimi_pagamenti:
            for up in ultimi_pagamenti:
                ora = up['timestamp_pagamento'].strftime('%H:%M') if up['timestamp_pagamento'] else 'N/A'
                st.markdown(f"Tavolo {up['numero']}: {format_currency(up['totale'])} - {ora}")
        else:
            st.info("Nessuna attività recente")


# CORREZIONE 2 - Nuova funzione per statistiche reparto (DA AGGIUNGERE DOPO show_dashboard)
def show_statistiche_reparto():
    """Mostra statistiche rapide per reparto in dashboard"""
    with st.expander("👨‍🍳 STATISTICHE REPARTI OGGI", expanded=False):
        stats = ReportService.get_statistiche_reparti(1)  # ultimo giorno
        
        if stats:
            cols = st.columns(len(stats))
            for i, stat in enumerate(stats):
                with cols[i]:
                    st.metric(
                        label=f"{stat['icona']} {stat['reparto']}",
                        value=f"{stat['piatti_preparati']} piatti",
                        help=f"Tempo medio: {stat.get('tempo_medio_minuti', 0)} min"
                    )
        else:
            st.info("Nessun dato disponibile per oggi")

# ============================================================================
# MODULO SALA - VERSIONE OTTIMIZZATA CON LAYOUT DUE COLONNE
# ============================================================================
def show_sala():
    """Gestione sala con layout due colonne (menu a sinistra, carrello a destra)"""
    
    # Controllo piatti pronti (notifica persistente)
    piatti_pronti_totali = esegui_query("""
        SELECT COUNT(*) as cnt FROM comandine
        WHERE stato = 'PRONTO'
    """, fetchone=True)['cnt']
    
    if piatti_pronti_totali > 0:
        st.warning(f"🔔 **{piatti_pronti_totali} piatti pronti da servire!**")
        
        # Mostra tavoli con piatti pronti
        tavoli_con_pronti = esegui_query("""
            SELECT DISTINCT t.id, t.numero, s.nome as sala_nome,
                   COUNT(cmd.id) as num_pronti
            FROM comandine cmd
            JOIN comande c ON cmd.comanda_id = c.id
            JOIN tavoli t ON c.tavolo_id = t.id
            JOIN sale s ON t.sala_id = s.id
            WHERE cmd.stato = 'PRONTO'
            GROUP BY t.id, t.numero, s.nome
            ORDER BY s.nome, t.numero
        """, fetchall=True)
        
        if tavoli_con_pronti:
            cols = st.columns(len(tavoli_con_pronti))
            for i, tavolo in enumerate(tavoli_con_pronti):
                with cols[i]:
                    if st.button(f"🔔 Tavolo {tavolo['numero']}\n({tavolo['num_pronti']} piatti)", 
                               key=f"vai_pronto_{tavolo['id']}"):
                        # Vai al tavolo con piatti pronti
                        tavoli = TavoloService.get_tutti_tavoli()
                        for t in tavoli:
                            if t['id'] == tavolo['id']:
                                st.session_state.tavolo_attivo = t
                                comanda = OrdineService.get_comande_attive(t['id'])
                                if comanda:
                                    st.session_state.comanda_attiva_id = comanda['id']
                                st.rerun()
    
    st.divider()
    
    # Se nessun tavolo attivo, mostra mappa
    if st.session_state.tavolo_attivo is None:
        show_mappa_tavoli()
    else:
        show_gestione_tavolo()


def show_mappa_tavoli():
    """Mappa interattiva dei tavoli con anteprima piatti pronti"""
    
    tavoli = TavoloService.get_tutti_tavoli()
    
    # Raggruppa per sala
    sale = {}
    for t in tavoli:
        if t['sala_nome'] not in sale:
            sale[t['sala_nome']] = []
        sale[t['sala_nome']].append(t)
    
    for nome_sala, tavoli_sala in sale.items():
        st.subheader(f"🏢 {nome_sala}")
        
        cols = st.columns(4)
        
        for i, tavolo in enumerate(tavoli_sala):
            with cols[i % 4]:
                # Controlla piatti pronti per questo tavolo
                piatti_pronti_tavolo = esegui_query("""
                    SELECT COUNT(*) as cnt FROM comandine cmd
                    JOIN comande c ON cmd.comanda_id = c.id
                    WHERE c.tavolo_id = ? AND cmd.stato = 'PRONTO'
                """, (tavolo['id'],), fetchone=True)['cnt']
                
                # Determina icona e stato
                if tavolo['richiesta_conto'] == 1:
                    icona = "💰"
                    bg_color = "#f39c12"
                    stato = "CONTO RICHIESTO"
                elif piatti_pronti_tavolo > 0:
                    icona = f"🔔 {piatti_pronti_tavolo}"
                    bg_color = "#27ae60"
                    stato = f"{piatti_pronti_tavolo} PRONTI"
                elif tavolo['stato'] == 'OCCUPATO':
                    icona = "👥"
                    bg_color = "#3498db"
                    stato = "OCCUPATO"
                else:
                    icona = "✅"
                    bg_color = "#7f8c8d"
                    stato = "LIBERO"
                
                # Bottone con stile personalizzato
                if st.button(
                    f"{icona}\n**Tavolo {tavolo['numero']}**\n{stato}",
                    key=f"tavolo_{tavolo['id']}",
                    use_container_width=True,
                    help=f"Clicca per gestire Tavolo {tavolo['numero']}"
                ):
                    st.session_state.tavolo_attivo = tavolo
                    comanda = OrdineService.get_comande_attive(tavolo['id'])
                    if comanda:
                        st.session_state.comanda_attiva_id = comanda['id']
                    st.session_state.carrello = []
                    st.rerun()
    
    st.divider()
    
    # Statistiche rapide
    col1, col2, col3 = st.columns(3)
    with col1:
        occupati = sum(1 for t in tavoli if t['stato'] == 'OCCUPATO')
        st.metric("🪑 Tavoli Occupati", occupati)
    with col2:
        liberi = sum(1 for t in tavoli if t['stato'] == 'LIBERO')
        st.metric("✅ Tavoli Liberi", liberi)
    with col3:
        conti = sum(1 for t in tavoli if t['richiesta_conto'] == 1)
        st.metric("💰 Conti Richiesti", conti)


def show_gestione_tavolo():
    """Gestione tavolo con layout a due colonne (menu a sinistra, carrello a destra)"""
    
    tavolo = st.session_state.tavolo_attivo
    
    # Header con info tavolo e azioni
    col_header1, col_header2, col_header3, col_header4 = st.columns([2, 1, 1, 1])
    
    with col_header1:
        if st.button("⬅️ TORNA ALLA MAPPA", use_container_width=True):
            st.session_state.tavolo_attivo = None
            st.session_state.carrello = []
            st.session_state.categoria_selezionata = None
            st.session_state.comanda_attiva_id = None
            st.rerun()
    
    with col_header2:
        st.markdown(f"### 🪑 Tavolo {tavolo['numero']}")
        st.caption(f"{tavolo['sala_nome']}")
    
    with col_header3:
        # Verifica comanda attiva
        comanda = OrdineService.get_comande_attive(tavolo['id'])
        if comanda:
            st.session_state.comanda_attiva_id = comanda['id']
            st.success("✅ Comanda attiva")
        else:
            st.session_state.comanda_attiva_id = None
            st.warning("🆕 Nuova comanda")
    
    with col_header4:
        # Piatti pronti per questo tavolo
        if st.session_state.get('comanda_attiva_id'):
            piatti_pronti = esegui_query("""
                SELECT COUNT(*) as cnt FROM comandine
                WHERE comanda_id = ? AND stato = 'PRONTO'
            """, (st.session_state.comanda_attiva_id,), fetchone=True)['cnt']
            
            if piatti_pronti > 0:
                st.info(f"🔔 {piatti_pronti} pronti")
    
    st.divider()
    
    # LAYOUT PRINCIPALE: DUE COLONNE
    col_menu, col_carrello = st.columns([2, 1])
    
    with col_menu:
        st.markdown("### 📖 MENU")
        show_categorie_piatti()
    
    with col_carrello:
        st.markdown("### 🛒 COMANDA IN CORSO")
        show_carrello(tavolo, comanda if 'comanda' in locals() else None)
    
    # Sezione piatti pronti (sotto le due colonne)
    if st.session_state.get('comanda_attiva_id'):
        piatti_pronti_lista = esegui_query("""
            SELECT * FROM comandine
            WHERE comanda_id = ? AND stato = 'PRONTO'
            ORDER BY timestamp_pronto
        """, (st.session_state.comanda_attiva_id,), fetchall=True)
        
        if piatti_pronti_lista:
            st.divider()
            st.markdown("### 🔔 PIATTI PRONTI DA SERVIRE")
            
            # Griglia piatti pronti
            cols = st.columns(min(len(piatti_pronti_lista), 4))
            for i, piatto in enumerate(piatti_pronti_lista):
                with cols[i % 4]:
                    with st.container(border=True):
                        st.markdown(f"**{piatto['piatto_nome']}**")
                        st.caption(f"Qtà: {piatto['qty']}")
                        if piatto.get('note'):
                            # Prova a parsare JSON per note e variazioni
                            try:
                                note_data = json.loads(piatto['note'])
                                if note_data.get('note'):
                                    st.caption(f"📝 {note_data['note']}")
                                if note_data.get('variazioni'):
                                    for v in note_data['variazioni']:
                                        st.caption(f"✨ {v['nome']}")
                            except:
                                if piatto['note'] and not piatto['note'].startswith('{'):
                                    st.caption(f"📝 {piatto['note']}")
                        
                        if st.button("✅ SERVI", key=f"servi_{piatto['id']}"):
                            OrdineService.aggiorna_stato(piatto['id'], 'SERVITO', st.session_state.user_id)
                            st.rerun()


def show_categorie_piatti():
    """Mostra categorie e piatti con selezione diretta e variazioni"""
    
    # Se nessuna categoria selezionata, mostra griglia categorie
    if st.session_state.get('categoria_selezionata') is None:
        categorie = esegui_query("""
            SELECT c.*, COUNT(p.id) as num_piatti
            FROM categorie c
            LEFT JOIN piatti p ON c.id = p.categoria_id AND p.disponibile = 1
            WHERE c.attiva = 1
            GROUP BY c.id
            ORDER BY c.ordine
        """, fetchall=True)
        
        # Griglia categorie 2 colonne
        cols = st.columns(2)
        for i, cat in enumerate(categorie):
            with cols[i % 2]:
                if st.button(
                    f"{cat.get('icona', '🍽️')} **{cat['nome']}**\n{cat['num_piatti']} piatti",
                    key=f"cat_{cat['id']}",
                    use_container_width=True
                ):
                    st.session_state.categoria_selezionata = cat
                    st.rerun()
    
    # Altrimenti mostra piatti della categoria selezionata
    else:
        cat = st.session_state.categoria_selezionata
        
        # Header categoria con pulsante indietro
        col_back, col_title = st.columns([1, 3])
        with col_back:
            if st.button("⬅️ INDIETRO", key="back_from_categories"):
                st.session_state.categoria_selezionata = None
                st.rerun()
        with col_title:
            st.markdown(f"### {cat.get('icona', '🍽️')} {cat['nome']}")
        
        # Recupera piatti della categoria
        piatti = esegui_query("""
            SELECT * FROM piatti
            WHERE categoria_id = ? AND disponibile = 1
            ORDER BY ordine, nome
        """, (cat['id'],), fetchall=True)
        
        if not piatti:
            st.info("Nessun piatto disponibile in questa categoria")
            return
        
        # Mostra piatti in griglia 2 colonne
        for i in range(0, len(piatti), 2):
            cols = st.columns(2)
            for j in range(2):
                if i + j < len(piatti):
                    piatto = piatti[i + j]
                    with cols[j]:
                        with st.container(border=True):
                            st.markdown(f"**{piatto['nome']}**")
                            st.caption(f"💰 {format_currency(piatto['prezzo'])}")
                            
                            # Variazioni (se presenti)
                            variazioni = get_variazioni_per_piatto(piatto['id'])
                            variazioni_selezionate = []
                            
                            if variazioni:
                                with st.expander("✨ Variazioni", expanded=False):
                                    for var in variazioni:
                                        if st.checkbox(
                                            f"{var['nome']} (+{format_currency(var['prezzo'])})",
                                            key=f"var_{piatto['id']}_{var['id']}_{i}_{j}"
                                        ):
                                            variazioni_selezionate.append(var)
                            
                            # Quantità
                            qty = st.number_input(
                                "Qtà",
                                min_value=1,
                                max_value=10,
                                value=1,
                                key=f"qty_{piatto['id']}_{i}_{j}",
                                label_visibility="collapsed"
                            )
                            
                            # Note
                            note = st.text_input(
                                "📝 Note",
                                placeholder="Es. senza cipolla",
                                key=f"note_{piatto['id']}_{i}_{j}",
                                label_visibility="collapsed"
                            )
                            
                            # Bottone aggiungi
                            if st.button("➕ AGGIUNGI", key=f"add_{piatto['id']}_{i}_{j}", use_container_width=True):
                                # Determina tempo consegna in base alla categoria
                                nome_cat = cat['nome'].upper()
                                if 'ANTIPASTO' in nome_cat or 'BEVANDE' in nome_cat:
                                    tempo_codice = "TEMPO1"
                                    tempo_nome = "TEMPO 1"
                                    minuti = 0
                                elif 'PRIMO' in nome_cat or 'PASTA' in nome_cat:
                                    tempo_codice = "TEMPO2"
                                    tempo_nome = "TEMPO 2"
                                    minuti = 10
                                elif 'SECONDO' in nome_cat or 'CARNE' in nome_cat:
                                    tempo_codice = "TEMPO3"
                                    tempo_nome = "TEMPO 3"
                                    minuti = 20
                                elif 'DOLCE' in nome_cat:
                                    tempo_codice = "TEMPO4"
                                    tempo_nome = "TEMPO 4"
                                    minuti = 30
                                else:
                                    tempo_codice = "TEMPO2"
                                    tempo_nome = "TEMPO 2"
                                    minuti = 10
                                
                                # Aggiungi al carrello
                                st.session_state.carrello.append({
                                    'id': piatto['id'],
                                    'nome': piatto['nome'],
                                    'prezzo': piatto['prezzo'],
                                    'qty': qty,
                                    'note': note,
                                    'variazioni': variazioni_selezionate,
                                    'tempo_codice': tempo_codice,
                                    'tempo_nome': tempo_nome,
                                    'minuti_consegna': minuti,
                                    'categoria': cat['nome']
                                })
                                st.success(f"✅ {qty}x {piatto['nome']} aggiunto!")
                                st.rerun()


def show_carrello(tavolo, comanda):
    """Carrello con tutte le funzioni: elimina, modifica, note, variazioni"""
    
    if not st.session_state.get('carrello'):
        st.info("🛒 Carrello vuoto\n\nAggiungi piatti dal menu")
        
        # Mostra piatti già ordinati se c'è una comanda attiva
        if comanda:
            piatti_ordinati = OrdineService.get_piatti_comanda(comanda['id'])
            if piatti_ordinati:
                st.markdown("---")
                st.markdown("### 📋 Piatti già ordinati")
                for p in piatti_ordinati:
                    stato_icona = {
                        'NUOVO': '🆕', 'IN_CORSO': '👨‍🍳', 
                        'PRONTO': '🔔', 'SERVITO': '✅', 'ANNULLATO': '❌'
                    }.get(p['stato'], '❓')
                    
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        with col1:
                            st.markdown(f"{stato_icona} **{p['qty']}x {p['piatto_nome']}**")
                            if p.get('note'):
                                # Prova a parsare JSON per note
                                try:
                                    note_data = json.loads(p['note'])
                                    if note_data.get('note'):
                                        st.caption(f"📝 {note_data['note']}")
                                    if note_data.get('variazioni'):
                                        for v in note_data['variazioni']:
                                            st.caption(f"✨ {v['nome']}")
                                except:
                                    st.caption(f"📝 {p['note']}")
                        with col2:
                            st.markdown(f"**{format_currency(p['prezzo_unitario'] * p['qty'])}**")
        
        return
    
    # Raggruppa carrello per evitare duplicati
    carrello_raggruppato = []
    for item in st.session_state.carrello:
        trovato = False
        for esistente in carrello_raggruppato:
            if (esistente['id'] == item['id'] and 
                esistente.get('note') == item.get('note') and
                str(esistente.get('variazioni')) == str(item.get('variazioni'))):
                esistente['qty'] += item['qty']
                trovato = True
                break
        if not trovato:
            carrello_raggruppato.append(item.copy())
    
    # Mostra carrello raggruppato
    totale = 0
    for idx, item in enumerate(carrello_raggruppato):
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.markdown(f"**{item['qty']}x {item['nome']}**")
                
                # Variazioni
                if item.get('variazioni'):
                    for v in item['variazioni']:
                        st.caption(f"  ✦ {v['nome']} (+{format_currency(v['prezzo'])})")
                
                # Note
                if item.get('note'):
                    st.caption(f"📝 {item['note']}")
                
                # Tempo
                st.caption(f"⏱️ {item.get('tempo_nome', 'TEMPO 2')}")
            
            with col2:
                # Calcola prezzo con variazioni
                prezzo_base = item['prezzo'] * item['qty']
                prezzo_variazioni = sum(v['prezzo'] * item['qty'] for v in item.get('variazioni', []))
                importo_totale = prezzo_base + prezzo_variazioni
                totale += importo_totale
                
                st.markdown(f"**{format_currency(importo_totale)}**")
            
            with col3:
                # Bottone elimina
                if st.button("🗑️", key=f"del_carrello_{idx}"):
                    # Rimuove TUTTI gli item con stessi parametri
                    nuovi = []
                    for orig in st.session_state.carrello:
                        if not (orig['id'] == item['id'] and 
                              orig.get('note') == item.get('note') and
                              str(orig.get('variazioni')) == str(item.get('variazioni'))):
                            nuovi.append(orig)
                    st.session_state.carrello = nuovi
                    st.rerun()
    
    st.markdown(f"### Totale: {format_currency(totale)}")
    
    # Bottoni azione
    col_svuota, col_invia = st.columns(2)
    
    with col_svuota:
        if st.button("🗑️ SVUOTA CARRELLO", use_container_width=True):
            st.session_state.carrello = []
            st.rerun()
    
    with col_invia:
        if st.button("🚀 INVIA IN CUCINA", type="primary", use_container_width=True):
            if not comanda:
                # Crea nuova comanda
                comanda_id = TavoloService.occupa_tavolo(tavolo['id'], st.session_state.user_id)
            else:
                comanda_id = comanda['id']
            
            # Raccogli piatti per reparto (per stampa)
            piatti_per_reparto = {}
            
            for item in st.session_state.carrello:
                # Calcola prezzo con variazioni
                prezzo_finale = item['prezzo']
                if item.get('variazioni'):
                    prezzo_finale += sum(v['prezzo'] for v in item['variazioni'])
                
                # Determina reparto
                piatto_info = esegui_query("""
                    SELECT c.reparto_id 
                    FROM piatti p
                    JOIN categorie c ON p.categoria_id = c.id
                    WHERE p.id = ?
                """, (item['id'],), fetchone=True)
                
                reparto_id = piatto_info['reparto_id'] if piatto_info else 1
                
                # Prepara note come JSON se ci sono variazioni
                note_json = json.dumps({
                    'note': item.get('note', ''),
                    'variazioni': item.get('variazioni', [])
                }) if item.get('variazioni') or item.get('note') else item.get('note', '')
                
                # Inserisci commandina
                esegui_query("""
                    INSERT INTO comandine 
                    (comanda_id, piatto_id, piatto_nome, qty, prezzo_unitario, 
                     note, stato, reparto_id, tempo_consegna, minuti_consegna)
                    VALUES (?, ?, ?, ?, ?, ?, 'NUOVO', ?, ?, ?)
                """, (
                    comanda_id, 
                    item['id'], 
                    item['nome'], 
                    item['qty'], 
                    prezzo_finale,
                    note_json, 
                    reparto_id, 
                    item.get('tempo_codice', 'TEMPO2'),
                    item.get('minuti_consegna', 10)
                ), commit=True)
                
                # Raccogli per stampa
                if reparto_id not in piatti_per_reparto:
                    piatti_per_reparto[reparto_id] = []
                
                piatti_per_reparto[reparto_id].append({
                    'piatto_nome': f"{item['nome']}" + (f" (con variazioni)" if item.get('variazioni') else ""),
                    'qty': item['qty'],
                    'note': note_json
                })
            
            # Stampa automatica
            try:
                from db import StampanteService
                for reparto_id, piatti in piatti_per_reparto.items():
                    StampanteService.stampa_comanda(comanda_id, reparto_id, piatti)
            except Exception as e:
                st.warning(f"⚠️ Stampa non disponibile: {e}")
            
            st.success("✅ Ordine inviato in cucina!")
            
            # SVUOTA CARRELLO E TORNA ALLA MAPPA
            st.session_state.carrello = []
            st.session_state.categoria_selezionata = None
            st.session_state.tavolo_attivo = None
            st.session_state.comanda_attiva_id = None
            
            st.info("🔄 Reindirizzamento alla sala...")
            time.sleep(2)
            st.rerun()


def show_storico_comanda(comanda):
    """Mostra storico piatti della comanda"""
    
    if not comanda:
        st.info("Nessuna comanda attiva")
        return
    
    tavolo_id = comanda['tavolo_id']
    piatti = OrdineService.get_piatti_comanda(comanda['id'])
    
    if not piatti:
        st.warning("Nessun piatto in questa comanda")
        
        if st.button("🗑️ CHIUDI COMANDA VUOTA", key="chiudi_comanda_vuota"):
            esegui_query("UPDATE comande SET stato = 'CHIUSA' WHERE id = ?", 
                        (comanda['id'],), commit=True)
            TavoloService.libera_tavolo(tavolo_id)
            st.success("✅ Tavolo liberato!")
            st.session_state.tavolo_attivo = None
            st.session_state.comanda_attiva_id = None
            st.rerun()
        return
    
    totali = {'NUOVO': 0, 'IN_CORSO': 0, 'PRONTO': 0, 'SERVITO': 0, 'ANNULLATO': 0}
    for p in piatti:
        totali[p['stato']] += p['qty']
    
    piatti_attivi = totali['NUOVO'] + totali['IN_CORSO'] + totali['PRONTO']
    
    cols = st.columns(5)
    with cols[0]: st.metric("🆕 Nuovi", totali['NUOVO'])
    with cols[1]: st.metric("👨‍🍳 In corso", totali['IN_CORSO'])
    with cols[2]: st.metric("🔔 Pronti", totali['PRONTO'])
    with cols[3]: st.metric("✅ Serviti", totali['SERVITO'])
    with cols[4]: st.metric("❌ Annullati", totali['ANNULLATO'])
    
    st.divider()
    
    for p in piatti:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            
            with col1:
                st.markdown(f"**{p['qty']}x {p['piatto_nome']}**")
                if p['note']:
                    # Prova a parsare JSON per note
                    try:
                        note_data = json.loads(p['note'])
                        if note_data.get('note'):
                            st.caption(f"📝 {note_data['note']}")
                        if note_data.get('variazioni'):
                            for v in note_data['variazioni']:
                                st.caption(f"  ✦ {v['nome']}")
                    except:
                        st.caption(f"📝 {p['note']}")
            
            with col2:
                colore = get_stato_colore(p['stato'])
                icona = get_stato_icona(p['stato'])
                st.markdown(f"<span style='color:{colore}'>{icona}</span>", unsafe_allow_html=True)
            
            with col3:
                st.markdown(format_currency(p['prezzo_unitario'] * p['qty']))
            
            with col4:
                if p['stato'] in ['NUOVO', 'IN_CORSO']:
                    if st.button("❌", key=f"annulla_{p['id']}"):
                        OrdineService.aggiorna_stato(p['id'], 'ANNULLATO', st.session_state.user_id)
                        st.rerun()
                elif p['stato'] == 'PRONTO':
                    if st.button("✅", key=f"servi_{p['id']}"):
                        OrdineService.aggiorna_stato(p['id'], 'SERVITO', st.session_state.user_id)
                        st.rerun()
    
    st.divider()
    
    if piatti_attivi == 0 and totali['SERVITO'] > 0:
        st.success("✅ Tutti i piatti sono stati serviti!")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if st.button("📄 PRECONTO", key=f"preconto_storico_{comanda['id']}"):
                brand = esegui_query("SELECT * FROM brand WHERE id = 1", fetchone=True)
                preconto_html, totale = genera_preconto(comanda['id'], brand, "PRECONTO")
                st.session_state.preconto_html = preconto_html
                st.session_state.preconto_show = True
                st.session_state.preconto_comanda_id = comanda['id']
                st.rerun()
        
        with col2:
            if st.button("💰 RICHIEDI CONTO", key="richiedi_conto", type="primary", use_container_width=True):
                success, msg = PagamentoService.richiedi_conto(tavolo_id)
                if success:
                    try:
                        from db import OrdineService
                        OrdineService.archivia_comanda(comanda['id'])
                    except Exception as e:
                        write_debug(f"❌ Errore archiviazione: {e}")
                    
                    st.success("✅ Conto richiesto!")
                    st.session_state.tavolo_attivo = None
                    st.session_state.comanda_attiva_id = None
                    st.rerun()
                else:
                    st.error(msg)
        
        with col3:
            if st.button("🔄 LIBERA TAVOLO", key="libera_tavolo", use_container_width=True):
                try:
                    from db import OrdineService
                    OrdineService.archivia_comanda(comanda['id'])
                except Exception as e:
                    write_debug(f"❌ Errore archiviazione: {e}")
                
                TavoloService.libera_tavolo(tavolo_id)
                esegui_query("UPDATE comande SET stato = 'CHIUSA' WHERE id = ?", 
                            (comanda['id'],), commit=True)
                st.success("✅ Tavolo liberato!")
                st.session_state.tavolo_attivo = None
                st.session_state.comanda_attiva_id = None
                st.rerun()
    
    elif piatti_attivi == 0 and totali['SERVITO'] == 0 and totali['ANNULLATO'] > 0:
        st.warning("⚠️ Tutti i piatti sono stati annullati")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("📄 PRECONTO", key=f"preconto_annullato_{comanda['id']}"):
                brand = esegui_query("SELECT * FROM brand WHERE id = 1", fetchone=True)
                preconto_html, totale = genera_preconto(comanda['id'], brand, "PRECONTO")
                st.session_state.preconto_html = preconto_html
                st.session_state.preconto_show = True
                st.session_state.preconto_comanda_id = comanda['id']
                st.rerun()
        
        with col2:
            if st.button("🗑️ CHIUDI TAVOLO", key="chiudi_tavolo", type="primary", use_container_width=True):
                try:
                    from db import OrdineService
                    OrdineService.archivia_comanda(comanda['id'])
                except Exception as e:
                    write_debug(f"❌ Errore archiviazione: {e}")
                
                esegui_query("UPDATE comande SET stato = 'ANNULLATA' WHERE id = ?", 
                            (comanda['id'],), commit=True)
                TavoloService.libera_tavolo(tavolo_id)
                st.success("✅ Tavolo liberato!")
                st.session_state.tavolo_attivo = None
                st.session_state.comanda_attiva_id = None
                st.rerun()


def show_reparto(reparto_nome, reparto_id, mostra_tutti=False):
    """Visualizzazione comande per reparto"""
    
    st.title(f"{reparto_nome}")
    
    col1, col2 = st.columns(2)
    with col1:
        filtro_stato = st.selectbox(
            "Stato",
            ["TUTTI", "NUOVO", "IN_CORSO", "PRONTO"],
            key=f"filtro_{reparto_nome}"
        )
    with col2:
        filtro_tempo = st.selectbox(
            "Tempo",
            ["TUTTI", "TEMPO 1", "TEMPO 2", "TEMPO 3", "TEMPO 4"],
            key=f"filtro_tempo_{reparto_nome}"
        )
    
    if mostra_tutti:
        query = """
            SELECT 
                cmd.id as commandina_id,
                cmd.comanda_id,
                cmd.piatto_nome,
                cmd.qty,
                cmd.note,
                cmd.stato,
                cmd.tempo_consegna,
                cmd.minuti_consegna,
                cmd.reparto_id,
                cmd.timestamp_inserimento,
                t.numero as tavolo_numero,
                s.nome as sala_nome,
                r.nome as reparto_nome,
                r.icona as reparto_icona,
                u.nome as cameriere_nome
            FROM comandine cmd
            JOIN comande c ON cmd.comanda_id = c.id
            JOIN tavoli t ON c.tavolo_id = t.id
            JOIN sale s ON t.sala_id = s.id
            JOIN reparti r ON cmd.reparto_id = r.id
            LEFT JOIN utenti u ON c.cameriere_id = u.id
            WHERE 1=1
        """
        params = []
    else:
        query = """
            SELECT 
                cmd.id as commandina_id,
                cmd.comanda_id,
                cmd.piatto_nome,
                cmd.qty,
                cmd.note,
                cmd.stato,
                cmd.tempo_consegna,
                cmd.minuti_consegna,
                cmd.reparto_id,
                cmd.timestamp_inserimento,
                t.numero as tavolo_numero,
                s.nome as sala_nome,
                r.nome as reparto_nome,
                r.icona as reparto_icona,
                u.nome as cameriere_nome
            FROM comandine cmd
            JOIN comande c ON cmd.comanda_id = c.id
            JOIN tavoli t ON c.tavolo_id = t.id
            JOIN sale s ON t.sala_id = s.id
            JOIN reparti r ON cmd.reparto_id = r.id
            LEFT JOIN utenti u ON c.cameriere_id = u.id
            WHERE cmd.reparto_id = ?
        """
        params = [reparto_id]
    
    if filtro_stato != "TUTTI":
        query += " AND cmd.stato = ?"
        params.append(filtro_stato)
    
    if filtro_tempo != "TUTTI":
        tempo_db = filtro_tempo.replace(" ", "")
        query += " AND cmd.tempo_consegna = ?"
        params.append(tempo_db)
    
    query += " ORDER BY cmd.timestamp_inserimento DESC"
    
    comande = esegui_query(query, tuple(params), fetchall=True)
    
    if not comande:
        st.success(f"🎉 Nessuna comanda in attesa per {reparto_nome}!")
        return
    
    st.metric("📋 Totale piatti", len(comande))
    st.divider()
    
    for cmd in comande:
        with st.container(border=True):
            col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
            
            with col1:
                st.markdown(f"**Tavolo {cmd['tavolo_numero']} - {cmd['sala_nome']}**")
                st.markdown(f"{cmd['qty']}x {cmd['piatto_nome']}")
                if cmd['note']:
                    # Prova a parsare JSON per note
                    try:
                        note_data = json.loads(cmd['note'])
                        if note_data.get('note'):
                            st.caption(f"📝 {note_data['note']}")
                        if note_data.get('variazioni'):
                            for v in note_data['variazioni']:
                                st.caption(f"  ✦ {v['nome']}")
                    except:
                        st.caption(f"📝 {cmd['note']}")
            
            with col2:
                stato_icone = {
                    'NUOVO': '🆕', 'IN_CORSO': '👨‍🍳', 
                    'PRONTO': '🔔', 'SERVITO': '✅', 'ANNULLATO': '❌'
                }
                st.markdown(stato_icone.get(cmd['stato'], '❓'))
            
            with col3:
                tempo_mostra = {
                    "TEMPO1": "⚡1", "TEMPO2": "⏱️2", 
                    "TEMPO3": "📅3", "TEMPO4": "🎂4"
                }.get(cmd['tempo_consegna'], cmd['tempo_consegna'] or '⏱️2')
                st.markdown(tempo_mostra)
            
            with col4:
                if cmd.get('minuti_consegna', 0) > 0:
                    st.markdown(f"{cmd['minuti_consegna']}min")
            
            with col5:
                if cmd['stato'] == 'NUOVO':
                    if st.button("👨‍🍳", key=f"prendi_{cmd['commandina_id']}"):
                        OrdineService.aggiorna_stato(cmd['commandina_id'], 'IN_CORSO', st.session_state.user_id)
                        st.rerun()
                elif cmd['stato'] == 'IN_CORSO':
                    if st.button("🔔", key=f"pronto_{cmd['commandina_id']}"):
                        OrdineService.aggiorna_stato(cmd['commandina_id'], 'PRONTO', st.session_state.user_id)
                        st.rerun()


def show_ricetta_piatto(piatto_id):
    """Mostra la ricetta segreta (solo per staff autorizzato)"""
    
    if st.session_state.user_role not in ['SUPERADMIN', 'ADMIN', 'CUCINA', 'BAR']:
        st.error("⛔ Accesso negato")
        return
    
    piatto = esegui_query("SELECT * FROM piatti WHERE id = ?", (piatto_id,), fetchone=True)
    
    if not piatto or not piatto.get('descrizione_privata'):
        st.info("Nessuna ricetta disponibile")
        return
    
    try:
        ricetta = json.loads(piatto['descrizione_privata'])
        
        with st.expander(f"📖 Ricetta: {piatto['nome']}", expanded=True):
            col1, col2 = st.columns(2)
            
            with col1:
                if piatto.get('foto_data'):
                    st.image(piatto['foto_data'], width=200)
                st.markdown(f"**💰 Prezzo:** {format_currency(piatto['prezzo'])}")
                st.markdown(f"**⏱️ Tempo:** {piatto['tempo_preparazione']} min")
            
            with col2:
                st.markdown("### 🥗 Ingredienti")
                st.write(ricetta.get('ingredienti', 'N/A'))
            
            st.divider()
            st.markdown("### 👨‍🍳 Preparazione")
            st.write(ricetta.get('preparazione', 'N/A'))
            st.markdown("### 📝 Note")
            st.write(ricetta.get('note_cucina', 'N/A'))
            
            if ricetta.get('allergeni'):
                st.warning(f"⚠️ Allergeni: {', '.join(ricetta['allergeni'])}")
                
    except Exception as e:
        st.error(f"Errore nel caricamento della ricetta: {e}")

# ============================================================================
# GESTIONE PRE-ORDINI CLIENTI
# ============================================================================
def show_preordini():
    st.title("📋 Pre-ordini Clienti")
    
    # ============================================================================
    # DEBUG DIRETTO SUL DATABASE (SENZA JOIN)
    # ============================================================================
    with st.expander("🔍 DEBUG DATABASE RAW", expanded=True):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # 1. Quanti record in preordini?
            cursor.execute("SELECT COUNT(*) FROM preordini")
            count = cursor.fetchone()[0]
            st.write(f"📊 **Record in preordini:** {count}")
            
            # 2. Mostra TUTTI i record con i campi grezzi
            cursor.execute("SELECT id, tavolo_id, stato, note, timestamp_creazione FROM preordini ORDER BY id DESC")
            records = cursor.fetchall()
            
            if records:
                st.write("**📋 Contenuto tabella preordini:**")
                for r in records:
                    st.write(f"   • ID:{r[0]}, Tavolo:{r[1]}, Stato:'{r[2]}', Note:'{r[3]}', Data:{r[4]}")
            else:
                st.warning("⚠️ Nessun record in preordini")
            
            # 3. Controlla se ci sono tavoli
            cursor.execute("SELECT COUNT(*) FROM tavoli")
            tavoli_count = cursor.fetchone()[0]
            st.write(f"🪑 **Tavoli nel database:** {tavoli_count}")
            
            if tavoli_count > 0:
                cursor.execute("SELECT id, numero FROM tavoli LIMIT 5")
                tavoli = cursor.fetchall()
                st.write("**Primi 5 tavoli:**")
                for t in tavoli:
                    st.write(f"   • ID:{t[0]}, Numero:{t[1]}")
            
            conn.close()
            
        except Exception as e:
            st.error(f"❌ Errore debug: {e}")
    
    # ============================================================================
    # DEBUG - Verifica database (COMPATTO)
    # ============================================================================
    with st.expander("🔍 DEBUG DATABASE", expanded=False):
        try:
            # Mostra il percorso del database
            st.write(f"📦 **Database path:** {DB_PATH}")
            
            # Verifica se la tabella esiste
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='preordini'")
            if cursor.fetchone():
                st.success("✅ Tabella 'preordini' esiste")
                
                # Conta i record per stato
                cursor.execute("SELECT stato, COUNT(*) as cnt FROM preordini GROUP BY stato")
                records = cursor.fetchall()
                
                if records:
                    st.markdown("##### 📊 Pre-ordini per stato:")
                    for r in records:
                        st.write(f"  • {r[0]}: {r[1]}")
                else:
                    st.warning("⚠️ Nessun record in 'preordini'")
                    
                # Mostra ID dei record recenti
                cursor.execute("""
                    SELECT id, tavolo_id, stato, timestamp_creazione 
                    FROM preordini 
                    ORDER BY id DESC LIMIT 3
                """)
                recenti = cursor.fetchall()
                if recenti:
                    st.markdown("##### 🔄 Ultimi 3 pre-ordini:")
                    for r in recenti:
                        st.write(f"  • ID:{r[0]}, Tav:{r[1]}, {r[2]}, {r[3]}")
            else:
                st.error("❌ Tabella 'preordini' NON esiste!")
            
            conn.close()
            
        except Exception as e:
            st.error(f"❌ Errore nel debug: {e}")
    
    # ============================================================================
    # TABS principali
    # ============================================================================
    tab_attesa, tab_revisione, tab_storico = st.tabs(["⏳ IN ATTESA", "👀 DA REVISIONARE", "📜 STORICO"])
    
    with tab_attesa:
        show_preordini_stato('IN_ATTESA')
    with tab_revisione:
        show_preordini_stato('REVISIONATO')
    with tab_storico:
        show_preordini_storico()


def show_preordini_stato(stato):
    """Mostra i pre-ordini con un determinato stato"""
    
    # DEBUG: mostra cosa stiamo cercando
    st.caption(f"🔍 Ricerca pre-ordini con stato: **{stato}**")
    
    # DEBUG AGGIUNTIVO - Conta totale record
    totale = esegui_query("SELECT COUNT(*) as cnt FROM preordini", fetchone=True)
    st.write(f"📊 **Totale record in preordini:** {totale['cnt'] if totale else 0}")
    
    # DEBUG - Mostra tutti gli stati
    stati = esegui_query("SELECT stato, COUNT(*) as cnt FROM preordini GROUP BY stato", fetchall=True)
    if stati:
        st.write("📋 **Stati presenti:**")
        for s in stati:
            st.write(f"   • {s['stato']}: {s['cnt']}")
    
    # Recupera i pre-ordini con quel stato - USA LEFT JOIN per robustezza
    preordini = esegui_query("""
        SELECT p.*, 
               COALESCE(t.numero, '?') as tavolo_numero, 
               COALESCE(s.nome, 'Sala sconosciuta') as sala_nome
        FROM preordini p
        LEFT JOIN tavoli t ON p.tavolo_id = t.id
        LEFT JOIN sale s ON t.sala_id = s.id
        WHERE p.stato = ?
        ORDER BY p.timestamp_creazione DESC
    """, (stato,), fetchall=True)
    
    st.write(f"🔎 **Risultati query:** {len(preordini)} pre-ordini trovati")
    
    if not preordini:
        st.info(f"📭 Nessun pre-ordine con stato '{stato}'")
        return
    
    st.success(f"✅ Trovati {len(preordini)} pre-ordini con stato '{stato}'")
    
    for pre in preordini:
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"**🪑 Tavolo {pre['tavolo_numero']} - {pre['sala_nome']}** (ID: {pre['id']})")
                
                # Gestione data
                if pre['timestamp_creazione']:
                    if hasattr(pre['timestamp_creazione'], 'strftime'):
                        data_ora = pre['timestamp_creazione'].strftime('%d/%m/%Y %H:%M')
                    else:
                        data_ora = str(pre['timestamp_creazione'])[:16]
                else:
                    data_ora = 'N/A'
                st.caption(f"🕐 {data_ora}")
                
                if pre['note']:
                    st.caption(f"📝 {pre['note']}")
            
            with col2:
                # Recupera i dettagli per il totale
                dettagli = esegui_query("SELECT * FROM preordini_dettaglio WHERE preordine_id = ?", 
                                        (pre['id'],), fetchall=True)
                totale = sum(d['qty'] * d['prezzo_unitario'] for d in dettagli) if dettagli else 0
                st.metric("💰 Totale", format_currency(totale))
                st.caption(f"{len(dettagli) if dettagli else 0} piatti")
            
            with col3:
                if stato == 'IN_ATTESA':
                    if st.button("👀 REVISIONA", key=f"rev_{pre['id']}"):
                        st.session_state.preordine_id_da_revisionare = pre['id']
                        st.session_state.tavolo_numero_da_revisionare = pre['tavolo_numero']
                        st.session_state.sala_nome_da_revisionare = pre['sala_nome']
                        st.rerun()
                elif stato == 'REVISIONATO':
                    if st.button("✅ CONFERMA", key=f"conf_{pre['id']}"):
                        conferma_preordine(pre['id'])
                        st.rerun()
            
            # Mostra i piatti dell'ordine
            st.markdown("---")
            st.markdown("##### 🍽️ Piatti ordinati:")
            
            # Recupera i dettagli se non l'hai già fatto
            if 'dettagli' not in locals() or not dettagli:
                dettagli = esegui_query("SELECT * FROM preordini_dettaglio WHERE preordine_id = ?", 
                                        (pre['id'],), fetchall=True)
            
            if dettagli:
                for d in dettagli:
                    cols = st.columns([4, 1, 2])
                    with cols[0]:
                        st.markdown(f"**{d['qty']}x {d['piatto_nome']}**")
                    with cols[1]:
                        st.markdown(f"€{d['prezzo_unitario']:.2f}")
                    with cols[2]:
                        st.markdown(f"**€{d['qty'] * d['prezzo_unitario']:.2f}**")
                    
                    # Mostra note del piatto
                    if d.get('note') and d['note'] not in ['[]', '{}', '']:
                        st.caption(f"  📝 {d['note']}")
            else:
                st.caption("Nessun dettaglio disponibile")


def show_preordini_storico():
    """Mostra storico pre-ordini"""
    
    preordini = esegui_query("""
        SELECT p.*, t.numero as tavolo_numero, s.nome as sala_nome, u.username as cameriere
        FROM preordini p
        JOIN tavoli t ON p.tavolo_id = t.id
        JOIN sale s ON t.sala_id = s.id
        LEFT JOIN utenti u ON p.cameriere_id = u.id
        WHERE p.timestamp_creazione >= date('now', '-30 days')
        ORDER BY p.timestamp_creazione DESC
        LIMIT 50
    """, fetchall=True)
    
    if not preordini:
        st.info("Nessun pre-ordine nello storico")
        return
    
    st.caption(f"📊 Mostrati {len(preordini)} pre-ordini degli ultimi 30 giorni")
    
    for pre in preordini:
        # Formatta la data in modo leggibile
        if pre['timestamp_creazione']:
            if hasattr(pre['timestamp_creazione'], 'strftime'):
                data_ora = pre['timestamp_creazione'].strftime('%d/%m/%Y %H:%M')
            else:
                data_ora = str(pre['timestamp_creazione'])[:16]
        else:
            data_ora = 'N/A'
            
        with st.expander(f"📅 {data_ora} - Tavolo {pre['tavolo_numero']} - {pre['stato']}"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Stato:** {pre['stato']}")
                if pre.get('cameriere'):
                    st.write(f"**Gestito da:** {pre['cameriere']}")
                if pre.get('note'):
                    st.write(f"**Note:** {pre['note']}")
            
            with col2:
                # Recupera dettagli
                dettagli = esegui_query("""
                    SELECT * FROM preordini_dettaglio
                    WHERE preordine_id = ?
                """, (pre['id'],), fetchall=True)
                
                totale = sum(d['qty'] * d['prezzo_unitario'] for d in dettagli)
                st.metric("💰 Totale", format_currency(totale))
                st.caption(f"{len(dettagli)} piatti")
            
            # Mostra dettaglio piatti
            with st.expander("📋 Dettaglio piatti", expanded=False):
                for d in dettagli:
                    st.caption(f"  • {d['qty']}x {d['piatto_nome']} - {format_currency(d['prezzo_unitario'] * d['qty'])}")
                    if d.get('variazioni') and d['variazioni'] not in ['[]', '{}', '']:
                        try:
                            var = json.loads(d['variazioni'])
                            for v in var:
                                st.caption(f"    ✦ {v.get('nome', '')} (+{format_currency(v.get('prezzo', 0))})")
                        except:
                            pass


def show_revisione_preordine():
    """Mostra dettaglio pre-ordine per revisione con possibilità di modifica"""
    
    # Verifica che abbiamo l'ID del pre-ordine da revisionare
    if 'preordine_id_da_revisionare' not in st.session_state:
        st.info("Nessun pre-ordine selezionato")
        return
    
    preordine_id = st.session_state.preordine_id_da_revisionare
    tavolo_numero = st.session_state.get('tavolo_numero_da_revisionare', 'N/A')
    sala_nome = st.session_state.get('sala_nome_da_revisionare', '')
    
    st.caption(f"🔍 Revisione pre-ordine ID: {preordine_id}")
    
    # Recupera i dati del pre-ordine dal database
    pre = esegui_query("""
        SELECT * FROM preordini WHERE id = ?
    """, (preordine_id,), fetchone=True)
    
    if not pre:
        st.error("Pre-ordine non trovato")
        # Pulisci lo stato
        del st.session_state.preordine_id_da_revisionare
        if 'tavolo_numero_da_revisionare' in st.session_state:
            del st.session_state.tavolo_numero_da_revisionare
        return
    
    st.title(f"📋 Revisione Ordine - Tavolo {tavolo_numero} {f'- {sala_nome}' if sala_nome else ''}")
    
    # Header con info
    col_back, col_info = st.columns([1, 3])
    with col_back:
        if st.button("⬅️ Indietro"):
            del st.session_state.preordine_id_da_revisionare
            if 'tavolo_numero_da_revisionare' in st.session_state:
                del st.session_state.tavolo_numero_da_revisionare
            if 'rev_carrello' in st.session_state:
                del st.session_state.rev_carrello
            if 'rev_cat_selezionata' in st.session_state:
                del st.session_state.rev_cat_selezionata
            st.rerun()
    
    with col_info:
        if pre.get('timestamp_creazione'):
            if hasattr(pre['timestamp_creazione'], 'strftime'):
                data_ora = pre['timestamp_creazione'].strftime('%d/%m/%Y %H:%M')
            else:
                data_ora = str(pre['timestamp_creazione'])[:16]
        else:
            data_ora = 'N/A'
        st.caption(f"Ricevuto: {data_ora}")
        
        if pre.get('note'):
            st.info(f"📝 Note cliente: {pre['note']}")
    
    st.divider()
    
    # Recupera dettagli originali
    dettagli = esegui_query("""
        SELECT * FROM preordini_dettaglio
        WHERE preordine_id = ?
    """, (preordine_id,), fetchall=True)
    
    # Inizializza carrello di revisione se non esiste
    if 'rev_carrello' not in st.session_state:
        st.session_state.rev_carrello = []
        for d in dettagli:
            # Parsing variazioni
            variazioni = []
            if d.get('variazioni') and d['variazioni'] not in ['[]', '{}', '']:
                try:
                    variazioni = json.loads(d['variazioni'])
                except:
                    variazioni = []
            
            st.session_state.rev_carrello.append({
                'id': d['piatto_id'],
                'nome': d['piatto_nome'],
                'prezzo': d['prezzo_unitario'],
                'qty': d['qty'],
                'variazioni': variazioni,
                'note': d.get('note', ''),
                'originale': True
            })
    
    # Layout a due colonne: menu a sinistra, carrello a destra
    col_menu, col_carrello = st.columns([2, 1])
    
    with col_menu:
        st.markdown("### 📖 Aggiungi Piatti")
        
        # Selezione categoria
        categorie = esegui_query("""
            SELECT c.*, COUNT(p.id) as num_piatti
            FROM categorie c
            LEFT JOIN piatti p ON c.id = p.categoria_id AND p.disponibile = 1
            WHERE c.attiva = 1
            GROUP BY c.id
            ORDER BY c.ordine
        """, fetchall=True)
        
        # Griglia categorie
        cols = st.columns(3)
        for i, cat in enumerate(categorie):
            with cols[i % 3]:
                if st.button(
                    f"{cat.get('icona', '🍽️')} {cat['nome']}",
                    key=f"rev_cat_{cat['id']}",
                    use_container_width=True
                ):
                    st.session_state.rev_cat_selezionata = cat
                    st.rerun()
        
        # Mostra piatti della categoria selezionata
        if 'rev_cat_selezionata' in st.session_state:
            cat = st.session_state.rev_cat_selezionata
            
            col_back_cat, col_title_cat = st.columns([1, 3])
            with col_back_cat:
                if st.button("⬅️ Categorie", key="back_to_rev_cats"):
                    del st.session_state.rev_cat_selezionata
                    st.rerun()
            with col_title_cat:
                st.markdown(f"### {cat.get('icona', '🍽️')} {cat['nome']}")
            
            # Recupera piatti
            piatti = esegui_query("""
                SELECT * FROM piatti
                WHERE categoria_id = ? AND disponibile = 1
                ORDER BY nome
            """, (cat['id'],), fetchall=True)
            
            if piatti:
                cols = st.columns(2)
                for i, piatto in enumerate(piatti):
                    with cols[i % 2]:
                        with st.container(border=True):
                            st.markdown(f"**{piatto['nome']}**")
                            st.caption(f"💰 {format_currency(piatto['prezzo'])}")
                            
                            # Quantità
                            qty = st.number_input(
                                "Qtà",
                                min_value=1,
                                max_value=10,
                                value=1,
                                key=f"rev_qty_{piatto['id']}",
                                label_visibility="collapsed"
                            )
                            
                            # Variazioni
                            variazioni = get_variazioni_per_piatto(piatto['id'])
                            variazioni_selezionate = []
                            
                            if variazioni:
                                with st.expander("✨ Variazioni"):
                                    for var in variazioni:
                                        if st.checkbox(
                                            f"{var['nome']} (+{format_currency(var['prezzo'])})",
                                            key=f"rev_var_{piatto['id']}_{var['id']}"
                                        ):
                                            variazioni_selezionate.append(var)
                            
                            # Bottone aggiungi
                            if st.button("➕ Aggiungi", key=f"rev_add_{piatto['id']}"):
                                st.session_state.rev_carrello.append({
                                    'id': piatto['id'],
                                    'nome': piatto['nome'],
                                    'prezzo': piatto['prezzo'],
                                    'qty': qty,
                                    'variazioni': variazioni_selezionate,
                                    'note': '',
                                    'originale': False
                                })
                                st.rerun()
    
    with col_carrello:
        st.markdown("### 🛒 Ordine da Revisionare")
        
        if not st.session_state.rev_carrello:
            st.info("Carrello vuoto")
        else:
            totale = 0
            for idx, item in enumerate(st.session_state.rev_carrello):
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    
                    with col1:
                        if item.get('originale'):
                            st.markdown(f"**{item['qty']}x {item['nome']}** 📝")
                        else:
                            st.markdown(f"**{item['qty']}x {item['nome']}** ➕")
                        
                        if item.get('variazioni'):
                            for v in item['variazioni']:
                                st.caption(f"  ✦ {v['nome']} (+{format_currency(v['prezzo'])})")
                        if item.get('note'):
                            st.caption(f"📝 {item['note']}")
                    
                    with col2:
                        importo = item['prezzo'] * item['qty']
                        if item.get('variazioni'):
                            importo += sum(v['prezzo'] * item['qty'] for v in item['variazioni'])
                        st.markdown(f"**{format_currency(importo)}**")
                        totale += importo
                    
                    with col3:
                        if st.button("🗑️", key=f"rev_del_{idx}"):
                            st.session_state.rev_carrello.pop(idx)
                            st.rerun()
            
            st.markdown(f"### Totale: {format_currency(totale)}")
            
            st.divider()
            
            # Bottoni azione
            col_conf, col_annulla = st.columns(2)
            
            with col_conf:
                if st.button("✅ CONFERMA ORDINE", type="primary", use_container_width=True):
                    # Crea la comanda definitiva
                    tavolo_id = pre['tavolo_id']
                    comanda_id = TavoloService.occupa_tavolo(tavolo_id, st.session_state.user_id)
                    
                    # Raccogli piatti per reparto
                    piatti_per_reparto = {}
                    
                    for item in st.session_state.rev_carrello:
                        # Calcola prezzo con variazioni
                        prezzo_finale = item['prezzo']
                        if item.get('variazioni'):
                            prezzo_finale += sum(v['prezzo'] for v in item['variazioni'])
                        
                        # Determina reparto
                        piatto_info = esegui_query("""
                            SELECT c.reparto_id 
                            FROM piatti p
                            JOIN categorie c ON p.categoria_id = c.id
                            WHERE p.id = ?
                        """, (item['id'],), fetchone=True)
                        
                        reparto_id = piatto_info['reparto_id'] if piatto_info else 1
                        
                        # Salva nel database
                        variazioni_json = json.dumps(item.get('variazioni', []))
                        esegui_query("""
                            INSERT INTO comandine 
                            (comanda_id, piatto_id, piatto_nome, qty, prezzo_unitario, 
                             note, stato, reparto_id, tempo_consegna, minuti_consegna)
                            VALUES (?, ?, ?, ?, ?, ?, 'NUOVO', ?, ?, ?)
                        """, (
                            comanda_id, item['id'], item['nome'], item['qty'], prezzo_finale,
                            variazioni_json, reparto_id, 'TEMPO2', 10
                        ), commit=True)
                        
                        # Raccogli per stampa
                        if reparto_id not in piatti_per_reparto:
                            piatti_per_reparto[reparto_id] = []
                        
                        piatti_per_reparto[reparto_id].append({
                            'piatto_nome': f"{item['nome']}" + (f" (con variazioni)" if item.get('variazioni') else ""),
                            'qty': item['qty'],
                            'note': variazioni_json
                        })
                    
                    # Stampa automatica
                    try:
                        from db import StampanteService
                        for reparto_id, piatti in piatti_per_reparto.items():
                            StampanteService.stampa_comanda(comanda_id, reparto_id, piatti)
                            st.success(f"🖨️ Comanda inviata al reparto {reparto_id}")
                    except Exception as e:
                        st.warning(f"⚠️ Stampa non disponibile: {e}")
                    
                    # Aggiorna stato pre-ordine
                    esegui_query("""
                        UPDATE preordini 
                        SET stato = 'CONFERMATO', cameriere_id = ?, timestamp_revisione = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (st.session_state.user_id, pre['id']), commit=True)
                    
                    # Archivia la comanda nello storico (già creata)
                    try:
                        from db import OrdineService
                        OrdineService.archivia_comanda(comanda_id)
                        write_debug(f"✅ Comanda {comanda_id} archiviata da pre-ordine")
                    except Exception as e:
                        write_debug(f"❌ Errore archiviazione pre-ordine: {e}")
                    
                    st.success("✅ Ordine confermato e inviato ai reparti!")
                    st.balloons()
                    # Pulisci TUTTE le variabili di sessione correlate
                    if 'preordine_id_da_revisionare' in st.session_state:
                        del st.session_state.preordine_id_da_revisionare
                    if 'tavolo_numero_da_revisionare' in st.session_state:
                        del st.session_state.tavolo_numero_da_revisionare
                    if 'rev_carrello' in st.session_state:
                        del st.session_state.rev_carrello
                    if 'rev_cat_selezionata' in st.session_state:
                        del st.session_state.rev_cat_selezionata
                    time.sleep(3)
                    st.rerun()
            
            with col_annulla:
                if st.button("❌ ANNULLA ORDINE", use_container_width=True):
                    esegui_query("UPDATE preordini SET stato = 'ANNULLATO' WHERE id = ?", 
                                (pre['id'],), commit=True)
                    # Pulisci TUTTE le variabili di sessione correlate
                    if 'preordine_id_da_revisionare' in st.session_state:
                        del st.session_state.preordine_id_da_revisionare
                    if 'tavolo_numero_da_revisionare' in st.session_state:
                        del st.session_state.tavolo_numero_da_revisionare
                    if 'rev_carrello' in st.session_state:
                        del st.session_state.rev_carrello
                    if 'rev_cat_selezionata' in st.session_state:
                        del st.session_state.rev_cat_selezionata
                    st.rerun()

 # ============================================================================
# FASE 3 - GESTIONE PROMEMORIA CLIENTI CON TEMPI (PER CAMERIERI)
# ============================================================================
def mostra_promemoria_clienti():
    """Visualizza tutti i promemoria dei clienti con i tempi di servizio"""
    st.title("📋 Promemoria Clienti")
    
    # Recupera tutti i pre-ordini in attesa
    preordini = esegui_query("""
        SELECT p.*, t.numero as tavolo_numero, s.nome as sala_nome
        FROM preordini p
        JOIN tavoli t ON p.tavolo_id = t.id
        JOIN sale s ON t.sala_id = s.id
        WHERE p.stato = 'IN_ATTESA'
        ORDER BY p.timestamp_creazione DESC
    """, fetchall=True)
    
    if not preordini:
        st.info("📭 Nessun promemoria cliente in attesa")
        return
    
    for pre in preordini:
        with st.container(border=True):
            # Header del promemoria
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"### 🪑 Tavolo {pre['tavolo_numero']} - {pre['sala_nome']}")
                if pre['timestamp_creazione']:
                    data_ora = pre['timestamp_creazione'].strftime('%d/%m/%Y %H:%M') if hasattr(pre['timestamp_creazione'], 'strftime') else str(pre['timestamp_creazione'])[:16]
                    st.caption(f"🕐 Ricevuto: {data_ora}")
            
            with col2:
                # Recupera dettagli
                dettagli = esegui_query("""
                    SELECT * FROM preordini_dettaglio 
                    WHERE preordine_id = ? 
                    ORDER BY posizione
                """, (pre['id'],), fetchall=True)
                
                totale = sum(d['qty'] * d['prezzo_unitario'] for d in dettagli) if dettagli else 0
                st.metric("💰 Totale", format_currency(totale))
                st.caption(f"📦 {len(dettagli) if dettagli else 0} piatti")
            
            with col3:
                if st.button("👀 VEDI DETTAGLIO", key=f"dettaglio_{pre['id']}"):
                    st.session_state.promemoria_selezionato = pre['id']
                    st.session_state.tavolo_promemoria = pre['tavolo_numero']
                    st.session_state.sala_promemoria = pre['sala_nome']
                    st.rerun()
    
    # Mostra dettaglio se selezionato
    if 'promemoria_selezionato' in st.session_state:
        mostra_dettaglio_promemoria()


def mostra_dettaglio_promemoria():
    """Mostra il dettaglio di un promemoria con i tempi di servizio"""
    
    if 'promemoria_selezionato' not in st.session_state:
        return
    
    preordine_id = st.session_state.promemoria_selezionato
    tavolo_numero = st.session_state.tavolo_promemoria
    sala_nome = st.session_state.sala_promemoria
    
    st.divider()
    st.markdown(f"## 📋 Dettaglio Ordine - Tavolo {tavolo_numero} ({sala_nome})")
    
    # Recupera dettagli ordinati per posizione
    dettagli = esegui_query("""
        SELECT * FROM preordini_dettaglio 
        WHERE preordine_id = ? 
        ORDER BY posizione
    """, (preordine_id,), fetchall=True)
    
    if not dettagli:
        st.warning("Nessun piatto in questo promemoria")
        return
    
    # Mostra timeline dei tempi
    st.markdown("### 📊 Timeline di Servizio")
    
    cols = st.columns(4)
    tempi = ["⚡ TEMPO 1", "⏱️ TEMPO 2", "📅 TEMPO 3", "🎂 TEMPO 4"]
    colori = ["#e74c3c", "#f39c12", "#3498db", "#9b59b6"]
    
    for i, (col, tempo, colore) in enumerate(zip(cols, tempi, colori)):
        with col:
            piatti_tempo = [d for d in dettagli if d['posizione'] == i]
            st.markdown(f"""
                <div style="background-color: {colore}20; padding: 0.5rem; border-radius: 10px; border-left: 5px solid {colore};">
                    <span style="color: {colore}; font-weight: bold;">{tempo}</span>
                    <div style="font-size: 1.2rem;">{len(piatti_tempo)} piatti</div>
                </div>
            """, unsafe_allow_html=True)
    
    st.divider()
    
    # Mostra piatti in ordine
    totale = 0
    for idx, d in enumerate(dettagli):
        # Determina colore in base alla posizione
        if idx == 0:
            colore_tempo = "#e74c3c"
            tempo_nome = "⚡ TEMPO 1"
        elif idx == 1:
            colore_tempo = "#f39c12"
            tempo_nome = "⏱️ TEMPO 2"
        elif idx == 2:
            colore_tempo = "#3498db"
            tempo_nome = "📅 TEMPO 3"
        else:
            colore_tempo = "#9b59b6"
            tempo_nome = "🎂 TEMPO 4"
        
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                st.markdown(f"""
                    <span style="color: {colore_tempo}; font-weight: bold;">{tempo_nome}</span>
                """, unsafe_allow_html=True)
                st.markdown(f"**{d['qty']}x {d['piatto_nome']}**")
                
                # Mostra variazioni se presenti
                if d.get('variazioni') and d['variazioni'] not in ['[]', '{}', '']:
                    try:
                        var = json.loads(d['variazioni'])
                        for v in var:
                            st.caption(f"  ✦ {v.get('nome', '')} (+{format_currency(v.get('prezzo', 0))})")
                    except:
                        pass
                
                if d.get('note'):
                    st.caption(f"📝 {d['note']}")
            
            with col2:
                st.markdown(f"**{format_currency(d['prezzo_unitario'])}**")
            
            with col3:
                st.markdown(f"**{format_currency(d['prezzo_unitario'] * d['qty'])}**")
            
            totale += d['prezzo_unitario'] * d['qty']
    
    st.markdown(f"### TOTALE: {format_currency(totale)}")
    
    st.divider()
    
    # Bottoni azione
    col_back, col_converti = st.columns(2)
    
    with col_back:
        if st.button("⬅️ TORNA ALLA LISTA", use_container_width=True):
            del st.session_state.promemoria_selezionato
            del st.session_state.tavolo_promemoria
            del st.session_state.sala_promemoria
            st.rerun()
    
    with col_converti:
        if st.button("✅ CONVERTI IN COMANDA", type="primary", use_container_width=True):
            converti_promemoria_in_comanda(preordine_id, tavolo_numero, dettagli)


def converti_promemoria_in_comanda(preordine_id, tavolo_numero, dettagli):
    """Converte un promemoria in comanda rispettando i tempi"""
    
    try:
        # Recupera il preordine
        preordine = esegui_query("SELECT * FROM preordini WHERE id = ?", (preordine_id,), fetchone=True)
        
        if not preordine:
            st.error("Promemoria non trovato")
            return
        
        # Occupa il tavolo e crea comanda
        comanda_id = TavoloService.occupa_tavolo(preordine['tavolo_id'], st.session_state.user_id)
        
        # Raccogli piatti per reparto (per stampe)
        piatti_per_reparto = {}
        
        # Inserisci le comandine rispettando l'ordine e i tempi
        for idx, d in enumerate(dettagli):
            # Determina tempo in base alla posizione
            if idx == 0:
                tempo_codice = "TEMPO1"
                minuti = 0
            elif idx == 1:
                tempo_codice = "TEMPO2"
                minuti = 10
            elif idx == 2:
                tempo_codice = "TEMPO3"
                minuti = 20
            else:
                tempo_codice = "TEMPO4"
                minuti = 30
            
            # Determina reparto
            piatto_info = esegui_query("""
                SELECT c.reparto_id 
                FROM piatti p
                JOIN categorie c ON p.categoria_id = c.id
                WHERE p.id = ?
            """, (d['piatto_id'],), fetchone=True)
            
            reparto_id = piatto_info['reparto_id'] if piatto_info else 1
            
            # Prepara note
            note_json = d.get('variazioni', '[]')
            
            # Inserisci commandina
            esegui_query("""
                INSERT INTO comandine 
                (comanda_id, piatto_id, piatto_nome, qty, prezzo_unitario, 
                 note, stato, reparto_id, tempo_consegna, minuti_consegna)
                VALUES (?, ?, ?, ?, ?, ?, 'NUOVO', ?, ?, ?)
            """, (
                comanda_id,
                d['piatto_id'],
                d['piatto_nome'],
                d['qty'],
                d['prezzo_unitario'],
                note_json,
                reparto_id,
                tempo_codice,
                minuti
            ), commit=True)
            
            # Raccogli per stampa
            if reparto_id not in piatti_per_reparto:
                piatti_per_reparto[reparto_id] = []
            
            piatti_per_reparto[reparto_id].append({
                'piatto_nome': f"{d['piatto_nome']} [{tempo_codice}]",
                'qty': d['qty'],
                'note': note_json
            })
        
        # Aggiorna stato preordine
        esegui_query("""
            UPDATE preordini 
            SET stato = 'CONFERMATO', cameriere_id = ?, timestamp_revisione = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (st.session_state.user_id, preordine_id), commit=True)
        
        # Stampa automatica
        try:
            from db import StampanteService
            for reparto_id, piatti in piatti_per_reparto.items():
                StampanteService.stampa_comanda(comanda_id, reparto_id, piatti)
        except Exception as e:
            st.warning(f"⚠️ Stampa non disponibile: {e}")
        
        st.success(f"✅ Ordine convertito in comanda #{comanda_id}!")
        st.balloons()
        
        # Pulisci sessione
        del st.session_state.promemoria_selezionato
        del st.session_state.tavolo_promemoria
        del st.session_state.sala_promemoria
        
        time.sleep(2)
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Errore durante la conversione: {e}")
        import traceback
        traceback.print_exc()                   


def conferma_preordine(preordine_id):
    """Converte un pre-ordine in comanda vera e propria"""
    
    # Recupera il pre-ordine
    preordine = esegui_query("SELECT * FROM preordini WHERE id = ?", (preordine_id,), fetchone=True)
    
    if not preordine:
        st.error("Pre-ordine non trovato")
        return False
    
    # Recupera i dettagli del pre-ordine
    dettagli = esegui_query("SELECT * FROM preordini_dettaglio WHERE preordine_id = ?", 
                           (preordine_id,), fetchall=True)
    
    if not dettagli:
        st.error("Nessun piatto nel pre-ordine")
        return False
    
    try:
        # Crea la comanda (occupa il tavolo)
        comanda_id = TavoloService.occupa_tavolo(preordine['tavolo_id'], st.session_state.user_id)
        st.write(f"✅ Comanda creata con ID: {comanda_id}")  # Debug
        
        # Per ogni piatto, crea una commandina
        for d in dettagli:
            # Determina il reparto del piatto
            piatto_info = esegui_query("""
                SELECT c.reparto_id 
                FROM piatti p
                JOIN categorie c ON p.categoria_id = c.id
                WHERE p.id = ?
            """, (d['piatto_id'],), fetchone=True)
            
            reparto_id = piatto_info['reparto_id'] if piatto_info else 1
            
            # Gestisci variazioni
            variazioni_json = d.get('variazioni', '')
            
            # Inserisci la commandina
            esegui_query("""
                INSERT INTO comandine 
                (comanda_id, piatto_id, piatto_nome, qty, prezzo_unitario, 
                 note, stato, reparto_id, tempo_consegna, minuti_consegna)
                VALUES (?, ?, ?, ?, ?, ?, 'NUOVO', ?, 'TEMPO2', 10)
            """, (
                comanda_id, 
                d['piatto_id'], 
                d['piatto_nome'], 
                d['qty'], 
                d['prezzo_unitario'],
                variazioni_json, 
                reparto_id
            ), commit=True)
        
        # Aggiorna lo stato del pre-ordine
        esegui_query("""
            UPDATE preordini 
            SET stato = 'CONFERMATO', cameriere_id = ?, timestamp_revisione = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (st.session_state.user_id, preordine_id), commit=True)
        
        st.success(f"✅ Ordine confermato e inviato ai reparti!")
        return True
        
    except Exception as e:
        st.error(f"❌ Errore durante la conferma: {e}")
        import traceback
        traceback.print_exc()
        return False

# ============================================================================
# MODULO CASSA
# ============================================================================
def show_cassa():
    st.title("💰 Cassa")
    
    tab_conti, tab_pagamenti, tab_stats = st.tabs(["🪑 CONTI DA PAGARE", "💳 PAGAMENTI", "📊 STATS"])
    
    with tab_conti:
        show_conti_da_pagare()
    with tab_pagamenti:
        show_pagamenti()
    with tab_stats:
        show_stats_cassa()


# ============================================================================
# FUNZIONE PER GENERARE PRECONTO/SCONTRINO
# ============================================================================
def genera_preconto(comanda_id, brand_info=None, tipo="PRECONTO"):
    """Genera HTML per preconto/scontrino"""
    
    if not brand_info:
        brand_info = esegui_query("SELECT * FROM brand WHERE id = 1", fetchone=True)
    
    # Recupera dati comanda
    comanda = esegui_query("""
        SELECT c.*, t.numero as tavolo_numero, s.nome as sala_nome,
               u.nome as cameriere_nome, u.cognome as cameriere_cognome
        FROM comande c
        JOIN tavoli t ON c.tavolo_id = t.id
        JOIN sale s ON t.sala_id = s.id
        LEFT JOIN utenti u ON c.cameriere_id = u.id
        WHERE c.id = ?
    """, (comanda_id,), fetchone=True)
    
    # Recupera piatti
    piatti = esegui_query("""
        SELECT * FROM comandine
        WHERE comanda_id = ?
        ORDER BY id
    """, (comanda_id,), fetchall=True)
    
    # Recupera pagamento se esiste (per scontrino)
    pagamento = None
    if tipo == "SCONTRINO":
        pagamento = esegui_query("""
            SELECT * FROM pagamenti
            WHERE comanda_id = ?
            ORDER BY timestamp_pagamento DESC
            LIMIT 1
        """, (comanda_id,), fetchone=True)
    
    # Calcola totali
    subtotale = sum(p['qty'] * p['prezzo_unitario'] for p in piatti)
    
    # Intestazione
    html = f"""
    <div style="font-family: 'Courier New', monospace; max-width: 300px; margin: 0 auto; padding: 20px; border: 1px solid #ccc; background: white;">
        <div style="text-align: center; margin-bottom: 20px;">
            <h2 style="margin:0; color: #d35400;">{brand_info['nome'] if brand_info else 'RISTORAPP'}</h2>
            <p style="margin:5px 0;">{brand_info.get('indirizzo', '')}</p>
            <p style="margin:5px 0;">Tel: {brand_info.get('telefono', '')}</p>
            <p style="margin:5px 0;">P.IVA: {brand_info.get('partita_iva', '')}</p>
            <hr>
            <h3 style="margin:10px 0;">{tipo}</h3>
    """
    
    # Aggiungi scritta "NON FISCALE" per scontrino
    if tipo == "SCONTRINO":
        html += """
            <p style="color: #e74c3c; font-weight: bold; font-size: 1.1em;">📌 NON FISCALE</p>
        """
    
    html += """
        </div>
    """
    
    # Info tavolo e data/ora
    ora_attuale = datetime.now().strftime('%d/%m/%Y %H:%M')
    html += f"""
        <div style="margin-bottom: 15px;">
            <p><strong>Tavolo:</strong> {comanda['tavolo_numero']} - {comanda['sala_nome']}</p>
            <p><strong>Cameriere:</strong> {comanda.get('cameriere_nome', '')} {comanda.get('cameriere_cognome', '')}</p>
            <p><strong>Data e Ora:</strong> {ora_attuale}</p>
    """
    
    if pagamento:
        html += f"""
            <p><strong>Pagamento:</strong> {pagamento.get('metodo', 'N/A')}</p>
            <p><strong>Operatore:</strong> {st.session_state.get('username', 'N/A')}</p>
        """
    
    html += """
        </div>
        
        <hr>
        
        <table style="width:100%; border-collapse: collapse;">
            <tr style="border-bottom: 1px solid #ccc;">
                <th style="text-align:left;">Articolo</th>
                <th style="text-align:right;">Q.tà</th>
                <th style="text-align:right;">Prezzo</th>
                <th style="text-align:right;">Totale</th>
            </tr>
    """
    
    # Piatti
    for p in piatti:
        html += f"""
            <tr>
                <td>{p['piatto_nome']}</td>
                <td style="text-align:right;">{p['qty']}</td>
                <td style="text-align:right;">€ {p['prezzo_unitario']:.2f}</td>
                <td style="text-align:right;">€ {p['qty'] * p['prezzo_unitario']:.2f}</td>
            </tr>
        """
        
        if p.get('note'):
            html += f"""
            <tr>
                <td colspan="4" style="font-style:italic; color:#666; padding-left:20px;">📝 {p['note']}</td>
            </tr>
            """
    
    html += f"""
        </table>
        
        <hr>
        
        <div style="text-align:right; font-size:1.2em;">
            <p><strong>Subtotale: € {subtotale:.2f}</strong></p>
    """
    
    # Dettaglio pagamento per scontrino
    if pagamento:
        html += f"""
            <hr>
            <p><strong>Contanti: € {pagamento.get('contanti', 0):.2f}</strong></p>
            <p><strong>Carta: € {pagamento.get('carta', 0):.2f}</strong></p>
            <p><strong>Bancomat: € {pagamento.get('bancomat', 0):.2f}</strong></p>
            <p><strong>Altro: € {pagamento.get('altri', 0):.2f}</strong></p>
            <hr>
            <p><strong>TOTALE PAGATO: € {subtotale:.2f}</strong></p>
            <p><strong>Resto: € {pagamento.get('resto', 0):.2f}</strong></p>
        """
    else:
        html += f"""
            <p><strong>TOTALE: € {subtotale:.2f}</strong></p>
        """
    
    html += """
        </div>
        
        <div style="text-align:center; margin-top:30px;">
            <p>Grazie per averci scelto!</p>
            <p>Alla prossima!</p>
        </div>
    </div>
    """
    
    return html, subtotale


# ============================================================================
# FUNZIONE PER STAMPARE SCONTRINO (TESTO PER STAMPANTE TERMICA)
# ============================================================================
def stampa_scontrino(comanda_id, tipo="SCONTRINO"):
    """Genera testo per stampante termica"""
    try:
        # Recupera dati comanda
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
            return False, "Comanda non trovata"
        
        # Recupera piatti
        piatti = esegui_query("""
            SELECT * FROM comandine
            WHERE comanda_id = ?
            ORDER BY id
        """, (comanda_id,), fetchall=True)
        
        if not piatti:
            return False, "Nessun piatto in questa comanda"
        
        # Recupera pagamento
        pagamento = esegui_query("""
            SELECT * FROM pagamenti
            WHERE comanda_id = ?
            ORDER BY timestamp_pagamento DESC
            LIMIT 1
        """, (comanda_id,), fetchone=True)
        
        # Recupera brand
        brand = esegui_query("SELECT * FROM brand WHERE id = 1", fetchone=True) or {}
        
        # Calcola totale
        totale = sum(p['qty'] * p['prezzo_unitario'] for p in piatti)
        
        # Data e ora attuale
        ora_attuale = datetime.now().strftime('%d/%m/%Y %H:%M')
        
        # Crea contenuto per stampa
        lines = []
        lines.append("=" * 42)
        lines.append(f"  {brand.get('nome', 'RISTORAPP')}")
        if brand.get('indirizzo'):
            lines.append(f"  {brand['indirizzo']}")
        if brand.get('telefono'):
            lines.append(f"  Tel: {brand['telefono']}")
        if brand.get('partita_iva'):
            lines.append(f"  P.IVA: {brand['partita_iva']}")
        lines.append("=" * 42)
        lines.append(f"  {tipo}")
        
        # Aggiungi scritta NON FISCALE per scontrino
        if tipo == "SCONTRINO":
            lines.append("  📌 NON FISCALE")
        
        lines.append("=" * 42)
        lines.append(f"  TAVOLO: {comanda['tavolo_numero']} - {comanda['sala_nome']}")
        lines.append(f"  DATA e ORA: {ora_attuale}")
        if comanda.get('cameriere_nome'):
            lines.append(f"  CAMERIERE: {comanda['cameriere_nome']} {comanda.get('cameriere_cognome', '')}")
        lines.append("-" * 42)
        lines.append(" QTA DESCRIZIONE")
        lines.append("-" * 42)
        
        for p in piatti:
            nome = p['piatto_nome'][:28] if len(p['piatto_nome']) > 28 else p['piatto_nome']
            lines.append(f" {p['qty']:2}  {nome}")
            lines.append(f"     € {p['prezzo_unitario']:6.2f}  € {p['qty'] * p['prezzo_unitario']:6.2f}")
            if p.get('note'):
                lines.append(f"     -> {p['note'][:30]}")
        
        lines.append("-" * 42)
        lines.append(f" TOTALE: € {totale:8.2f}")
        
        if pagamento and tipo == "SCONTRINO":
            lines.append("-" * 42)
            lines.append(" SUDDIVISIONE PAGAMENTO:")
            if pagamento.get('contanti', 0) > 0:
                lines.append(f"   Contanti: € {pagamento['contanti']:8.2f}")
            if pagamento.get('carta', 0) > 0:
                lines.append(f"   Carta: € {pagamento['carta']:8.2f}")
            if pagamento.get('bancomat', 0) > 0:
                lines.append(f"   Bancomat: € {pagamento['bancomat']:8.2f}")
            if pagamento.get('altri', 0) > 0:
                lines.append(f"   Altro: € {pagamento['altri']:8.2f}")
            if pagamento.get('resto', 0) > 0:
                lines.append(f"   Resto: € {pagamento['resto']:8.2f}")
        
        lines.append("=" * 42)
        lines.append("  Grazie e arrivederci!")
        lines.append("=" * 42)
        lines.append("")
        lines.append("\n" * 3)
        
        content = "\n".join(lines)
        
        # Prova a inviare alla stampante
        try:
            from db import StampanteService
            job = {
                'printer': {'nome': 'Stampante Termica'},
                'content': content,
                'tipo': tipo,
                'comanda_id': comanda_id,
                'reparto_id': None
            }
            if hasattr(StampanteService, '_print_queue'):
                StampanteService._print_queue.put(job)
                return True, f"✅ {tipo} inviato alla stampante"
            else:
                return True, content
        except:
            return True, content
            
    except Exception as e:
        return False, f"Errore: {e}"


def show_conti_da_pagare():
    conti = PagamentoService.get_conti_richiesti()
    
    if not conti:
        st.success("✅ Nessun conto da pagare")
        return
    
    for conto in conti:
        with st.container(border=True):
            col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
            
            with col1:
                st.markdown(f"### 🪑 Tavolo {conto['tavolo_numero']}")
                st.caption(f"Sala: {conto['sala_nome']}")
            
            with col2:
                st.markdown(f"### {format_currency(conto['totale'])}")
                if conto['timestamp_richiesta_conto']:
                    if hasattr(conto['timestamp_richiesta_conto'], 'strftime'):
                        ora = conto['timestamp_richiesta_conto'].strftime('%H:%M')
                    else:
                        ora = str(conto['timestamp_richiesta_conto'])[:5]
                else:
                    ora = 'N/A'
                st.caption(f"Richiesto: {ora}")
            
            with col3:
                if st.button("📄 PRECONTO", key=f"preconto_{conto['comanda_id']}"):
                    brand = esegui_query("SELECT * FROM brand WHERE id = 1", fetchone=True)
                    preconto_html, totale = genera_preconto(conto['comanda_id'], brand, "PRECONTO")
                    st.session_state.preconto_html = preconto_html
                    st.session_state.preconto_show = True
                    st.session_state.preconto_comanda_id = conto['comanda_id']
                    st.rerun()
            
            with col4:
                if st.button("🖨️ STAMPA", key=f"stampa_{conto['comanda_id']}"):
                    success, result = stampa_scontrino(conto['comanda_id'], "PRECONTO")
                    if success:
                        if not result.startswith("✅"):
                            with st.expander("🖨️ Anteprima Stampa", expanded=True):
                                st.code(result, language="text")
                        else:
                            st.success(result)
                    else:
                        st.error(result)
            
            with col5:
                if st.button("💰 PAGA", key=f"paga_{conto['comanda_id']}"):
                    st.session_state.pagamento_in_corso = conto
                    st.rerun()
    
    # Mostra preconto se richiesto
    if st.session_state.get('preconto_show', False):
        with st.expander("🧾 PRECONTO", expanded=True):
            st.markdown(st.session_state.preconto_html, unsafe_allow_html=True)
            
            col_stampa, col_stampa_testo, col_chiudi = st.columns(3)
            with col_stampa:
                if st.button("🖨️ STAMPA TERMICA", key="stampa_preconto"):
                    if st.session_state.get('preconto_comanda_id'):
                        success, result = stampa_scontrino(st.session_state.preconto_comanda_id, "PRECONTO")
                        if success:
                            if not result.startswith("✅"):
                                with st.expander("📄 Anteprima Stampa", expanded=False):
                                    st.code(result, language="text")
                            else:
                                st.success(result)
                        else:
                            st.error(result)
            
            with col_stampa_testo:
                if st.button("📄 COPIA TESTO", key="copia_preconto"):
                    if st.session_state.get('preconto_comanda_id'):
                        success, result = stampa_scontrino(st.session_state.preconto_comanda_id, "PRECONTO")
                        if success and not result.startswith("✅"):
                            st.code(result, language="text")
                            st.info("Copia il testo sopra per incollarlo dove vuoi")
            
            with col_chiudi:
                if st.button("✖️ CHIUDI PRECONTO", key="chiudi_preconto"):
                    st.session_state.preconto_show = False
                    st.rerun()


def show_pagamenti():
    if not st.session_state.pagamento_in_corso:
        st.info("Seleziona un tavolo dalla lista")
        return
    
    conto = st.session_state.pagamento_in_corso
    st.subheader(f"💰 Pagamento Tavolo {conto['tavolo_numero']}")
    
    # Mostra dettaglio comanda
    with st.expander("📋 DETTAGLIO COMANDA", expanded=True):
        piatti = OrdineService.get_piatti_comanda(conto['comanda_id'])
        totale_calcolato = 0
        for p in piatti:
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"{p['qty']}x {p['piatto_nome']}")
            with col2:
                st.write(f"€{p['prezzo_unitario']:.2f}")
            with col3:
                importo = p['qty'] * p['prezzo_unitario']
                st.write(f"**€{importo:.2f}**")
                totale_calcolato += importo
        
        st.markdown("---")
        st.markdown(f"### TOTALE: € {totale_calcolato:.2f}")
    
    st.markdown("---")
    st.markdown("### 💳 SUDDIVISIONE PAGAMENTO")
    
    col1, col2 = st.columns(2)
    
    with col1:
        contanti = st.number_input("💵 Contanti", min_value=0.0, step=5.0, value=0.0, format="%.2f", key="contanti_input")
        carta = st.number_input("💳 Carta", min_value=0.0, step=5.0, value=0.0, format="%.2f", key="carta_input")
    
    with col2:
        bancomat = st.number_input("🏦 Bancomat", min_value=0.0, step=5.0, value=0.0, format="%.2f", key="bancomat_input")
        altri = st.number_input("💰 Altro", min_value=0.0, step=5.0, value=0.0, format="%.2f", key="altri_input")
    
    totale_inserito = contanti + carta + bancomat + altri
    differenza = totale_inserito - totale_calcolato
    
    # Mostra riepilogo
    col_res1, col_res2, col_res3 = st.columns(3)
    with col_res1:
        st.metric("Totale da pagare", f"€ {totale_calcolato:.2f}")
    with col_res2:
        st.metric("Totale inserito", f"€ {totale_inserito:.2f}")
    with col_res3:
        if differenza >= 0:
            st.metric("Resto", f"€ {differenza:.2f}", delta_color="off")
        else:
            st.error(f"Mancano € {abs(differenza):.2f}")
    
    st.markdown("---")
    
    col_annulla, col_conferma, col_stampa = st.columns(3)
    
    with col_annulla:
        if st.button("❌ ANNULLA", use_container_width=True):
            st.session_state.pagamento_in_corso = None
            st.rerun()
    
    with col_conferma:
        if st.button("✅ CONFERMA PAGAMENTO", type="primary", use_container_width=True, 
                    disabled=(abs(differenza) > 0.01)):
            if abs(differenza) <= 0.01:
                # Determina metodo prevalente
                if contanti == totale_calcolato:
                    metodo = "CONTANTI"
                elif carta == totale_calcolato:
                    metodo = "CARTA"
                elif bancomat == totale_calcolato:
                    metodo = "BANCOMAT"
                else:
                    metodo = "MISTO"
                
                success = PagamentoService.registra_pagamento(
                    conto['comanda_id'], 
                    metodo,
                    contanti=contanti,
                    carta=carta,
                    bancomat=bancomat,
                    altri=altri,
                    operatore_id=st.session_state.user_id
                )
                
                if success:
                    # Archivia nello storico
                    try:
                        from db import OrdineService, ReportService
                        OrdineService.archivia_comanda(conto['comanda_id'])
                        ReportService.aggiorna_storico_cassa()
                    except Exception as e:
                        write_debug(f"Errore archiviazione storico: {e}")
                    
                    st.success("✅ Pagamento registrato!")
                    
                    # Genera scontrino con scritta NON FISCALE
                    brand = esegui_query("SELECT * FROM brand WHERE id = 1", fetchone=True)
                    scontrino_html, totale = genera_preconto(conto['comanda_id'], brand, "SCONTRINO")
                    st.session_state.scontrino_html = scontrino_html
                    st.session_state.scontrino_show = True
                    
                    # Stampa automatica
                    try:
                        stampa_scontrino(conto['comanda_id'], "SCONTRINO")
                    except:
                        pass
                    
                    st.session_state.pagamento_in_corso = None
                    time.sleep(1)
                    st.rerun()
    
    with col_stampa:
        if st.button("🖨️ STAMPA PRECONTO", use_container_width=True):
            success, result = stampa_scontrino(conto['comanda_id'], "PRECONTO")
            if success:
                if not result.startswith("✅"):
                    with st.expander("📄 Anteprima Stampa", expanded=True):
                        st.code(result, language="text")
                else:
                    st.success(result)
            else:
                st.error(result)
    
    # Mostra scontrino dopo pagamento
    if st.session_state.get('scontrino_show', False):
        with st.expander("🧾 SCONTRINO", expanded=True):
            st.markdown(st.session_state.scontrino_html, unsafe_allow_html=True)
            
            col_stampa, col_chiudi = st.columns(2)
            with col_stampa:
                if st.button("🖨️ STAMPA SCONTRINO", key="stampa_scontrino"):
                    if st.session_state.get('preconto_comanda_id'):
                        success, result = stampa_scontrino(st.session_state.preconto_comanda_id, "SCONTRINO")
                        if success:
                            if not result.startswith("✅"):
                                with st.expander("📄 Anteprima Stampa", expanded=False):
                                    st.code(result, language="text")
                            else:
                                st.success(result)
                        else:
                            st.error(result)
            
            with col_chiudi:
                if st.button("✖️ CHIUDI SCONTRINO", key="chiudi_scontrino"):
                    st.session_state.scontrino_show = False
                    st.rerun()


def show_stats_cassa():
    st.subheader("📊 Statistiche Cassa")
    stats = ReportService.statistiche_complete_oggi()
    st.metric("💰 Incasso Oggi", format_currency(stats['incasso_totale']))
    st.metric("🧾 Scontrini", stats['totale_scontrini'])


# ============================================================================
# MODULO AMMINISTRAZIONE
# ============================================================================
def show_amministrazione():
    st.title("⚙️ Amministrazione")
    
    tabs = st.tabs(["🏢 BRAND", "👥 UTENTI", "🍽️ MENU", "📊 REPORT", "🖨️ STAMPANTI", "📱 QR CODE", "🔄 BACKUP", "🧹 PULIZIA"])
    
    with tabs[0]:
        show_gestione_brand()
    with tabs[1]:
        show_gestione_utenti()
    with tabs[2]:
        show_gestione_menu()
    with tabs[3]:
        show_report_amministrazione()
    with tabs[4]:
        show_gestione_stampanti()
    with tabs[5]:
        show_qr_code_generator()
    with tabs[6]:
        show_backup()
    with tabs[7]:
        mostra_pulizia_backup(prefix="admin_pulizia")


def show_gestione_utenti():
    st.subheader("👥 Utenti")
    utenti = esegui_query("SELECT * FROM utenti ORDER BY ruolo, username", fetchall=True)
    for u in utenti:
        st.write(f"{u['nome']} {u['cognome']} - {u['ruolo']}")


# ============================================================================
# REPORT AMMINISTRAZIONE (CON PASSO 5 - ESPORTAZIONE CSV/JSON)
# ============================================================================
def show_report_amministrazione():
    st.markdown("### 📊 REPORT AMMINISTRATIVI")
    
    tab_giornaliero, tab_reparti, tab_tavoli, tab_cassa = st.tabs([
        "📅 GIORNALIERO", "👨‍🍳 REPARTI", "🪑 TAVOLI", "💰 CASSA"
    ])
    
    with tab_giornaliero:
        st.subheader("Report Giornaliero")
        
        col1, col2 = st.columns(2)
        with col1:
            data_inizio = st.date_input("Data inizio", value=date.today() - timedelta(days=7))
        with col2:
            data_fine = st.date_input("Data fine", value=date.today())
        
        if st.button("🔄 GENERA REPORT", key="gen_report"):
            report = ReportService.get_report_giornaliero(
                data_inizio.isoformat(), 
                data_fine.isoformat()
            )
            
            if report:
                df = pd.DataFrame(report)
                # Formatta colonne
                for col in ['incasso_totale', 'contanti', 'carta', 'bancomat', 'altri', 'scontrino_medio']:
                    if col in df.columns:
                        df[col] = df[col].apply(lambda x: f"€ {x:.2f}")
                
                st.dataframe(df, use_container_width=True)
                
                # Grafico
                st.subheader("Andamento Incassi")
                df_chart = pd.DataFrame(report)
                st.bar_chart(df_chart.set_index('data')['incasso_totale'])
                
                # PASSO 5 - Pulsanti esportazione
                col_csv, col_json = st.columns(2)
                with col_csv:
                    csv = df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        "📥 ESPORTA CSV",
                        data=csv,
                        file_name=f"report_{data_inizio}_{data_fine}.csv",
                        mime="text/csv",
                        key="download_csv"
                    )
                with col_json:
                    json_str = df.to_json(orient='records', indent=2)
                    st.download_button(
                        "📥 ESPORTA JSON",
                        data=json_str,
                        file_name=f"report_{data_inizio}_{data_fine}.json",
                        mime="application/json",
                        key="download_json"
                    )
            else:
                st.info("Nessun dato nel periodo selezionato")
    
    with tab_reparti:
        st.subheader("Produttività Reparti")
        
        giorni_reparti = st.slider("Ultimi giorni", min_value=1, max_value=90, value=30, key="giorni_reparti")
        
        stats_reparti = ReportService.get_statistiche_reparti(giorni_reparti)
        
        if stats_reparti:
            df_reparti = pd.DataFrame(stats_reparti)
            st.dataframe(df_reparti, use_container_width=True)
            
            # Grafico
            st.subheader("Piatti per Reparto")
            st.bar_chart(df_reparti.set_index('reparto')['piatti_preparati'])
        else:
            st.info("Nessun dato disponibile")
    
    with tab_tavoli:
        st.subheader("Storico Tavoli")
        
        # Selezione tavolo
        tavoli = TavoloService.get_tutti_tavoli()
        tavolo_options = {t['id']: f"Tavolo {t['numero']} - {t['sala_nome']}" for t in tavoli}
        
        tavolo_id = st.selectbox(
            "Seleziona tavolo",
            options=list(tavolo_options.keys()),
            format_func=lambda x: tavolo_options[x]
        )
        
        giorni_tavolo = st.slider("Giorni da visualizzare", min_value=1, max_value=90, value=30, key="giorni_tavolo")
        
        if tavolo_id:
            storico = OrdineService.get_storico_tavolo(tavolo_id, giorni_tavolo)
            
            if storico:
                df_storico = pd.DataFrame(storico)
                st.dataframe(df_storico, use_container_width=True)
                
                # Totali
                totale_periodo = sum(s['totale_comanda'] for s in storico)
                num_comande = len(storico)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Totale periodo", format_currency(totale_periodo))
                with col2:
                    st.metric("Numero comande", num_comande)
                with col3:
                    media = totale_periodo/num_comande if num_comande > 0 else 0
                    st.metric("Media per comanda", format_currency(media))
            else:
                st.info("Nessuno storico per questo tavolo")
    
    with tab_cassa:
        st.subheader("Storico Cassa")
        
        giorni_cassa = st.slider("Ultimi giorni", min_value=1, max_value=90, value=7, key="giorni_cassa")
        
        storico = ReportService.get_storico_cassa(giorni_cassa)
        
        if storico:
            df_cassa = pd.DataFrame(storico)
            
            # Formatta colonne
            for col in ['incasso_contanti', 'incasso_carta', 'incasso_bancomat', 'incasso_altri', 'totale_incasso', 'scontrino_medio']:
                if col in df_cassa.columns:
                    df_cassa[col] = df_cassa[col].apply(lambda x: f"€ {x:.2f}")
            
            st.dataframe(df_cassa, use_container_width=True)
            
            # Grafico a stack per metodo
            st.subheader("Suddivisione Incassi per Metodo")
            df_metodi = pd.DataFrame(storico)
            df_metodi_plot = df_metodi[['data', 'incasso_contanti', 'incasso_carta', 'incasso_bancomat', 'incasso_altri']]
            st.bar_chart(df_metodi_plot.set_index('data'))
        else:
            st.info("Nessun dato disponibile")


# ============================================================================
# GESTIONE BRAND
# ============================================================================
def show_gestione_brand():
    """Gestione del brand e logo del ristorante"""
    st.markdown("### 🏢 Gestione Brand")
    
    # Recupera info brand
    brand = esegui_query("SELECT * FROM brand WHERE id = 1", fetchone=True)
    if not brand:
        brand = {'nome': 'PALAZZO FIORINI', 'indirizzo': '', 'telefono': '', 'email': '', 'partita_iva': '', 'logo_data': None}
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.markdown("**📝 Informazioni Ristorante**")
        with st.form("form_brand"):
            nome = st.text_input("Nome Ristorante *", value=brand.get('nome', 'PALAZZO FIORINI'))
            indirizzo = st.text_input("Indirizzo", value=brand.get('indirizzo', ''))
            telefono = st.text_input("Telefono", value=brand.get('telefono', ''))
            email = st.text_input("Email", value=brand.get('email', ''))
            partita_iva = st.text_input("Partita IVA", value=brand.get('partita_iva', ''))
            
            st.markdown("---")
            st.markdown("**🖼️ Logo**")
            logo_file = st.file_uploader(
                "Carica logo (PNG, JPG, max 2MB)",
                type=['png', 'jpg', 'jpeg'],
                help="Il logo apparirà nell'header della pagina cliente"
            )
            
            if logo_file:
                if logo_file.size > 2 * 1024 * 1024:
                    st.error("File troppo grande (max 2MB)")
                else:
                    st.image(logo_file, width=150, caption="Anteprima logo")
            
            if st.form_submit_button("💾 SALVA BRAND", type="primary", use_container_width=True):
                try:
                    # Assicura che la tabella brand esista
                    esegui_query("""
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
                    """, commit=True)
                    
                    # Salva o aggiorna brand
                    if logo_file:
                        logo_data = logo_file.getvalue()
                        esegui_query("""
                            INSERT OR REPLACE INTO brand (id, nome, indirizzo, telefono, email, partita_iva, logo_data, updated_at)
                            VALUES (1, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """, (nome, indirizzo, telefono, email, partita_iva, logo_data), commit=True)
                    else:
                        # Verifica se il brand esiste già
                        existing = esegui_query("SELECT * FROM brand WHERE id = 1", fetchone=True)
                        if existing:
                            esegui_query("""
                                UPDATE brand SET nome = ?, indirizzo = ?, telefono = ?, email = ?, partita_iva = ?, updated_at = CURRENT_TIMESTAMP
                                WHERE id = 1
                            """, (nome, indirizzo, telefono, email, partita_iva), commit=True)
                        else:
                            esegui_query("""
                                INSERT INTO brand (id, nome, indirizzo, telefono, email, partita_iva, updated_at)
                                VALUES (1, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                            """, (nome, indirizzo, telefono, email, partita_iva), commit=True)
                    
                    st.success("✅ Brand aggiornato con successo!")
                    # Pulisci la cache per forzare il ricaricamento dei dati in cliente.py
                    st.cache_data.clear()
                    st.balloons()
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore: {e}")
    
    with col2:
        if brand.get('logo_data'):
            st.markdown("**📸 Logo Attuale**")
            st.image(brand['logo_data'], width=200)
        else:
            st.info("Nessun logo caricato")
        
        st.markdown("---")
        st.markdown("**🔍 Anteprima Header Cliente**")
        
        # Anteprima dell'header come sarà visto dal cliente
        if brand.get('logo_data'):
            import base64
            encoded = base64.b64encode(brand['logo_data']).decode()
            logo_html = f'<img src="data:image/png;base64,{encoded}" style="height:35px; margin-right:10px;">'
        else:
            logo_html = ''
        
        st.markdown(f"""
            <div style='background: linear-gradient(135deg, #d35400 0%, #e67e22 100%); padding: 0.8rem 1rem; border-radius: 10px; color: white; display: flex; align-items: center; justify-content: space-between; margin-top: 0.5rem;'>
                <div style='display: flex; align-items: center;'>
                    {logo_html}
                    <span style='font-size:1.2rem; font-weight:600;'>{nome}</span>
                </div>
                <div style='background: rgba(255,255,255,0.2); padding: 0.2rem 1rem; border-radius: 30px; font-size:0.9rem;'>
                    Tavolo 1
                </div>
            </div>
        """, unsafe_allow_html=True)
        
        st.caption("Questa è l'anteprima di come apparirà l'header nella pagina cliente")

# ============================================================================
# GESTIONE MENU COMPLETO
# ============================================================================
def show_gestione_menu():
    st.subheader("🍽️ Gestione Menu")
    
    menu_tabs = st.tabs(["📁 CATEGORIE", "🍽️ PIATTI", "✨ VARIAZIONI", "🔒 RICETTE SEGRETE"])
    
    with menu_tabs[0]:
        show_gestione_categorie()
    
    with menu_tabs[1]:
        show_gestione_piatti()
    
    with menu_tabs[2]:
        show_gestione_variazioni()
    
    with menu_tabs[3]:
        show_ricette_segrete()

# ============================================================================
# GESTIONE CATEGORIE
# ============================================================================
def show_gestione_categorie():
    st.markdown("### 📁 Gestione Categorie")
    
    # Recupera reparti per il selectbox
    reparti = esegui_query("SELECT * FROM reparti ORDER BY nome", fetchall=True)
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        with st.form("nuova_categoria"):
            st.markdown("**➕ Nuova Categoria**")
            
            nome = st.text_input("Nome categoria *", placeholder="es. ANTIPASTI")
            
            # Verifica che ci siano reparti
            if not reparti:
                st.error("❌ Nessun reparto trovato! Crea prima i reparti.")
                st.info("I reparti dovrebbero essere creati automaticamente all'avvio.")
            else:
                # Selectbox per reparto - con valore di default
                reparto_options = {r['id']: f"{r['icona']} {r['nome']}" for r in reparti}
                reparto_id = st.selectbox(
                    "Reparto *",
                    options=list(reparto_options.keys()),
                    format_func=lambda x: reparto_options[x],
                    index=0  # Seleziona il primo reparto
                )
            
            icona = st.text_input("Icona", value="🍽️", placeholder="es. 🥗")
            ordine = st.number_input("Ordine", min_value=1, value=10)
            attiva = st.checkbox("Categoria attiva", value=True)
            
            if st.form_submit_button("💾 SALVA CATEGORIA", use_container_width=True):
                if not nome:
                    st.error("Il nome è obbligatorio")
                elif not reparti:
                    st.error("Impossibile creare categoria: nessun reparto disponibile")
                else:
                    try:
                        # Assicurati che reparto_id sia valido
                        if reparto_id is None:
                            st.error("Seleziona un reparto valido")
                        else:
                            esegui_query("""
                                INSERT INTO categorie (nome, reparto_id, icona, ordine, attiva)
                                VALUES (?, ?, ?, ?, ?)
                            """, (nome.upper(), reparto_id, icona, ordine, 1 if attiva else 0), commit=True)
                            st.success(f"✅ Categoria '{nome}' creata!")
                            st.cache_data.clear()
                            st.rerun()
                    except Exception as e:
                        st.error(f"Errore: {e}")
                        write_debug(f"Errore creazione categoria: {e}", e)
    
    with col2:
        st.markdown("**📋 Categorie Esistenti**")
        
        categorie = esegui_query("""
            SELECT c.*, r.nome as reparto_nome, r.icona as reparto_icona
            FROM categorie c
            JOIN reparti r ON c.reparto_id = r.id
            ORDER BY c.ordine, c.nome
        """, fetchall=True)
        
        if not categorie:
            st.info("Nessuna categoria creata")
        else:
            for cat in categorie:
                with st.container(border=True):
                    cols = st.columns([3, 1, 1, 1])
                    with cols[0]:
                        st.markdown(f"{cat['icona']} **{cat['nome']}**")
                        st.caption(f"📦 {cat['reparto_icona']} {cat['reparto_nome']} | Ordine: {cat['ordine']}")
                    with cols[1]:
                        stato = "✅ Attiva" if cat['attiva'] else "❌ Inattiva"
                        st.markdown(stato)
                    with cols[2]:
                        if st.button("✏️", key=f"edit_cat_{cat['id']}"):
                            st.session_state.edit_cat_id = cat['id']
                            st.rerun()
                    with cols[3]:
                        if st.button("🗑️", key=f"del_cat_{cat['id']}"):
                            if st.checkbox(f"Confermi?", key=f"conf_cat_{cat['id']}"):
                                esegui_query("DELETE FROM categorie WHERE id = ?", (cat['id'],), commit=True)
                                st.cache_data.clear()
                                st.rerun()

# ============================================================================
# GESTIONE PIATTI CON IMMAGINI E RICETTE
# ============================================================================
def show_gestione_piatti():
    """Gestione completa dei piatti con modifica ed eliminazione"""
    
    # ============================================================================
    # GESTIONE MODIFICA PIATTO (se in modalità edit)
    # ============================================================================
    if st.session_state.get('edit_piatto_id'):
        show_modifica_piatto()
        return
    
    st.markdown("### 🍽️ Gestione Piatti")
    
    # Filtri
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        categorie = esegui_query("SELECT * FROM categorie WHERE attiva = 1 ORDER BY nome", fetchall=True)
        cat_options = {0: "📋 TUTTE"} | {c['id']: f"{c['icona']} {c['nome']}" for c in categorie}
        filtro_cat = st.selectbox(
            "Filtra categoria",
            options=list(cat_options.keys()),
            format_func=lambda x: cat_options[x],
            key="filtro_cat_piatti"
        )
    
    with col_f2:
        filtro_disponibile = st.selectbox(
            "Disponibilità",
            ["TUTTI", "Disponibili", "Non disponibili"],
            key="filtro_disp_piatti"
        )
    
    # Nuovo piatto
    with st.expander("➕ NUOVO PIATTO", expanded=False):
        with st.form("nuovo_piatto_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                nome = st.text_input("Nome piatto *", placeholder="es. Spaghetti Carbonara")
                categoria_id = st.selectbox(
                    "Categoria *",
                    options=[c['id'] for c in categorie],
                    format_func=lambda x: next(f"{c['icona']} {c['nome']}" for c in categorie if c['id'] == x)
                )
                prezzo = st.number_input("Prezzo (€) *", min_value=0.0, step=0.5, value=10.0)
            
            with col2:
                tempo_prep = st.number_input("Tempo preparazione (min)", min_value=1, value=15)
                disponibile = st.checkbox("Disponibile", value=True)
                ordinamento = st.number_input("Ordine", min_value=1, value=10)
            
            st.divider()
            st.markdown("##### 📖 Descrizione pubblica (visibile ai clienti)")
            descrizione_pubblica = st.text_area(
                "Descrizione per il menu",
                placeholder="Ingredienti e descrizione che vedranno i clienti...",
                height=100
            )
            
            st.divider()
            st.markdown("##### 🔒 Ricetta segreta (visibile solo a staff)")
            st.warning("⚠️ Quest'area è visibile solo a cucina, bar e amministrazione")
            
            col_ric1, col_ric2 = st.columns(2)
            with col_ric1:
                ingredienti = st.text_area(
                    "🥗 Ingredienti",
                    placeholder="Elenco ingredienti con quantità...",
                    height=150
                )
                preparazione = st.text_area(
                    "👨‍🍳 Preparazione",
                    placeholder="Passaggi per la preparazione...",
                    height=150
                )
            
            with col_ric2:
                note_cucina = st.text_area(
                    "📝 Note per la cucina",
                    placeholder="Temperatura, cottura, presentazione...",
                    height=150
                )
                allergeni = st.multiselect(
                    "⚠️ Allergeni",
                    ["Glutine", "Lattosio", "Uova", "Soia", "Frutta a guscio", "Crostacei", "Pesce", "Sedano"]
                )
            
            st.divider()
            st.markdown("##### 📸 Foto del piatto")
            foto_file = st.file_uploader(
                "Carica immagine (JPG, PNG, max 5MB)",
                type=['jpg', 'jpeg', 'png'],
                help="Seleziona una foto dal tuo computer",
                key="nuovo_piatto_foto"
            )
            
            if foto_file:
                if foto_file.size > 5 * 1024 * 1024:
                    st.error("File troppo grande (max 5MB)")
                else:
                    st.image(foto_file, width=200, caption="Anteprima")
                    st.session_state['temp_foto'] = foto_file.getvalue()
            
            if st.form_submit_button("💾 SALVA PIATTO", type="primary", use_container_width=True):
                if not nome or not categoria_id:
                    st.error("Nome e categoria sono obbligatori")
                else:
                    try:
                        # Crea JSON per la ricetta
                        ricetta_json = json.dumps({
                            'ingredienti': ingredienti,
                            'preparazione': preparazione,
                            'note_cucina': note_cucina,
                            'allergeni': allergeni
                        }, ensure_ascii=False)
                        
                        # Salva con o senza foto
                        if 'temp_foto' in st.session_state and st.session_state['temp_foto']:
                            esegui_query("""
                                INSERT INTO piatti 
                                (nome, categoria_id, prezzo, descrizione_pubblica, 
                                 descrizione_privata, tempo_preparazione, foto_data, 
                                 disponibile, ordine)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                nome, categoria_id, prezzo, descrizione_pubblica,
                                ricetta_json, tempo_prep, st.session_state['temp_foto'],
                                1 if disponibile else 0, ordinamento
                            ), commit=True)
                            del st.session_state['temp_foto']
                        else:
                            esegui_query("""
                                INSERT INTO piatti 
                                (nome, categoria_id, prezzo, descrizione_pubblica, 
                                 descrizione_privata, tempo_preparazione, disponibile, ordine)
                                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                            """, (
                                nome, categoria_id, prezzo, descrizione_pubblica,
                                ricetta_json, tempo_prep, 1 if disponibile else 0, ordinamento
                            ), commit=True)
                        
                        st.success(f"✅ Piatto '{nome}' creato!")
                        # Pulisci cache menu
                        st.cache_data.clear()
                        st.balloons()
                        st.rerun()
                    except Exception as e:
                        st.error(f"Errore: {e}")
    
    # Lista piatti
    st.divider()
    st.markdown("##### 📋 Lista Piatti")
    
    # Costruisci query con filtri
    query = """
        SELECT p.*, c.nome as categoria_nome, c.icona as cat_icona
        FROM piatti p
        JOIN categorie c ON p.categoria_id = c.id
        WHERE 1=1
    """
    params = []
    
    if filtro_cat != 0:
        query += " AND p.categoria_id = ?"
        params.append(filtro_cat)
    
    if filtro_disponibile == "Disponibili":
        query += " AND p.disponibile = 1"
    elif filtro_disponibile == "Non disponibili":
        query += " AND p.disponibile = 0"
    
    query += " ORDER BY c.ordine, p.nome"
    
    piatti = esegui_query(query, tuple(params), fetchall=True)
    
    if not piatti:
        st.info("Nessun piatto trovato")
    else:
        for p in piatti:
            with st.expander(f"{p.get('cat_icona', '🍽️')} **{p['nome']}** - {format_currency(p['prezzo'])}", expanded=False):
                col1, col2, col3 = st.columns([1, 2, 1])
                
                with col1:
                    if p.get('foto_data'):
                        st.image(p['foto_data'], width=150)
                    else:
                        st.image("https://via.placeholder.com/150?text=Nessuna+foto", width=150)
                    
                    stato = "✅ Disponibile" if p['disponibile'] else "❌ Non disponibile"
                    st.markdown(stato)
                    # Usa get() per evitare KeyError se la chiave non esiste
                    tempo = p.get('tempo_preparazione', 'N/A')
                    st.caption(f"⏱️ Tempo: {tempo} min")
                
                with col2:
                    tab_pub, tab_priv = st.tabs(["📖 Pubblico", "🔒 Privato"])
                    
                    with tab_pub:
                        st.markdown("**Descrizione:**")
                        st.write(p['descrizione_pubblica'] or "Nessuna descrizione")
                    
                    with tab_priv:
                        if st.session_state.user_role in ['SUPERADMIN', 'ADMIN', 'CUCINA', 'BAR']:
                            if p.get('descrizione_privata'):
                                try:
                                    ricetta = json.loads(p['descrizione_privata'])
                                    st.markdown("**🥗 Ingredienti:**")
                                    st.write(ricetta.get('ingredienti', 'N/A'))
                                    st.markdown("**👨‍🍳 Preparazione:**")
                                    st.write(ricetta.get('preparazione', 'N/A'))
                                    st.markdown("**📝 Note cucina:**")
                                    st.write(ricetta.get('note_cucina', 'N/A'))
                                    if ricetta.get('allergeni'):
                                        st.warning(f"⚠️ Allergeni: {', '.join(ricetta['allergeni'])}")
                                except:
                                    st.write(p['descrizione_privata'])
                            else:
                                st.info("Nessuna ricetta segreta")
                        else:
                            st.error("⛔ Accesso riservato")
                
                with col3:
                    st.markdown("**Azioni**")
                    
                    # Bottone MODIFICA
                    if st.button("✏️ Modifica", key=f"edit_{p['id']}", use_container_width=True):
                        st.session_state.edit_piatto_id = p['id']
                        st.rerun()
                    
                    # Bottone ATTIVA/DISATTIVA
                    nuovo_stato = "❌ Disabilita" if p['disponibile'] else "✅ Abilita"
                    if st.button(nuovo_stato, key=f"toggle_{p['id']}", use_container_width=True):
                        esegui_query("UPDATE piatti SET disponibile = ? WHERE id = ?", 
                                    (0 if p['disponibile'] else 1, p['id']), commit=True)
                        st.success(f"✅ Piatto {'disabilitato' if p['disponibile'] else 'abilitato'}!")
                        st.cache_data.clear()
                        st.rerun()
                    
                    # Bottone ELIMINA con conferma
                    delete_key = f"del_{p['id']}"
                    confirm_key = f"conf_del_{p['id']}"
                    
                    if st.button("🗑️ Elimina", key=delete_key, use_container_width=True):
                        st.session_state[confirm_key] = True
                        st.rerun()
                    
                    if st.session_state.get(confirm_key, False):
                        st.warning(f"Sei sicuro di voler eliminare '{p['nome']}'?")
                        col_conf1, col_conf2 = st.columns(2)
                        with col_conf1:
                            if st.button("✅ Sì", key=f"yes_{p['id']}", use_container_width=True):
                                try:
                                    # Prima elimina eventuali riferimenti in comandine e preordini_dettaglio
                                    esegui_query("DELETE FROM comandine WHERE piatto_id = ?", (p['id'],), commit=True)
                                    esegui_query("DELETE FROM preordini_dettaglio WHERE piatto_id = ?", (p['id'],), commit=True)
                                    # Poi elimina il piatto
                                    esegui_query("DELETE FROM piatti WHERE id = ?", (p['id'],), commit=True)
                                    st.success(f"✅ Piatto '{p['nome']}' eliminato!")
                                    st.cache_data.clear()
                                    del st.session_state[confirm_key]
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Errore durante l'eliminazione: {e}")
                        with col_conf2:
                            if st.button("❌ No", key=f"no_{p['id']}", use_container_width=True):
                                del st.session_state[confirm_key]
                                st.rerun()


def show_modifica_piatto():
    """Form per modificare un piatto esistente"""
    piatto_id = st.session_state.edit_piatto_id
    
    # Recupera i dati del piatto
    piatto = esegui_query("SELECT * FROM piatti WHERE id = ?", (piatto_id,), fetchone=True)
    
    if not piatto:
        st.error("Piatto non trovato")
        del st.session_state.edit_piatto_id
        st.rerun()
        return
    
    st.markdown(f"### ✏️ Modifica Piatto: {piatto['nome']}")
    
    # Pulsante per tornare indietro
    if st.button("⬅️ Torna alla lista", key="back_from_edit"):
        del st.session_state.edit_piatto_id
        if 'temp_foto_mod' in st.session_state:
            del st.session_state['temp_foto_mod']
        if 'rimuovi_foto' in st.session_state:
            del st.session_state['rimuovi_foto']
        st.rerun()
    
    st.divider()
    
    # Recupera categorie
    categorie = esegui_query("SELECT * FROM categorie WHERE attiva = 1 ORDER BY nome", fetchall=True)
    
    # Decodifica ricetta se esiste
    ricetta = {}
    if piatto.get('descrizione_privata'):
        try:
            ricetta = json.loads(piatto['descrizione_privata'])
        except:
            ricetta = {}
    
    with st.form("modifica_piatto_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            nome = st.text_input("Nome piatto *", value=piatto['nome'])
            
            # Trova l'indice della categoria corrente
            cat_index = 0
            for i, c in enumerate(categorie):
                if c['id'] == piatto['categoria_id']:
                    cat_index = i
                    break
            
            categoria_id = st.selectbox(
                "Categoria *",
                options=[c['id'] for c in categorie],
                format_func=lambda x: next(f"{c['icona']} {c['nome']}" for c in categorie if c['id'] == x),
                index=cat_index
            )
            prezzo = st.number_input("Prezzo (€) *", min_value=0.0, step=0.5, value=float(piatto['prezzo']))
        
        with col2:
            tempo_prep = st.number_input("Tempo preparazione (min)", min_value=1, value=piatto['tempo_preparazione'] or 15)
            disponibile = st.checkbox("Disponibile", value=bool(piatto['disponibile']))
            ordinamento = st.number_input("Ordine", min_value=1, value=piatto['ordine'] or 10)
        
        st.divider()
        st.markdown("##### 📖 Descrizione pubblica (visibile ai clienti)")
        descrizione_pubblica = st.text_area(
            "Descrizione per il menu",
            value=piatto['descrizione_pubblica'] or "",
            height=100
        )
        
        st.divider()
        st.markdown("##### 🔒 Ricetta segreta (visibile solo a staff)")
        
        col_ric1, col_ric2 = st.columns(2)
        with col_ric1:
            ingredienti = st.text_area(
                "🥗 Ingredienti",
                value=ricetta.get('ingredienti', ''),
                height=150
            )
            preparazione = st.text_area(
                "👨‍🍳 Preparazione",
                value=ricetta.get('preparazione', ''),
                height=150
            )
        
        with col_ric2:
            note_cucina = st.text_area(
                "📝 Note per la cucina",
                value=ricetta.get('note_cucina', ''),
                height=150
            )
            allergeni = st.multiselect(
                "⚠️ Allergeni",
                ["Glutine", "Lattosio", "Uova", "Soia", "Frutta a guscio", "Crostacei", "Pesce", "Sedano"],
                default=ricetta.get('allergeni', [])
            )
        
        st.divider()
        st.markdown("##### 📸 Foto del piatto")
        
        # Mostra foto attuale se presente
        if piatto.get('foto_data'):
            st.image(piatto['foto_data'], width=200, caption="Foto attuale")
            rimuovi_foto = st.checkbox("🗑️ Rimuovi foto", key="rimuovi_foto_check")
            if rimuovi_foto:
                st.session_state['rimuovi_foto'] = True
        else:
            st.info("Nessuna foto attuale")
        
        foto_file = st.file_uploader(
            "Carica nuova immagine (JPG, PNG, max 5MB)",
            type=['jpg', 'jpeg', 'png'],
            help="Seleziona una foto dal tuo computer (lascia vuoto per mantenere l'attuale)",
            key="modifica_piatto_foto"
        )
        
        if foto_file:
            if foto_file.size > 5 * 1024 * 1024:
                st.error("File troppo grande (max 5MB)")
            else:
                st.image(foto_file, width=200, caption="Nuova anteprima")
                st.session_state['temp_foto_mod'] = foto_file.getvalue()
        
        st.divider()
        
        col_save, col_cancel = st.columns(2)
        with col_save:
            submitted = st.form_submit_button("💾 SALVA MODIFICHE", type="primary", use_container_width=True)
        with col_cancel:
            cancel = st.form_submit_button("❌ ANNULLA", use_container_width=True)
        
        if submitted:
            if not nome or not categoria_id:
                st.error("Nome e categoria sono obbligatori")
            else:
                try:
                    # Crea JSON per la ricetta
                    ricetta_json = json.dumps({
                        'ingredienti': ingredienti,
                        'preparazione': preparazione,
                        'note_cucina': note_cucina,
                        'allergeni': allergeni
                    }, ensure_ascii=False)
                    
                    # Prepara i parametri per l'update
                    if st.session_state.get('rimuovi_foto', False):
                        # Rimuovi foto
                        esegui_query("""
                            UPDATE piatti 
                            SET nome = ?, categoria_id = ?, prezzo = ?, descrizione_pubblica = ?,
                                descrizione_privata = ?, tempo_preparazione = ?, foto_data = NULL,
                                disponibile = ?, ordine = ?
                            WHERE id = ?
                        """, (
                            nome, categoria_id, prezzo, descrizione_pubblica,
                            ricetta_json, tempo_prep,
                            1 if disponibile else 0, ordinamento,
                            piatto_id
                        ), commit=True)
                        st.success("✅ Foto rimossa!")
                    
                    elif 'temp_foto_mod' in st.session_state and st.session_state['temp_foto_mod']:
                        # Aggiorna con nuova foto
                        esegui_query("""
                            UPDATE piatti 
                            SET nome = ?, categoria_id = ?, prezzo = ?, descrizione_pubblica = ?,
                                descrizione_privata = ?, tempo_preparazione = ?, foto_data = ?,
                                disponibile = ?, ordine = ?
                            WHERE id = ?
                        """, (
                            nome, categoria_id, prezzo, descrizione_pubblica,
                            ricetta_json, tempo_prep, st.session_state['temp_foto_mod'],
                            1 if disponibile else 0, ordinamento,
                            piatto_id
                        ), commit=True)
                        del st.session_state['temp_foto_mod']
                        st.success("✅ Foto aggiornata!")
                    
                    else:
                        # Mantieni foto attuale
                        esegui_query("""
                            UPDATE piatti 
                            SET nome = ?, categoria_id = ?, prezzo = ?, descrizione_pubblica = ?,
                                descrizione_privata = ?, tempo_preparazione = ?,
                                disponibile = ?, ordine = ?
                            WHERE id = ?
                        """, (
                            nome, categoria_id, prezzo, descrizione_pubblica,
                            ricetta_json, tempo_prep,
                            1 if disponibile else 0, ordinamento,
                            piatto_id
                        ), commit=True)
                    
                    st.success(f"✅ Piatto '{nome}' aggiornato!")
                    st.balloons()
                    
                    # Pulisci cache e variabili di sessione
                    st.cache_data.clear()
                    del st.session_state.edit_piatto_id
                    if 'rimuovi_foto' in st.session_state:
                        del st.session_state['rimuovi_foto']
                    if 'temp_foto_mod' in st.session_state:
                        del st.session_state['temp_foto_mod']
                    
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Errore durante l'aggiornamento: {e}")
        
        if cancel:
            # Pulisci le variabili di sessione
            del st.session_state.edit_piatto_id
            if 'temp_foto_mod' in st.session_state:
                del st.session_state['temp_foto_mod']
            if 'rimuovi_foto' in st.session_state:
                del st.session_state['rimuovi_foto']
            st.rerun()


# ============================================================================
# GESTIONE VARIAZIONI
# ============================================================================
def show_gestione_variazioni():
    st.markdown("### ✨ Gestione Variazioni")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        with st.form("nuova_variazione"):
            st.markdown("**➕ Nuova Variazione**")
            
            nome = st.text_input("Nome *", placeholder="es. Mozzarella extra")
            prezzo = st.number_input("Prezzo extra (€)", min_value=0.0, step=0.5, value=1.0)
            
            reparti = esegui_query("SELECT * FROM reparti ORDER BY nome", fetchall=True)
            reparto_id = st.selectbox(
                "Reparto *",
                options=[r['id'] for r in reparti],
                format_func=lambda x: next(r['nome'] for r in reparti if r['id'] == x)
            )
            
            attivo = st.checkbox("Attiva", value=True)
            ordine = st.number_input("Ordine", min_value=1, value=10)
            
            if st.form_submit_button("💾 SALVA", use_container_width=True):
                if nome:
                    esegui_query("""
                        INSERT INTO variazioni (nome, prezzo, reparto_id, attivo, ordine)
                        VALUES (?, ?, ?, ?, ?)
                    """, (nome, prezzo, reparto_id, 1 if attivo else 0, ordine), commit=True)
                    st.success(f"✅ Variazione '{nome}' creata!")
                    st.rerun()
    
    with col2:
        # CORREZIONE: usa LEFT JOIN invece di JOIN
        variazioni = esegui_query("""
            SELECT v.*, COALESCE(r.nome, 'Reparto sconosciuto') as reparto_nome
            FROM variazioni v
            LEFT JOIN reparti r ON v.reparto_id = r.id
            ORDER BY r.nome, v.ordine, v.nome
        """, fetchall=True)
        
        if not variazioni:
            st.info("Nessuna variazione")
        else:
            for v in variazioni:
                with st.container(border=True):
                    cols = st.columns([3, 1, 1, 1])
                    with cols[0]:
                        st.markdown(f"**{v['nome']}**")
                        st.caption(f"📦 {v['reparto_nome']} | +{format_currency(v['prezzo'])}")
                    with cols[1]:
                        st.markdown("✅ Attiva" if v['attivo'] else "❌ Inattiva")
                    with cols[2]:
                        if st.button("✏️", key=f"edit_var_{v['id']}"):
                            st.session_state.edit_var_id = v['id']
                            st.rerun()
                    with cols[3]:
                        if st.button("🗑️", key=f"del_var_{v['id']}"):
                            if st.checkbox(f"Confermi?", key=f"conf_var_{v['id']}"):
                                esegui_query("DELETE FROM variazioni WHERE id = ?", (v['id']), commit=True)
                                st.rerun()

# ============================================================================
# RICETTE SEGRETE (VISIONE COMPLETA)
# ============================================================================
def show_ricette_segrete():
    st.markdown("### 🔒 Ricette Segrete")
    
    if st.session_state.user_role not in ['SUPERADMIN', 'ADMIN', 'CUCINA', 'BAR']:
        st.error("⛔ Accesso negato - Quest'area è riservata")
        return
    
    # Filtro per reparto
    reparti = esegui_query("SELECT * FROM reparti ORDER BY nome", fetchall=True)
    filtro_reparto = st.selectbox(
        "Filtra per reparto",
        options=[0] + [r['id'] for r in reparti],
        format_func=lambda x: "📋 TUTTI" if x == 0 else next(r['nome'] for r in reparti if r['id'] == x)
    )
    
    # Query piatti con ricette
    query = """
        SELECT p.*, c.nome as categoria_nome, r.nome as reparto_nome
        FROM piatti p
        JOIN categorie c ON p.categoria_id = c.id
        JOIN reparti r ON c.reparto_id = r.id
        WHERE p.descrizione_privata IS NOT NULL AND p.descrizione_privata != ''
    """
    params = []
    
    if filtro_reparto != 0:
        query += " AND r.id = ?"
        params.append(filtro_reparto)
    
    query += " ORDER BY r.nome, c.nome, p.nome"
    
    piatti = esegui_query(query, tuple(params), fetchall=True)
    
    if not piatti:
        st.info("Nessuna ricetta disponibile")
    else:
        for p in piatti:
            with st.expander(f"🍽️ {p['nome']} - {p['reparto_nome']} / {p['categoria_nome']}"):
                try:
                    ricetta = json.loads(p['descrizione_privata'])
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if p.get('foto_data'):
                            st.image(p['foto_data'], width=200)
                        
                        st.markdown(f"**💰 Prezzo:** {format_currency(p['prezzo'])}")
                        st.markdown(f"**⏱️ Tempo:** {p['tempo_preparazione']} min")
                    
                    with col2:
                        st.markdown("**🥗 Ingredienti:**")
                        st.write(ricetta.get('ingredienti', 'N/A'))
                    
                    st.divider()
                    st.markdown("**👨‍🍳 Preparazione:**")
                    st.write(ricetta.get('preparazione', 'N/A'))
                    
                    st.markdown("**📝 Note cucina:**")
                    st.write(ricetta.get('note_cucina', 'N/A'))
                    
                    if ricetta.get('allergeni'):
                        st.warning(f"⚠️ Allergeni: {', '.join(ricetta['allergeni'])}")
                        
                except Exception as e:
                    st.error(f"Errore nel leggere la ricetta: {e}")

# ============================================================================
# BACKUP E RIPRISTINO (PASSO 7B - VERSIONE COMPLETA)
# ============================================================================
def show_backup():
    st.subheader("💾 Gestione Backup")
    
    # Tabs per le diverse funzionalità
    tab_backup, tab_restore, tab_config, tab_pulizia = st.tabs(["🔄 BACKUP", "📂 RIPRISTINA", "⚙️ CONFIGURAZIONE", "🧹 PULIZIA"])
    
    with tab_backup:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("### 📊 Stato Database")
            
            # Info database
            try:
                from db import DB_PATH
                db_size = os.path.getsize(DB_PATH)
                db_modified = datetime.fromtimestamp(os.path.getmtime(DB_PATH))
                
                st.metric("Dimensione database", f"{db_size/1024:.1f} KB" if db_size < 1024*1024 else f"{db_size/(1024*1024):.1f} MB")
                st.caption(f"Ultima modifica: {db_modified.strftime('%d/%m/%Y %H:%M')}")
                
                # Conta record
                conn = sqlite3.connect(DB_PATH)
                cursor = conn.cursor()
                
                tables = ['utenti', 'piatti', 'comande', 'pagamenti']
                for table in tables:
                    try:
                        cursor.execute(f"SELECT COUNT(*) FROM {table}")
                        count = cursor.fetchone()[0]
                        st.write(f"📋 {table}: {count} record")
                    except:
                        pass
                conn.close()
                
            except Exception as e:
                st.error(f"Errore lettura database: {e}")
        
        with col2:
            st.markdown("### 🆕 Crea Backup")
            
            if st.button("🔄 CREA BACKUP MANUALE", type="primary", use_container_width=True):
                with st.spinner("Creazione backup in corso..."):
                    from db import crea_backup_manual
                    path = crea_backup_manual()
                    if path:
                        st.success(f"✅ Backup creato con successo!")
                        st.caption(f"File: {os.path.basename(path)}")
                        st.balloons()
                    else:
                        st.error("❌ Errore durante la creazione del backup")
            
            st.markdown("---")
            st.markdown("### 📋 Ultimi Backup")
            
            from db import get_backup_list
            backup_list = get_backup_list()
            
            if not backup_list:
                st.info("Nessun backup disponibile")
            else:
                for backup in backup_list[:5]:  # Mostra solo ultimi 5
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([3, 1, 1])
                        with col1:
                            st.write(f"📅 {backup['timestamp'].strftime('%d/%m/%Y %H:%M')}")
                            st.caption(backup['size_str'])
                        with col2:
                            if st.button("📥", key=f"download_{backup['filename']}", help="Scarica backup"):
                                with open(backup['path'], 'rb') as f:
                                    st.download_button(
                                        "💾 Salva",
                                        data=f,
                                        file_name=backup['filename'],
                                        mime="application/octet-stream",
                                        key=f"download_btn_{backup['filename']}"
                                    )
                        with col3:
                            if st.button("🗑️", key=f"del_{backup['filename']}", help="Elimina backup"):
                                from db import elimina_backup
                                success, msg = elimina_backup(backup['path'])
                                if success:
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
    
    with tab_restore:
        st.markdown("### 📂 Ripristino Database")
        st.warning("⚠️ **ATTENZIONE**: Il ripristino sovrascriverà il database corrente. Tutti i dati non salvati andranno persi.")
        
        from db import get_backup_list, ripristina_backup
        backup_list = get_backup_list()
        
        if not backup_list:
            st.info("Nessun backup disponibile per il ripristino")
        else:
            # Crea opzioni per selectbox
            backup_options = {
                backup['path']: f"{backup['timestamp'].strftime('%d/%m/%Y %H:%M')} - {backup['size_str']}"
                for backup in backup_list
            }
            
            selected_backup = st.selectbox(
                "Seleziona backup da ripristinare",
                options=list(backup_options.keys()),
                format_func=lambda x: backup_options[x]
            )
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 RIPRISTINA BACKUP", type="primary", use_container_width=True):
                    with st.spinner("Ripristino in corso..."):
                        success, msg = ripristina_backup(selected_backup)
                        if success:
                            st.success(f"✅ {msg}")
                            st.warning("🔄 Riavvia l'app per applicare le modifiche")
                            if st.button("🔄 RIAVVIA ORA"):
                                st.rerun()
                        else:
                            st.error(f"❌ Errore: {msg}")
            
            with col2:
                if st.button("❌ ANNULLA", use_container_width=True):
                    st.rerun()
    
    with tab_config:
        st.markdown("### ⚙️ Configurazione Backup Automatico")
        
        from db import carica_config_backup, configura_backup_automatico
        
        config = carica_config_backup()
        
        with st.form("config_backup"):
            interval = st.number_input(
                "Intervallo backup (ore)",
                min_value=1,
                max_value=168,
                value=config['interval'],
                help="Ogni quante ore creare un backup automatico"
            )
            
            max_backups = st.number_input(
                "Numero massimo backup",
                min_value=1,
                max_value=50,
                value=config['max_backups'],
                help="Numero massimo di backup da mantenere (i più vecchi vengono eliminati)"
            )
            
            st.markdown("---")
            st.info("📌 I backup vengono salvati nella cartella 'backup' del progetto")
            
            if st.form_submit_button("💾 SALVA CONFIGURAZIONE", type="primary"):
                from db import configura_backup_automatico
                if configura_backup_automatico(interval, max_backups):
                    st.success("✅ Configurazione salvata!")
                    st.rerun()
                else:
                    st.error("❌ Errore nel salvataggio")
    
    with tab_pulizia:
        mostra_pulizia_backup()


def mostra_pulizia_backup(prefix="pulizia"):
    """Interfaccia per pulizia automatica backup
    Args:
        prefix: Prefisso per le chiavi (default 'pulizia')
    """
    st.header("🧹 Pulizia Automatica Backup")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("⚙️ Configurazione")
        
        # Carica configurazione attuale
        config = carica_config_pulizia()
        
        mantenere = st.number_input(
            "Numero backup da mantenere",
            min_value=1,
            max_value=50,
            value=config['mantenere'],
            key=f"{prefix}_mantenere"
        )
        
        giorni_vecchi = st.number_input(
            "Elimina backup più vecchi di (giorni)",
            min_value=7,
            max_value=365,
            value=config['giorni_vecchi'],
            key=f"{prefix}_giorni"
        )
        
        auto_compress = st.checkbox(
            "Comprimi automaticamente backup vecchi",
            value=config['auto_compress'],
            key=f"{prefix}_compress"
        )
        
        if st.button("💾 Salva Configurazione", type="primary", key=f"{prefix}_save"):
            if configura_pulizia_backup(mantenere, giorni_vecchi, auto_compress):
                st.success("✅ Configurazione salvata!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("❌ Errore salvataggio configurazione")
    
    with col2:
        st.subheader("📊 Statistiche Backup")
        
        backup_list = get_backup_list()
        if backup_list:
            totale_backup = len(backup_list)
            spazio_totale = sum(b['size'] for b in backup_list)
            
            st.metric("Totale backup", totale_backup, key=f"{prefix}_metric_totale")
            st.metric("Spazio occupato", f"{spazio_totale/(1024*1024):.2f} MB", key=f"{prefix}_metric_spazio")
            
            # Backup più vecchio
            if backup_list:
                piu_vecchio = backup_list[-1]
                st.metric("Backup più vecchio", 
                         piu_vecchio['timestamp'].strftime("%d/%m/%Y"),
                         f"{piu_vecchio.get('giorni', 0)} giorni fa",
                         key=f"{prefix}_metric_vecchio")
        else:
            st.info("Nessun backup presente", icon="ℹ️")
    
    st.divider()
    
    # Sezione pulizia manuale
    st.subheader("🔄 Pulizia Manuale")
    
    col3, col4, col5 = st.columns(3)
    
    with col3:
        if st.button("🧹 Esegui Pulizia Standard", key=f"{prefix}_std"):
            with st.spinner("Esecuzione pulizia in corso..."):
                risultato = esegui_pulizia_manuale()
                if risultato['eliminati'] > 0 or risultato['compressi'] > 0:
                    st.success(risultato['messaggio'])
                else:
                    st.info("Nessuna azione necessaria")
    
    with col4:
        if st.button("🗑️ Pulizia Aggressiva (mantieni 5)", key=f"{prefix}_agg"):
            with st.spinner("Esecuzione pulizia aggressiva..."):
                risultato = esegui_pulizia_manuale(mantenere=5, giorni_vecchi=15, comprimi=True)
                st.success(risultato['messaggio'])
    
    with col5:
        if st.button("📦 Comprimi Tutti", key=f"{prefix}_comp"):
            with st.spinner("Compressione in corso..."):
                backup_list = get_backup_list()
                compressi = 0
                for backup in backup_list:
                    if not backup['filename'].endswith('.gz'):
                        if comprimi_backup(backup['path']):
                            compressi += 1
                if compressi > 0:
                    st.success(f"✅ {compressi} backup compressi")
                else:
                    st.info("Nessun backup da comprimere")
    
    # Anteprima backup
    st.subheader("📋 Backup Attuali")
    backup_list = get_backup_list()
    if backup_list:
        data = []
        for idx, b in enumerate(backup_list[:10]):
            data.append({
                "File": b['filename'][:30] + "..." if len(b['filename']) > 30 else b['filename'],
                "Data": b['timestamp'].strftime("%d/%m/%Y %H:%M"),
                "Dimensione": b['size_str'],
                "Stato": "📦 Compresso" if b['filename'].endswith('.gz') else "💾 Normale"
            })
        st.dataframe(data, use_container_width=True, key=f"{prefix}_df")
    else:
        st.info("Nessun backup disponibile")

# ============================================================================
# GESTIONE STAMPANTI CON RICERCA AUTOMATICA
# ============================================================================
def show_gestione_stampanti():
    st.subheader("🖨️ Configurazione Stampanti")
    
    # Tabs per le diverse funzionalità
    tab_lista, tab_ricerca, tab_test = st.tabs(["📋 STAMPANTI CONFIGURATE", "🔍 RICERCA AUTOMATICA", "🧪 TEST STAMPA"])
    
    with tab_lista:
        mostra_lista_stampanti()
    
    with tab_ricerca:
        mostra_ricerca_stampanti()
    
    with tab_test:
        mostra_test_stampa()


def mostra_lista_stampanti():
    """Mostra la lista delle stampanti configurate"""
    
    # Pulsante per nuova stampante manuale
    with st.expander("➕ NUOVA STAMPANTE MANUALE", expanded=False):
        with st.form("nuova_stampante_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                nome = st.text_input("Nome stampante *", placeholder="es. Cucina Termica")
                
                # Reparti
                reparti = esegui_query("SELECT * FROM reparti ORDER BY nome", fetchall=True)
                reparto_id = st.selectbox(
                    "Reparto *",
                    options=[r['id'] for r in reparti],
                    format_func=lambda x: next(f"{r['icona']} {r['nome']}" for r in reparti if r['id'] == x)
                )
                
                tipo = st.selectbox(
                    "Tipo interfaccia",
                    ["TERMICA", "FISCALE", "ETICHETTE"]
                )
            
            with col2:
                interfaccia = st.selectbox(
                    "Interfaccia",
                    ["network", "usb", "serial"]
                )
                
                if interfaccia == "network":
                    indirizzo_ip = st.text_input("Indirizzo IP", placeholder="192.168.1.100")
                    porta = st.number_input("Porta", value=9100, min_value=1, max_value=65535)
                    device_path = None
                elif interfaccia == "usb":
                    indirizzo_ip = None
                    porta = None
                    device_path = st.text_input("Device path", placeholder="/dev/usb/lp0")
                else:  # serial
                    indirizzo_ip = None
                    porta = None
                    device_path = st.text_input("Porta COM", placeholder="COM3")
                
                caratteri = st.number_input("Caratteri per riga", value=42, min_value=20, max_value=80)
                stampa_auto = st.checkbox("Stampa automatica", value=True)
            
            if st.form_submit_button("💾 SALVA STAMPANTE", type="primary", use_container_width=True):
                if not nome or not reparto_id:
                    st.error("Nome e reparto sono obbligatori")
                else:
                    try:
                        from db import StampanteService
                        success = StampanteService.aggiungi_stampante(
                            nome=nome,
                            reparto_id=reparto_id,
                            tipo=tipo,
                            indirizzo_ip=indirizzo_ip,
                            porta=porta,
                            device_path=device_path
                        )
                        if success:
                            st.success(f"✅ Stampante '{nome}' aggiunta!")
                            st.rerun()
                        else:
                            st.error("Errore durante il salvataggio")
                    except Exception as e:
                        st.error(f"Errore: {e}")
    
    st.divider()
    
    # Lista stampanti configurate
    st.markdown("### 📋 Stampanti Configurate")
    
    try:
        from db import StampanteService, get_printer_status
        
        stampanti = StampanteService.get_tutte_stampanti()
        
        if not stampanti:
            st.info("Nessuna stampante configurata. Usa la ricerca automatica o aggiungine una manualmente.")
            return
        
        for s in stampanti:
            with st.container(border=True):
                # Ottieni stato
                status = get_printer_status(s['id']) if 'id' in s else None
                
                col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
                
                with col1:
                    reparto_icona = s.get('reparto_icona', '🖨️')
                    st.markdown(f"**{reparto_icona} {s['nome']}**")
                    st.caption(f"Reparto: {s.get('reparto_nome', 'N/A')}")
                
                with col2:
                    if s['interfaccia'] == 'network':
                        st.markdown(f"🌐 {s['indirizzo_ip']}:{s['porta']}")
                    elif s['interfaccia'] == 'usb':
                        st.markdown(f"🔌 {s['device_path']}")
                    else:
                        st.markdown(f"📠 {s['device_path']}")
                
                with col3:
                    if status:
                        if status['connected']:
                            st.success("✅ Online")
                        else:
                            st.error(f"❌ Offline\n{status['message']}")
                    else:
                        if s['attivo']:
                            st.warning("⏳ Stato sconosciuto")
                        else:
                            st.warning("⏸️ Disattiva")
                
                with col4:
                    # Menu azioni
                    with st.popover("⚙️"):
                        if st.button("🔄 Test", key=f"test_{s['id']}", use_container_width=True):
                            if status:
                                if status['connected']:
                                    st.success(f"✅ Connessione OK: {status['message']}")
                                else:
                                    st.error(f"❌ {status['message']}")
                        
                        if st.button("📝 Modifica", key=f"edit_{s['id']}", use_container_width=True):
                            st.session_state.edit_stampante_id = s['id']
                            st.rerun()
                        
                        if st.button("🗑️ Elimina", key=f"del_{s['id']}", use_container_width=True):
                            if st.checkbox(f"Confermi eliminazione {s['nome']}?", key=f"conf_{s['id']}"):
                                from db import StampanteService
                                if StampanteService.elimina_stampante(s['id']):
                                    st.success("✅ Stampante eliminata")
                                    st.rerun()
        
        # Modifica stampante
        if 'edit_stampante_id' in st.session_state:
            mostra_modifica_stampante(st.session_state.edit_stampante_id)
            
    except Exception as e:
        st.error(f"Errore nel caricamento stampanti: {e}")


def mostra_modifica_stampante(printer_id):
    """Modifica una stampante esistente"""
    try:
        from db import StampanteService, esegui_query
        
        stampante = esegui_query("SELECT * FROM stampanti WHERE id = ?", (printer_id,), fetchone=True)
        
        if not stampante:
            st.error("Stampante non trovata")
            del st.session_state.edit_stampante_id
            st.rerun()
            return
        
        st.markdown(f"### ✏️ Modifica: {stampante['nome']}")
        
        with st.form("modifica_stampante_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                nome = st.text_input("Nome stampante", value=stampante['nome'])
                
                reparti = esegui_query("SELECT * FROM reparti ORDER BY nome", fetchall=True)
                reparto_id = st.selectbox(
                    "Reparto",
                    options=[r['id'] for r in reparti],
                    format_func=lambda x: next(f"{r['icona']} {r['nome']}" for r in reparti if r['id'] == x),
                    index=next((i for i, r in enumerate(reparti) if r['id'] == stampante['reparto_id']), 0)
                )
                
                tipo = st.selectbox(
                    "Tipo",
                    ["TERMICA", "FISCALE", "ETICHETTE"],
                    index=["TERMICA", "FISCALE", "ETICHETTE"].index(stampante['tipo'])
                )
            
            with col2:
                interfaccia = st.selectbox(
                    "Interfaccia",
                    ["network", "usb", "serial"],
                    index=["network", "usb", "serial"].index(stampante['interfaccia'])
                )
                
                if interfaccia == "network":
                    indirizzo_ip = st.text_input("Indirizzo IP", value=stampante.get('indirizzo_ip', ''))
                    porta = st.number_input("Porta", value=stampante.get('porta', 9100))
                    device_path = None
                else:
                    indirizzo_ip = None
                    porta = None
                    device_path = st.text_input("Device path", value=stampante.get('device_path', ''))
                
                caratteri = st.number_input("Caratteri per riga", value=stampante.get('caratteri_per_riga', 42))
                attivo = st.checkbox("Stampante attiva", value=bool(stampante['attivo']))
            
            col_save, col_cancel = st.columns(2)
            with col_save:
                if st.form_submit_button("💾 SALVA MODIFICHE", type="primary", use_container_width=True):
                    try:
                        success = StampanteService.aggiorna_stampante(
                            printer_id,
                            nome=nome,
                            reparto_id=reparto_id,
                            tipo=tipo,
                            indirizzo_ip=indirizzo_ip,
                            porta=porta,
                            device_path=device_path,
                            caratteri_per_riga=caratteri,
                            attivo=1 if attivo else 0
                        )
                        if success:
                            st.success("✅ Stampante aggiornata!")
                            del st.session_state.edit_stampante_id
                            st.rerun()
                        else:
                            st.error("Errore durante l'aggiornamento")
                    except Exception as e:
                        st.error(f"Errore: {e}")
            
            with col_cancel:
                if st.form_submit_button("❌ ANNULLA", use_container_width=True):
                    del st.session_state.edit_stampante_id
                    st.rerun()
                    
    except Exception as e:
        st.error(f"Errore: {e}")


def mostra_ricerca_stampanti():
    """Ricerca automatica stampanti USB e di rete"""
    
    st.markdown("### 🔍 Ricerca Automatica Stampanti")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### 💻 Ricerca USB")
        if st.button("🔍 SCANSIONA PORTA USB", type="primary", use_container_width=True):
            with st.spinner("Scansione porte USB in corso..."):
                from db import scan_usb_printers
                usb_printers = scan_usb_printers()
                
                if usb_printers:
                    st.success(f"✅ Trovate {len(usb_printers)} stampanti USB")
                    st.session_state.usb_printers = usb_printers
                else:
                    st.info("Nessuna stampante USB trovata")
    
    with col2:
        st.markdown("#### 🌐 Ricerca Rete")
        
        subnet = st.text_input("Subnet (es. 192.168.1.)", placeholder="192.168.1.", help="Lascia vuoto per auto-rilevamento")
        
        if st.button("🔍 SCANSIONA RETE", type="primary", use_container_width=True):
            with st.spinner("Scansione rete in corso... (ci vorranno circa 30 secondi)"):
                from db import scan_network_printers
                network_printers = scan_network_printers(subnet if subnet else None)
                
                if network_printers:
                    st.success(f"✅ Trovate {len(network_printers)} stampanti di rete")
                    st.session_state.network_printers = network_printers
                else:
                    st.info("Nessuna stampante di rete trovata")
    
    st.divider()
    
    # Mostra risultati USB
    if 'usb_printers' in st.session_state and st.session_state.usb_printers:
        st.markdown("### 💻 Stampanti USB Trovate")
        
        for idx, printer in enumerate(st.session_state.usb_printers):
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.markdown(f"**{printer['nome']}**")
                    st.caption(printer.get('descrizione', ''))
                
                with col2:
                    st.markdown(f"📌 {printer.get('device_path', 'N/A')}")
                    if printer.get('vendor_id'):
                        st.caption(f"VID: {printer['vendor_id']:04x}, PID: {printer['product_id']:04x}")
                
                with col3:
                    if st.button("➕ AGGIUNGI", key=f"add_usb_{idx}"):
                        st.session_state.add_printer = printer
                        st.rerun()
    
    # Mostra risultati rete
    if 'network_printers' in st.session_state and st.session_state.network_printers:
        st.markdown("### 🌐 Stampanti di Rete Trovate")
        
        for idx, printer in enumerate(st.session_state.network_printers):
            with st.container(border=True):
                col1, col2, col3 = st.columns([3, 2, 1])
                
                with col1:
                    st.markdown(f"**{printer['nome']}**")
                
                with col2:
                    st.markdown(f"📌 {printer['indirizzo_ip']}:{printer['porta']}")
                
                with col3:
                    if st.button("➕ AGGIUNGI", key=f"add_net_{idx}"):
                        st.session_state.add_printer = printer
                        st.rerun()
    
    # Form aggiunta stampante trovata
    if 'add_printer' in st.session_state:
        st.divider()
        st.markdown("### ➕ Aggiungi Stampante Trovata")
        
        printer = st.session_state.add_printer
        
        with st.form("aggiungi_stampante_trovata"):
            col1, col2 = st.columns(2)
            
            with col1:
                nome = st.text_input("Nome stampante", value=printer['nome'])
                
                reparti = esegui_query("SELECT * FROM reparti ORDER BY nome", fetchall=True)
                reparto_id = st.selectbox(
                    "Reparto *",
                    options=[r['id'] for r in reparti],
                    format_func=lambda x: next(f"{r['icona']} {r['nome']}" for r in reparti if r['id'] == x)
                )
            
            with col2:
                caratteri = st.number_input("Caratteri per riga", value=42)
                stampa_auto = st.checkbox("Stampa automatica", value=True)
            
            # Mostra dettagli tecnici
            st.markdown("#### 📋 Dettagli Tecnici")
            for key, value in printer.items():
                if key not in ['nome', 'descrizione'] and value:
                    st.text(f"{key}: {value}")
            
            if st.form_submit_button("✅ CONFERMA AGGIUNTA", type="primary", use_container_width=True):
                try:
                    from db import StampanteService
                    
                    # Prepara parametri in base al tipo
                    params = {
                        'nome': nome,
                        'reparto_id': reparto_id,
                        'tipo': 'TERMICA'
                    }
                    
                    if printer.get('interfaccia') == 'network':
                        params['indirizzo_ip'] = printer['indirizzo_ip']
                        params['porta'] = printer.get('porta', 9100)
                    elif printer.get('interfaccia') == 'usb':
                        params['device_path'] = printer['device_path']
                        params['vendor_id'] = printer.get('vendor_id')
                        params['product_id'] = printer.get('product_id')
                    elif printer.get('interfaccia') == 'serial':
                        params['device_path'] = printer['porta']
                    
                    success = StampanteService.aggiungi_stampante(**params)
                    
                    if success:
                        st.success(f"✅ Stampante '{nome}' aggiunta!")
                        del st.session_state.add_printer
                        st.rerun()
                    else:
                        st.error("Errore durante il salvataggio")
                except Exception as e:
                    st.error(f"Errore: {e}")
        
        if st.button("❌ ANNULLA", key="cancel_add_printer"):
            del st.session_state.add_printer
            st.rerun()


def mostra_test_stampa():
    """Pagina per testare le stampanti"""
    
    st.markdown("### 🧪 Test Stampa")
    
    try:
        from db import StampanteService, test_printer_connection
        
        stampanti = StampanteService.get_tutte_stampanti()
        
        if not stampanti:
            st.info("Nessuna stampante configurata. Vai su 'RICERCA AUTOMATICA' per trovare le stampanti.")
            return
        
        # Selezione stampante
        printer_options = {s['id']: f"{s.get('reparto_icona', '🖨️')} {s['nome']}" for s in stampanti}
        printer_id = st.selectbox(
            "Seleziona stampante da testare",
            options=list(printer_options.keys()),
            format_func=lambda x: printer_options[x]
        )
        
        if printer_id:
            printer = next((s for s in stampanti if s['id'] == printer_id), None)
            
            if printer:
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("#### 📋 Dettagli Stampante")
                    st.json({
                        'Nome': printer['nome'],
                        'Reparto': printer.get('reparto_nome', 'N/A'),
                        'Interfaccia': printer['interfaccia'],
                        'IP/Porta': f"{printer.get('indirizzo_ip', 'N/A')}:{printer.get('porta', 'N/A')}" if printer['interfaccia'] == 'network' else 'N/A',
                        'Device': printer.get('device_path', 'N/A')
                    })
                
                with col2:
                    st.markdown("#### 🔌 Test Connessione")
                    if st.button("🔄 TEST CONNESSIONE", use_container_width=True):
                        with st.spinner("Test in corso..."):
                            connected, message = test_printer_connection(printer)
                            if connected:
                                st.success(f"✅ {message}")
                            else:
                                st.error(f"❌ {message}")
                
                st.divider()
                
                # Test di stampa
                st.markdown("#### 🖨️ Test di Stampa")
                
                testo_test = st.text_area(
                    "Testo di prova",
                    value="=" * 42 + "\n" +
                          "  RISTORAPP - TEST STAMPA\n" +
                          "=" * 42 + "\n" +
                          "  Questa è una stampa di prova\n" +
                          "  per verificare il corretto\n" +
                          "  funzionamento della stampante.\n" +
                          "-" * 42 + "\n" +
                          "  Data: " + datetime.now().strftime('%d/%m/%Y %H:%M') + "\n" +
                          "=" * 42 + "\n",
                    height=200
                )
                
                col_stampa, col_anteprima = st.columns(2)
                
                with col_stampa:
                    if st.button("🖨️ INVIA STAMPA DI TEST", type="primary", use_container_width=True):
                        try:
                            # Crea un job di test
                            from db import _print_queue
                            
                            job = {
                                'printer': printer,
                                'content': testo_test,
                                'tipo': 'TEST',
                                'comanda_id': None,
                                'reparto_id': printer['reparto_id']
                            }
                            _print_queue.put(job)
                            st.success("✅ Stampa di test accodata!")
                        except Exception as e:
                            st.error(f"❌ Errore: {e}")
                
                with col_anteprima:
                    if st.button("📄 ANTEPRIMA STAMPA", use_container_width=True):
                        with st.expander("📄 Anteprima", expanded=True):
                            st.code(testo_test, language="text")
    
    except Exception as e:
        st.error(f"Errore: {e}")


def show_qr_code_generator():
    """Genera QR code per ogni tavolo con URL permanente"""
    st.subheader("📱 QR Code per Tavoli")
    
    try:
        import qrcode
        from PIL import Image
        from io import BytesIO
        import base64
    except ImportError:
        st.error("❌ Libreria qrcode non installata. Esegui: pip install qrcode[pil]")
        return
    
    # Recupera tutti i tavoli
    tavoli = TavoloService.get_tutti_tavoli()
    
    if not tavoli:
        st.warning("Nessun tavolo configurato")
        return
    
    # ============================================================================
    # CARICA L'URL DAL DATABASE (ORA CON PERSISTENZA)
    # ============================================================================
    from db import carica_url_pubblico, salva_url_pubblico
    
    # Carica l'URL dal database OGNI VOLTA che la pagina viene caricata
    # Questo garantisce che eventuali modifiche fatte altrove vengano sempre riflesse
    database_url = carica_url_pubblico()
    
    # Aggiorna la sessione se l'URL nel database è diverso
    if 'public_url' not in st.session_state or st.session_state.public_url != database_url:
        st.session_state.public_url = database_url
    
    with st.expander("✏️ MODIFICA URL", expanded=True):
        st.markdown("""
        **Inserisci l'URL pubblico della tua app su Streamlit Cloud**
        
        Esempio: `https://ristorapp-bons72.streamlit.app`
        """)
        
        col1, col2 = st.columns([3, 1])
        with col1:
            nuovo_url = st.text_input(
                "URL:",
                value=st.session_state.public_url,
                key="url_input",
                label_visibility="collapsed"
            )
        with col2:
            if st.button("💾 SALVA", type="primary", use_container_width=True):
                if salva_url_pubblico(nuovo_url):
                    # Aggiorna immediatamente la sessione e forza il ricaricamento
                    st.session_state.public_url = nuovo_url
                    st.success("✅ URL salvato permanentemente!")
                    st.rerun()
    
    base_url = st.session_state.public_url
    st.info(f"🔗 **URL in uso:** `{base_url}`")
    st.divider()
    
    # Raggruppa per sala
    sale = {}
    for t in tavoli:
        if t['sala_nome'] not in sale:
            sale[t['sala_nome']] = []
        sale[t['sala_nome']].append(t)
    
    # Opzioni di personalizzazione
    with st.expander("⚙️ Opzioni QR Code", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            box_size = st.slider("Dimensione QR", min_value=4, max_value=12, value=8)
        with col2:
            border = st.slider("Bordo", min_value=1, max_value=5, value=2)
    
    st.divider()
    
    for nome_sala, tavoli_sala in sale.items():
        st.markdown(f"### 🏢 {nome_sala}")
        cols = st.columns(3)
        
        for i, tavolo in enumerate(tavoli_sala):
            with cols[i % 3]:
                url = f"{base_url}/?tavolo={tavolo['id']}&mode=cliente"
                
                qr = qrcode.QRCode(version=1, box_size=box_size, border=border)
                qr.add_data(url)
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                
                st.markdown(f"**Tavolo {tavolo['numero']}**")
                st.image(buffered.getvalue(), width=150)
                
                st.download_button(
                    label="📥 Download QR",
                    data=buffered.getvalue(),
                    file_name=f"tavolo_{tavolo['numero']}.png",
                    mime="image/png",
                    key=f"qr_{tavolo['id']}",
                    use_container_width=True
                )
                
                with st.expander("🔗 URL", expanded=False):
                    st.code(url, language="text")

# ============================================================================
# PAGINA NOTIFICHE
# ============================================================================
def show_notifiche():
    st.title("📬 Notifiche")
    
    notifiche = NotificaService.get_non_lette(
        st.session_state.user_id,
        st.session_state.user_role
    )
    
    if not notifiche:
        st.success("Nessuna notifica")
        return
    
    for n in notifiche:
        with st.container(border=True):
            st.markdown(f"**{n['titolo']}**")
            st.markdown(n['messaggio'])
            st.caption(str(n['timestamp_creazione'])[:16])
            if st.button("✓", key=f"read_{n['id']}"):
                NotificaService.segna_letta(n['id'])
                st.rerun()

# ============================================================================
# MAIN
# ============================================================================
def main():
    """Funzione principale"""
    
    # Gestione parametri
    params = {}
    for key, value in st.query_params.items():
        if isinstance(value, list):
            params[key] = value[0] if value else None
        else:
            params[key] = value
    
    # Modalità cliente
    tavolo_id = params.get('tavolo')
    mode = params.get('mode')
    
    if tavolo_id and mode == 'cliente':
        try:
            from cliente import show_cliente_page
            show_cliente_page()
            return
        except Exception as e:
            st.error(f"❌ Errore nel caricamento della pagina cliente: {e}")
            return
    
    # Login normale
    if not st.session_state.logged_in:
        show_login()
        return
    
    show_sidebar()
    
    # ============================================================================
    # VERIFICA DATABASE (DOPO IL LOGIN)
    # ============================================================================
    try:
        import sqlite3
        from db import DB_PATH, get_db_connection
        
        # Verifica lo stato completo del database
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Conta reparti
        cursor.execute("SELECT COUNT(*) as count FROM reparti")
        reparti_count = cursor.fetchone()['count']
        
        # Conta sale
        cursor.execute("SELECT COUNT(*) as count FROM sale")
        sale_count = cursor.fetchone()['count']
        
        # Conta tavoli
        cursor.execute("SELECT COUNT(*) as count FROM tavoli")
        tavoli_count = cursor.fetchone()['count']
        
        conn.close()
        
        # Se manca qualcosa, mostra avviso nella sidebar
        if reparti_count == 0 or sale_count == 0 or tavoli_count == 0:
            st.sidebar.warning("⚠️ Database incompleto")
            st.sidebar.write(f"Reparti: {reparti_count}, Sale: {sale_count}, Tavoli: {tavoli_count}")
            
            # Opzione per ricreare manualmente
            if st.sidebar.button("🔄 RICREA DATABASE"):
                with st.spinner("Ricreazione database in corso..."):
                    from db import init_db
                    init_db(force=True)
                    st.sidebar.success("✅ Database ricreato! Riavvia l'app.")
        else:
            st.sidebar.success(f"✅ Database OK: {reparti_count} reparti, {sale_count} sale, {tavoli_count} tavoli")
            
    except Exception as e:
        st.sidebar.error(f"❌ Errore database: {e}")
        write_debug(f"Errore verifica database: {e}", e)
    
# Routing pagine
    pagina = st.session_state.get('pagina_corrente', 'dashboard')
    
    if pagina == 'dashboard':
        show_dashboard()
    elif pagina == 'sala':
        show_sala()
    elif pagina == 'cucina':
        show_reparto("👨‍🍳 CUCINA", 1, mostra_tutti=True)
    elif pagina == 'pasticceria':
        show_reparto("🍰 PASTICCERIA", 3, mostra_tutti=False)
    elif pagina == 'bar':
        show_reparto("🍸 BAR", 2, mostra_tutti=False)
    elif pagina == 'pizzeria':
        show_reparto("🍕 PIZZERIA", 4, mostra_tutti=False)
    elif pagina == 'cassa':
        show_cassa()
    elif pagina == 'stats':
        show_stats_cassa()
    elif pagina == 'preordini':
        if 'preordine_in_revisione' in st.session_state:
            show_revisione_preordine()
        else:
            show_preordini()
    elif pagina == 'promemoria':  # 🔥 NUOVA PAGINA PER I PROMEMORIA CLIENTI
        mostra_promemoria_clienti()
    elif pagina == 'notifiche':
        show_notifiche()
    elif pagina == 'backup':
        show_backup()
    elif pagina == 'pulizia_backup':
        mostra_pulizia_backup(prefix="menu_pulizia")
    elif pagina == 'admin':
        show_amministrazione()
    else:
        show_dashboard()

if __name__ == "__main__":
    main()