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
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='utenti'")
        table_exists = cursor.fetchone()
        conn.close()
        
        if not table_exists:
            write_debug("🔄 Database non inizializzato. Creazione tabelle...")
            with get_db_connection(init_mode=True) as conn:
                cursor = conn.cursor()
                create_tables(cursor)
                create_indexes(cursor)
                populate_initial_data(cursor)
            write_debug("✅ Database inizializzato con successo!")
        else:
            write_debug("✅ Database già esistente e funzionante")
        
        return db_path
    except Exception as e:
        write_debug(f"❌ Errore inizializzazione database: {e}", e)
        return None

# Inizializza il database all'avvio
db_path = init_database()
if db_path:
    os.environ['DB_PATH'] = db_path
    write_debug(f"✅ DB_PATH impostato a: {db_path}")
else:
    write_debug("❌ Inizializzazione database fallita")

# ============================================================================
# IMPORT DAL DB.PY CON GESTIONE ERRORI
# ============================================================================
try:
    from db import (
        get_db_connection, esegui_query, verify_password,
        TavoloService, OrdineService, PagamentoService,
        NotificaService, ReportService
    )
    write_debug("✅ Import da db.py riuscito!")
    
    # Verifica che le classi esistano
    write_debug(f"✅ TavoloService: {TavoloService}")
    write_debug(f"✅ OrdineService: {OrdineService}")
    write_debug(f"✅ PagamentoService: {PagamentoService}")
    
except Exception as e:
    write_debug("❌ ERRORE IMPORT da db.py", e)
    # Mostra l'errore anche nell'interfaccia
    st.error(f"Errore di importazione: {e}")
    st.stop()

# ============================================================================
# MOSTRA DEBUG NELL'INTERFACCIA (OPZIONALE)
# ============================================================================
with st.sidebar.expander("🐛 DEBUG INFO", expanded=False):
    try:
        with open(DEBUG_LOG, 'r') as f:
            debug_content = f.read()
        st.text(debug_content[-1000:])  # Mostra ultimi 1000 caratteri
    except:
        st.info("Nessun debug disponibile")

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
# CONFIGURAZIONE PAGINA (SOLO PER LO STAFF)
# ============================================================================
st.set_page_config(
    page_title="PALAZZO FIORINI - Staff",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Auto-refresh intelligente (ogni 3 secondi)
count = st_autorefresh(interval=3000, key="autorefresh")

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
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

init_session_state()

# ============================================================================
# FUNZIONI DI UTILITY
# ============================================================================
def format_currency(amount):
    """Formatta importo in euro"""
    return f"€ {amount:.2f}"

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
# PAGINA DI LOGIN
# ============================================================================
def show_login():
    """Schermata di login"""
    st.markdown("""
        <div style='text-align: center; padding: 2rem;'>
            <h1>🏢 PALAZZO FIORINI</h1>
            <p style='color: #7f8c8d;'>Sistema di Gestione Ristorante</p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.form("login_form", clear_on_submit=True):
            st.markdown("### 🔐 Accedi")
            username = st.text_input("Username", placeholder="Inserisci username")
            password = st.text_input("Password", type="password", placeholder="Inserisci password")
            
            if st.form_submit_button("ACCEDI", use_container_width=True):
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
        st.caption("Utenti di test: admin/admin123, cameriere/123, cucina/123, bar/123, cassa/123")

# ============================================================================
# SIDEBAR
# ============================================================================
def show_sidebar():
    """Menu laterale dinamico"""
    with st.sidebar:
        st.markdown(f"""
            <div style='text-align: center; padding: 1rem;'>
                <h2>🏢 PALAZZO FIORINI</h2>
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
                ("⚙️ AMMINISTRAZIONE", "admin")
            ]
        elif st.session_state.user_role == 'CAMERIERE':
            menu_items = [
                ("🍽️ SALA", "sala"),
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

# ============================================================================
# MODULO SALA
# ============================================================================
def show_sala():
    st.title("🍽️ Sala - Camerieri")
    
    if st.session_state.tavolo_attivo is None:
        show_mappa_tavoli()
    else:
        show_gestione_tavolo()

def show_mappa_tavoli():
    """Mappa interattiva dei tavoli"""
    
    piatti_pronti = esegui_query("""
        SELECT COUNT(*) as cnt FROM comandine
        WHERE stato = 'PRONTO'
    """, fetchone=True)['cnt']
    
    if piatti_pronti > 0:
        st.info(f"🔔 {piatti_pronti} piatti pronti da servire!")
    
    tavoli = TavoloService.get_tutti_tavoli()
    
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
                if tavolo['richiesta_conto'] == 1:
                    icona = "💰"
                    stato = "CONTO RICHIESTO"
                elif tavolo['stato'] == 'OCCUPATO':
                    icona = "👥"
                    stato = "OCCUPATO"
                else:
                    icona = "✅"
                    stato = "LIBERO"
                
                piatti_pronti_tavolo = esegui_query("""
                    SELECT COUNT(*) as cnt FROM comandine cmd
                    JOIN comande c ON cmd.comanda_id = c.id
                    WHERE c.tavolo_id = ? AND cmd.stato = 'PRONTO'
                """, (tavolo['id'],), fetchone=True)['cnt']
                
                if piatti_pronti_tavolo > 0:
                    icona = f"🔔 {piatti_pronti_tavolo}"
                
                if st.button(
                    f"{icona}\n**Tavolo {tavolo['numero']}**",
                    key=f"tavolo_{tavolo['id']}",
                    use_container_width=True,
                    help=stato
                ):
                    st.session_state.tavolo_attivo = tavolo
                    st.rerun()
    
    st.divider()
    
    conti_richiesti = PagamentoService.get_conti_richiesti()
    if conti_richiesti:
        with st.expander("💰 Tavoli con conto richiesto"):
            for c in conti_richiesti:
                st.markdown(f"Tavolo {c['tavolo_numero']} - {format_currency(c['totale'])}")

def show_gestione_tavolo():
    """Gestione ordini per tavolo selezionato"""
    tavolo = st.session_state.tavolo_attivo
    
    col_back, col_title, col_status = st.columns([1, 3, 1])
    
    with col_back:
        if st.button("⬅️ Indietro"):
            st.session_state.tavolo_attivo = None
            st.session_state.carrello = []
            st.session_state.categoria_selezionata = None
            st.rerun()
    
    with col_title:
        st.header(f"🍽️ Tavolo {tavolo['numero']} - {tavolo['sala_nome']}")
    
    with col_status:
        comanda = OrdineService.get_comande_attive(tavolo['id'])
        if comanda:
            st.session_state.comanda_attiva_id = comanda['id']
            st.info("📋 Comanda attiva")
        else:
            st.session_state.comanda_attiva_id = None
    
    if st.session_state.get('comanda_attiva_id'):
        comanda = esegui_query("SELECT * FROM comande WHERE id = ?", 
                               (st.session_state.comanda_attiva_id,), fetchone=True)
    
    tab_categorie, tab_carrello, tab_storico = st.tabs(["📁 CATEGORIE", "🛒 CARRELLO", "📋 STORICO"])
    
    with tab_categorie:
        show_categorie_piatti()
    
    with tab_carrello:
        show_carrello(tavolo, comanda)
    
    with tab_storico:
        show_storico_comanda(comanda)

def show_categorie_piatti():
    """Mostra categorie e piatti con selezione tempo servizio"""
    
    if st.session_state.categoria_selezionata is None:
        categorie = esegui_query("""
            SELECT c.*, COUNT(p.id) as num_piatti
            FROM categorie c
            LEFT JOIN piatti p ON c.id = p.categoria_id AND p.disponibile = 1
            WHERE c.attiva = 1
            GROUP BY c.id
            ORDER BY c.ordine
        """, fetchall=True)
        
        cols = st.columns(2)
        for i, cat in enumerate(categorie):
            with cols[i % 2]:
                if st.button(
                    f"**{cat['nome']}**\n{cat['num_piatti']} piatti",
                    key=f"cat_{cat['id']}",
                    use_container_width=True
                ):
                    st.session_state.categoria_selezionata = cat
                    st.rerun()
    else:
        cat = st.session_state.categoria_selezionata
        
        col_back, col_title = st.columns([1, 3])
        with col_back:
            if st.button("⬅️ Indietro", key="back_from_categories"):
                st.session_state.categoria_selezionata = None
                st.rerun()
        with col_title:
            st.subheader(f"🍽️ {cat['nome']}")
        
        piatti = esegui_query("""
            SELECT * FROM piatti
            WHERE categoria_id = ? AND disponibile = 1
            ORDER BY nome
        """, (cat['id'],), fetchall=True)
        
        if not piatti:
            st.info("Nessun piatto disponibile in questa categoria")
            return
        
        cols = st.columns(2)
        for i, piatto in enumerate(piatti):
            with cols[i % 2]:
                with st.container(border=True):
                    st.markdown(f"**{piatto['nome']}**")
                    st.caption(f"💰 {format_currency(piatto['prezzo'])}")
                    
                    qty = st.number_input(
                        "Qtà",
                        min_value=1,
                        max_value=10,
                        value=1,
                        key=f"qty_{piatto['id']}",
                        label_visibility="collapsed"
                    )
                    
                    st.markdown("---")
                    st.markdown("**⏱️ Tempo di servizio**")
                    
                    opzioni_tempo = ["TEMPO 1", "TEMPO 2", "TEMPO 3", "TEMPO 4"]
                    
                    tempo_map = {
                        "TEMPO 1": {"codice": "TEMPO1", "minuti": 0},
                        "TEMPO 2": {"codice": "TEMPO2", "minuti": 10},
                        "TEMPO 3": {"codice": "TEMPO3", "minuti": 20},
                        "TEMPO 4": {"codice": "TEMPO4", "minuti": 30}
                    }
                    
                    nome_cat = cat['nome'].upper()
                    default_tempo = "TEMPO 2"
                    
                    if 'ANTIPASTO' in nome_cat or 'BEVANDE' in nome_cat:
                        default_tempo = "TEMPO 1"
                    elif 'PRIMO' in nome_cat or 'PASTA' in nome_cat:
                        default_tempo = "TEMPO 2"
                    elif 'SECONDO' in nome_cat or 'CARNE' in nome_cat:
                        default_tempo = "TEMPO 3"
                    elif 'DOLCE' in nome_cat:
                        default_tempo = "TEMPO 4"
                    
                    default_index = opzioni_tempo.index(default_tempo)
                    
                    selected_tempo_label = st.radio(
                        "Seleziona il tempo",
                        options=opzioni_tempo,
                        key=f"tempo_{piatto['id']}",
                        label_visibility="collapsed",
                        index=default_index,
                        horizontal=True
                    )
                    
                    if st.button("➕ AGGIUNGI", key=f"add_{piatto['id']}", use_container_width=True):
                        tempo_data = tempo_map[selected_tempo_label]
                        
                        st.session_state.carrello.append({
                            'id': piatto['id'],
                            'nome': piatto['nome'],
                            'prezzo': piatto['prezzo'],
                            'qty': qty,
                            'note': "",
                            'tempo_codice': tempo_data['codice'],
                            'tempo_nome': selected_tempo_label,
                            'minuti_consegna': tempo_data['minuti'],
                            'categoria': cat['nome']
                        })
                        st.success(f"✅ {qty}x {piatto['nome']} aggiunto!")
                        st.rerun()

def show_carrello(tavolo, comanda):
    """Gestione carrello ordini con tempi servizio"""
    
    if not st.session_state.carrello:
        st.info("🛒 Carrello vuoto")
        return
    
    carrello_raggruppato = []
    for item in st.session_state.carrello:
        trovato = False
        for esistente in carrello_raggruppato:
            if (esistente['id'] == item['id'] and 
                esistente.get('note') == item.get('note') and
                esistente.get('tempo_codice') == item.get('tempo_codice')):
                esistente['qty'] += item['qty']
                trovato = True
                break
        if not trovato:
            carrello_raggruppato.append(item.copy())
    
    st.markdown("### 📋 Riepilogo Ordine")
    
    tempi_ordine = {}
    for item in carrello_raggruppato:
        tempo = item.get('tempo_nome', 'TEMPO 2')
        if tempo not in tempi_ordine:
            tempi_ordine[tempo] = []
        tempi_ordine[tempo].append(item)
    
    totale = 0
    ordine_tempi = ["TEMPO 1", "TEMPO 2", "TEMPO 3", "TEMPO 4"]
    
    for tempo in ordine_tempi:
        if tempo in tempi_ordine:
            st.markdown(f"**{tempo}**")
            for item in tempi_ordine[tempo]:
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.markdown(f"{item['qty']}x {item['nome']}")
                with col2:
                    importo = item['prezzo'] * item['qty']
                    st.markdown(format_currency(importo))
                    totale += importo
                with col3:
                    if st.button("🗑️", key=f"del_{id(item)}"):
                        nuovi = []
                        for orig in st.session_state.carrello:
                            if not (orig['id'] == item['id'] and 
                                  orig.get('tempo_codice') == item.get('tempo_codice')):
                                nuovi.append(orig)
                        st.session_state.carrello = nuovi
                        st.rerun()
    
    st.markdown(f"### Totale: {format_currency(totale)}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ SVUOTA", key="svuota_carrello", use_container_width=True):
            st.session_state.carrello = []
            st.rerun()
    
    with col2:
        if st.button("🚀 INVIA", key="invia_ordine", type="primary", use_container_width=True):
            if not comanda:
                comanda_id = TavoloService.occupa_tavolo(tavolo['id'], st.session_state.user_id)
            else:
                comanda_id = comanda['id']
            
            piatti_per_reparto = {}
            
            for item in st.session_state.carrello:
                piatto_info = esegui_query("""
                    SELECT p.*, c.reparto_id 
                    FROM piatti p
                    JOIN categorie c ON p.categoria_id = c.id
                    WHERE p.id = ?
                """, (item['id'],), fetchone=True)
                
                if piatto_info:
                    reparto_id = piatto_info['reparto_id']
                    
                    esegui_query("""
                        INSERT INTO comandine 
                        (comanda_id, piatto_id, piatto_nome, qty, prezzo_unitario, 
                         note, stato, reparto_id, tempo_consegna, minuti_consegna)
                        VALUES (?, ?, ?, ?, ?, ?, 'NUOVO', ?, ?, ?)
                    """, (comanda_id, item['id'], item['nome'], item['qty'], item['prezzo'],
                          item.get('note', ''), reparto_id, 
                          item.get('tempo_codice', 'TEMPO2'),
                          item.get('minuti_consegna', 10)), commit=True)
                    
                    if reparto_id not in piatti_per_reparto:
                        piatti_per_reparto[reparto_id] = []
                    
                    piatti_per_reparto[reparto_id].append({
                        'piatto_nome': f"{item['nome']} [{item.get('tempo_nome', 'TEMPO 2')}]",
                        'qty': item['qty'],
                        'note': item.get('note', '')
                    })
            
            try:
                from db import StampanteService
                for reparto_id, piatti in piatti_per_reparto.items():
                    StampanteService.stampa_comanda(comanda_id, reparto_id, piatti)
            except Exception as e:
                st.warning(f"⚠️ Stampa non disponibile: {e}")
            
            st.success("✅ Ordine inviato!")
            st.session_state.carrello = []
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
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💰 RICHIEDI CONTO", key="richiedi_conto", type="primary", use_container_width=True):
                success, msg = PagamentoService.richiedi_conto(tavolo_id)
                if success:
                    st.success("✅ Conto richiesto!")
                    st.session_state.tavolo_attivo = None
                    st.session_state.comanda_attiva_id = None
                    st.rerun()
                else:
                    st.error(msg)
        
        with col2:
            if st.button("🔄 LIBERA TAVOLO", key="libera_tavolo", use_container_width=True):
                TavoloService.libera_tavolo(tavolo_id)
                esegui_query("UPDATE comande SET stato = 'CHIUSA' WHERE id = ?", 
                            (comanda['id'],), commit=True)
                st.success("✅ Tavolo liberato!")
                st.session_state.tavolo_attivo = None
                st.session_state.comanda_attiva_id = None
                st.rerun()
    
    elif piatti_attivi == 0 and totali['SERVITO'] == 0 and totali['ANNULLATO'] > 0:
        st.warning("⚠️ Tutti i piatti sono stati annullati")
        
        if st.button("🗑️ CHIUDI TAVOLO", key="chiudi_tavolo", type="primary", use_container_width=True):
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
    
    tab_attesa, tab_revisione, tab_storico = st.tabs(["⏳ IN ATTESA", "👀 DA REVISIONARE", "📜 STORICO"])
    
    with tab_attesa:
        show_preordini_stato('IN_ATTESA')
    with tab_revisione:
        show_preordini_stato('REVISIONATO')
    with tab_storico:
        show_preordini_storico()

def show_revisione_preordine():
    """Mostra dettaglio pre-ordine per revisione con possibilità di modifica"""
    
    # Verifica che abbiamo l'ID del pre-ordine da revisionare
    if 'preordine_id_da_revisionare' not in st.session_state:
        st.info("Nessun pre-ordine selezionato")
        return
    
    preordine_id = st.session_state.preordine_id_da_revisionare
    tavolo_numero = st.session_state.get('tavolo_numero_da_revisionare', 'N/A')
    sala_nome = st.session_state.get('sala_nome_da_revisionare', '')
    
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
    
    # Recupera i dettagli originali per mostrarli
    dettagli_originali = esegui_query("""
        SELECT * FROM preordini_dettaglio WHERE preordine_id = ?
    """, (preordine_id,), fetchall=True)
    
    # Mostra un riepilogo dell'ordine originale prima della revisione
    with st.expander("📋 Ordine originale", expanded=True):
        st.markdown(f"**Tavolo {tavolo_numero} {f'- {sala_nome}' if sala_nome else ''}**")
        if pre.get('note'):
            st.info(f"📝 Note cliente: {pre['note']}")
        
        for d in dettagli_originali:
            st.markdown(f"• {d['qty']}x {d['piatto_nome']} - €{d['prezzo_unitario']:.2f} ciascuno")
            if d.get('note'):
                st.caption(f"  📝 {d['note']}")
    
    st.divider()
    st.markdown("### ✏️ Modifica ordine")
    
    # ... continua con il resto della funzione (menu e carrello) ...

def show_preordini_storico():
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
                    if d.get('variazioni') and d['variazioni'] != '[]':
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
            if d.get('variazioni') and d['variazioni'] != '[]':
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

def conferma_preordine(preordine_id):
    """Converte un pre-ordine in comanda vera e propria"""
    st.success(f"Pre-ordine {preordine_id} confermato!")
    return True

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

def show_conti_da_pagare():
    conti = PagamentoService.get_conti_richiesti()
    
    if not conti:
        st.success("✅ Nessun conto da pagare")
        return
    
    for conto in conti:
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 1, 1])
            
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
                if st.button("💰 PAGA", key=f"paga_{conto['comanda_id']}"):
                    st.session_state.pagamento_in_corso = conto
                    st.rerun()

def show_pagamenti():
    if not st.session_state.pagamento_in_corso:
        st.info("Seleziona un tavolo dalla lista")
        return
    
    conto = st.session_state.pagamento_in_corso
    st.subheader(f"💰 Pagamento Tavolo {conto['tavolo_numero']}")
    
    metodo = st.radio("Metodo di pagamento", ["💵 Contanti", "💳 Carta", "🏦 Bancomat", "🔄 Misto", "💰 Altro"], horizontal=True)
    
    if st.button("✅ CONFERMA PAGAMENTO", type="primary"):
        success = PagamentoService.registra_pagamento(
            conto['comanda_id'], 'CONTANTI',
            contanti=conto['totale'], operatore_id=st.session_state.user_id
        )
        if success:
            st.success("✅ Pagamento registrato!")
            st.session_state.pagamento_in_corso = None
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
    
    tabs = st.tabs(["👥 UTENTI", "🍽️ MENU", "🖨️ STAMPANTI", "📱 QR CODE", "🔄 BACKUP"])
    
    with tabs[0]:
        show_gestione_utenti()
    with tabs[1]:
        show_gestione_menu()
    with tabs[2]:
        show_gestione_stampanti()
    with tabs[3]:
        show_qr_code_generator()
    with tabs[4]:
        show_backup()

def show_gestione_utenti():
    st.subheader("👥 Utenti")
    utenti = esegui_query("SELECT * FROM utenti ORDER BY ruolo, username", fetchall=True)
    for u in utenti:
        st.write(f"{u['nome']} {u['cognome']} - {u['ruolo']}")

def show_gestione_menu():
    st.subheader("🍽️ Gestione Menu")
    st.info("Funzione in sviluppo")

def show_backup():
    st.subheader("💾 Backup")
    if st.button("🔄 CREA BACKUP"):
        from db import backup_automatico
        path = backup_automatico()
        if path:
            st.success(f"Backup creato: {path}")

def show_gestione_stampanti():
    st.subheader("🖨️ Configurazione Stampanti")
    st.info("Funzione in sviluppo")

# ============================================================================
# GENERATORE QR CODE PER TAVOLI (VERSIONE CORRETTA PER STREAMLIT CLOUD)
# ============================================================================
def show_qr_code_generator():
    """Genera QR code per ogni tavolo con URL pubblico"""
    st.subheader("📱 QR Code per Tavoli")
    
    try:
        import qrcode
        from PIL import Image
        from io import BytesIO
        import base64
    except ImportError:
        st.error("❌ Libreria qrcode non installata. Esegui: pip install qrcode[pil]")
        if st.button("🔄 Mostra comando installazione"):
            st.code("pip install qrcode[pil]", language="bash")
        return
    
    # Recupera tutti i tavoli
    tavoli = TavoloService.get_tutti_tavoli()
    
    if not tavoli:
        st.warning("Nessun tavolo configurato")
        return
    
# ============================================================================
# GENERATORE QR CODE PER TAVOLI (VERSIONE CON EDITOR URL)
# ============================================================================
def show_qr_code_generator():
    """Genera QR code per ogni tavolo con URL modificabile"""
    st.subheader("📱 QR Code per Tavoli")
    
    try:
        import qrcode
        from PIL import Image
        from io import BytesIO
        import base64
    except ImportError:
        st.error("❌ Libreria qrcode non installata. Esegui: pip install qrcode[pil]")
        if st.button("🔄 Mostra comando installazione"):
            st.code("pip install qrcode[pil]", language="bash")
        return
    
    # Recupera tutti i tavoli
    tavoli = TavoloService.get_tutti_tavoli()
    
    if not tavoli:
        st.warning("Nessun tavolo configurato")
        return
    
    # ============================================================================
    # EDITOR URL - QUI PUOI MODIFICARE L'URL
    # ============================================================================
    
    # Inizializza l'URL in session state se non esiste
    if 'qr_base_url' not in st.session_state:
        st.session_state.qr_base_url = "http://localhost:8501"
    
    # Crea un expander per modificare l'URL
    with st.expander("✏️ MODIFICA URL", expanded=True):
        st.markdown("""
        **Inserisci l'URL pubblico della tua app su Streamlit Cloud**
        
        Esempio: `https://bons72-ristorapp.streamlit.app`
        """)
        
        # Campo di input per l'URL
        nuovo_url = st.text_input(
            "URL:",
            value=st.session_state.qr_base_url,
            key="url_input"
        )
        
        # Bottone per salvare
        if st.button("💾 SALVA URL"):
            st.session_state.qr_base_url = nuovo_url.rstrip('/')
            st.success(f"✅ URL salvato: {st.session_state.qr_base_url}")
            st.rerun()
    
    # URL corrente
    base_url = st.session_state.qr_base_url
    
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
    
    # Genera QR per ogni tavolo
    for nome_sala, tavoli_sala in sale.items():
        st.markdown(f"### 🏢 {nome_sala}")
        cols = st.columns(3)
        
        for i, tavolo in enumerate(tavoli_sala):
            with cols[i % 3]:
                url = f"{base_url}/?tavolo={tavolo['id']}&mode=cliente"
                
                qr = qrcode.QRCode(
                    version=1,
                    box_size=box_size,
                    border=border
                )
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
    elif pagina == 'notifiche':
        show_notifiche()
    elif pagina == 'admin':
        show_amministrazione()
    else:
        show_dashboard()

if __name__ == "__main__":
    main()