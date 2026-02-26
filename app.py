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
import json  # <--- AGGIUNGI QUESTA RIGA
# ============================================================================
# IMPORT DAL DB.PY
# ============================================================================
from db import (
    get_db_connection, esegui_query, verify_password,
    TavoloService, OrdineService, PagamentoService,
    NotificaService, ReportService
)

# ============================================================================
# ROUTING PER PAGINA CLIENTE
# ============================================================================
def check_cliente_mode():
    """Verifica se siamo in modalità cliente (QR code)"""
    query_params = st.query_params
    return 'tavolo' in query_params and query_params.get('mode', [''])[0] == 'cliente'

# ============================================================================
# CONFIGURAZIONE PAGINA
# ============================================================================
st.set_page_config(
    page_title="PALAZZO FIORINI",
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
        
        # Cassa
        'tavolo_selezionato_cassa': None,
        'pagamento_in_corso': None,
        'input_prezzo': "",
        'carrello_cassa': [],
        
        # UI
        'ultimo_aggiornamento': datetime.now(),
        'notifiche_lette': set()
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
        'NUOVO': '#3498db',      # Blu
        'IN_CORSO': '#f39c12',   # Arancione
        'PRONTO': '#27ae60',     # Verde
        'SERVITO': '#7f8c8d',    # Grigio
        'ANNULLATO': '#e74c3c'   # Rosso
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
                user = esegui_query(
                    "SELECT * FROM utenti WHERE username = ? AND attivo = 1",
                    (username,), fetchone=True
                )
                
                if user and verify_password(user['password_hash'], password):
                    st.session_state.logged_in = True
                    st.session_state.user_id = user['id']
                    st.session_state.username = user['username']
                    st.session_state.user_role = user['ruolo']
                    st.rerun()
                else:
                    st.error("❌ Credenziali non valide")
        
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
        # Variazione rispetto a ieri (esempio)
        st.metric("📈 Performance", "+12%", "vs ieri")
    
    st.divider()
    
    # Grafico vendite
    st.subheader("📈 Andamento Vendite Oggi")
    
    # Dati vendite per ora
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
                # CORREZIONE: converti datetime in stringa
                ora = up['timestamp_pagamento'].strftime('%H:%M') if up['timestamp_pagamento'] else 'N/A'
                st.markdown(f"Tavolo {up['numero']}: {format_currency(up['totale'])} - {ora}")
        else:
            st.info("Nessuna attività recente")

# ============================================================================
# MODULO SALA
# ============================================================================
def show_sala():
    st.title("🍽️ Sala - Camerieri")
    
    # Se nessun tavolo selezionato, mostra mappa
    if st.session_state.tavolo_attivo is None:
        show_mappa_tavoli()
    else:
        show_gestione_tavolo()

def show_mappa_tavoli():
    """Mappa interattiva dei tavoli"""
    
    # Bottone notifiche se ci sono piatti pronti
    piatti_pronti = esegui_query("""
        SELECT COUNT(*) as cnt FROM comandine
        WHERE stato = 'PRONTO'
    """, fetchone=True)['cnt']
    
    if piatti_pronti > 0:
        st.info(f"🔔 {piatti_pronti} piatti pronti da servire!")
    
    # Recupera tutti i tavoli
    tavoli = TavoloService.get_tutti_tavoli()
    
    # Raggruppa per sala
    sale = {}
    for t in tavoli:
        if t['sala_nome'] not in sale:
            sale[t['sala_nome']] = []
        sale[t['sala_nome']].append(t)
    
    # Mostra tavoli per sala
    for nome_sala, tavoli_sala in sale.items():
        st.subheader(f"🏢 {nome_sala}")
        
        # Griglia 4 colonne
        cols = st.columns(4)
        
        for i, tavolo in enumerate(tavoli_sala):
            with cols[i % 4]:
                # Determina stato e colore
                if tavolo['richiesta_conto'] == 1:
                    bg_color = "#f39c12"
                    icona = "💰"
                    stato = "CONTO RICHIESTO"
                elif tavolo['stato'] == 'OCCUPATO':
                    bg_color = "#3498db"
                    icona = "👥"
                    stato = "OCCUPATO"
                else:
                    bg_color = "#27ae60"
                    icona = "✅"
                    stato = "LIBERO"
                
                # Conta piatti pronti per questo tavolo
                piatti_pronti_tavolo = esegui_query("""
                    SELECT COUNT(*) as cnt FROM comandine cmd
                    JOIN comande c ON cmd.comanda_id = c.id
                    WHERE c.tavolo_id = ? AND cmd.stato = 'PRONTO'
                """, (tavolo['id'],), fetchone=True)['cnt']
                
                if piatti_pronti_tavolo > 0:
                    bg_color = "#e74c3c"
                    icona = f"🔔 {piatti_pronti_tavolo}"
                
                # Bottone tavolo
                if st.button(
                    f"{icona}\n**Tavolo {tavolo['numero']}**",
                    key=f"tavolo_{tavolo['id']}",
                    use_container_width=True,
                    help=stato
                ):
                    st.session_state.tavolo_attivo = tavolo
                    st.rerun()
    
    st.divider()
    
    # Lista rapida tavoli con conto richiesto
    conti_richiesti = PagamentoService.get_conti_richiesti()
    if conti_richiesti:
        with st.expander("💰 Tavoli con conto richiesto"):
            for c in conti_richiesti:
                st.markdown(f"Tavolo {c['tavolo_numero']} - {format_currency(c['totale'])}")

def show_gestione_tavolo():
    """Gestione ordini per tavolo selezionato"""
    tavolo = st.session_state.tavolo_attivo
    
    # Header
    col_back, col_title, col_status = st.columns([1, 3, 1])
    
    with col_back:
        if st.button("⬅️ Indietro"):
            st.session_state.tavolo_attivo = None
            st.session_state.carrello = []
            st.session_state.categoria_selezionata = None
            # NON cancelliamo comanda_attiva_id
            st.rerun()
    
    with col_title:
        st.header(f"🍽️ Tavolo {tavolo['numero']} - {tavolo['sala_nome']}")
    
    with col_status:
        # Comanda attiva - SALVA l'ID in session_state
        comanda = OrdineService.get_comande_attive(tavolo['id'])
        if comanda:
            st.session_state.comanda_attiva_id = comanda['id']
            st.info("📋 Comanda attiva")
        else:
            st.session_state.comanda_attiva_id = None
    
    # Recupera la comanda usando l'ID salvato (se esiste)
    if st.session_state.get('comanda_attiva_id'):
        comanda = esegui_query("SELECT * FROM comande WHERE id = ?", 
                               (st.session_state.comanda_attiva_id,), fetchone=True)
    
    # Tabs per navigazione
    tab_categorie, tab_carrello, tab_storico = st.tabs(["📁 CATEGORIE", "🛒 CARRELLO", "📋 STORICO"])
    
    with tab_categorie:
        show_categorie_piatti()
    
    with tab_carrello:
        show_carrello(tavolo, comanda)
    
    with tab_storico:
        show_storico_comanda(comanda)

def show_categorie_piatti():
    """Mostra categorie e piatti con selezione tempo servizio"""
    
    # Se nessuna categoria selezionata, mostra elenco categorie
    if st.session_state.categoria_selezionata is None:
        categorie = esegui_query("""
            SELECT c.*, COUNT(p.id) as num_piatti
            FROM categorie c
            LEFT JOIN piatti p ON c.id = p.categoria_id AND p.disponibile = 1
            WHERE c.attiva = 1
            GROUP BY c.id
            ORDER BY c.ordine
        """, fetchall=True)
        
        # Griglia categorie
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
        # Mostra piatti della categoria selezionata
        cat = st.session_state.categoria_selezionata
        
        col_back, col_title = st.columns([1, 3])
        with col_back:
            if st.button("⬅️ Indietro", key="back_from_categories"):
                st.session_state.categoria_selezionata = None
                st.rerun()
        with col_title:
            st.subheader(f"🍽️ {cat['nome']}")
        
        # Recupera piatti
        piatti = esegui_query("""
            SELECT * FROM piatti
            WHERE categoria_id = ? AND disponibile = 1
            ORDER BY nome
        """, (cat['id'],), fetchall=True)
        
        if not piatti:
            st.info("Nessun piatto disponibile in questa categoria")
            return
        
        # Griglia piatti
        cols = st.columns(2)
        for i, piatto in enumerate(piatti):
            with cols[i % 2]:
                with st.container(border=True):
                    st.markdown(f"**{piatto['nome']}**")
                    st.caption(f"💰 {format_currency(piatto['prezzo'])}")
                    
                    # Selezione quantità
                    qty = st.number_input(
                        "Qtà",
                        min_value=1,
                        max_value=10,
                        value=1,
                        key=f"qty_{piatto['id']}",
                        label_visibility="collapsed"
                    )
                    
                    # SELEZIONE TEMPO SERVIZIO
                    st.markdown("---")
                    st.markdown("**⏱️ Tempo di servizio**")
                    
                    # Opzioni tempo
                    opzioni_tempo = ["TEMPO 1", "TEMPO 2", "TEMPO 3", "TEMPO 4"]
                    
                    # Mappa tempi a valori per il database
                    tempo_map = {
                        "TEMPO 1": {"codice": "TEMPO1", "minuti": 0},
                        "TEMPO 2": {"codice": "TEMPO2", "minuti": 10},
                        "TEMPO 3": {"codice": "TEMPO3", "minuti": 20},
                        "TEMPO 4": {"codice": "TEMPO4", "minuti": 30}
                    }
                    
                    # Suggerimento in base alla categoria
                    nome_cat = cat['nome'].upper()
                    default_tempo = "TEMPO 2"
                    
                    if 'ANTIPASTO' in nome_cat or 'BEVANDE' in nome_cat or 'ACQUA' in nome_cat:
                        default_tempo = "TEMPO 1"
                    elif 'PRIMO' in nome_cat or 'PASTA' in nome_cat or 'RISOTTO' in nome_cat:
                        default_tempo = "TEMPO 2"
                    elif 'SECONDO' in nome_cat or 'CARNE' in nome_cat or 'PESCE' in nome_cat:
                        default_tempo = "TEMPO 3"
                    elif 'DOLCE' in nome_cat or 'DESSERT' in nome_cat:
                        default_tempo = "TEMPO 4"
                    
                    default_index = opzioni_tempo.index(default_tempo)
                    
                    # Radio button per selezione tempo
                    selected_tempo_label = st.radio(
                        "Seleziona il tempo di servizio",
                        options=opzioni_tempo,
                        key=f"tempo_{piatto['id']}",
                        label_visibility="visible",
                        index=default_index,
                        horizontal=True
                    )
                    
                    # Mostra spiegazione del tempo selezionato
                    spiegazione = {
                        "TEMPO 1": "⚡ Servire IMMEDIATAMENTE (prima corsa)",
                        "TEMPO 2": "⏱️ Servire DOPO antipasti/bevande (seconda corsa)",
                        "TEMPO 3": "📅 Servire DOPO i primi (terza corsa)",
                        "TEMPO 4": "🎂 Servire a FINE PASTO (quarta corsa)"
                    }
                    st.caption(spiegazione[selected_tempo_label])
                    
                    # Bottone per aggiungere
                    if st.button("➕ AGGIUNGI AL CARRELLO", key=f"add_{piatto['id']}", use_container_width=True):
                        # Ottieni i valori corrispondenti
                        tempo_data = tempo_map[selected_tempo_label]
                        
                        # Aggiungi al carrello con informazioni di tempo
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
                        st.success(f"✅ {qty}x {piatto['nome']} aggiunto ({selected_tempo_label})!")
                        st.rerun()        

def show_carrello(tavolo, comanda):
    """Gestione carrello ordini con tempi servizio"""
    
    if not st.session_state.carrello:
        st.info("🛒 Carrello vuoto")
        return
    
    # Raggruppa piatti uguali (considerando anche il tempo)
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
    
    # Mostra carrello raggruppato per tempo
    st.markdown("### 📋 Riepilogo Ordine per Tempi")
    
    # Raggruppa per tempo
    tempi_ordine = {}
    for item in carrello_raggruppato:
        tempo = item.get('tempo_nome', 'TEMPO 2')
        if tempo not in tempi_ordine:
            tempi_ordine[tempo] = []
        tempi_ordine[tempo].append(item)
    
    totale = 0
    
    # Ordine dei tempi
    ordine_tempi = ["TEMPO 1", "TEMPO 2", "TEMPO 3", "TEMPO 4"]
    
    for tempo in ordine_tempi:
        if tempo in tempi_ordine:
            if tempo == "TEMPO 1":
                st.markdown("### ⚡ TEMPO 1 - PRIMA CORSA (Immediato)")
            elif tempo == "TEMPO 2":
                st.markdown("### ⏱️ TEMPO 2 - SECONDA CORSA (Dopo antipasti)")
            elif tempo == "TEMPO 3":
                st.markdown("### 📅 TEMPO 3 - TERZA CORSA (Dopo primi)")
            elif tempo == "TEMPO 4":
                st.markdown("### 🎂 TEMPO 4 - QUARTA CORSA (Fine pasto)")
            
            for item in tempi_ordine[tempo]:
                col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
                
                with col1:
                    st.markdown(f"**{item['qty']}x {item['nome']}**")
                    if item.get('minuti_consegna', 0) > 0:
                        st.caption(f"⏱️ Previsto in {item['minuti_consegna']} min")
                
                with col2:
                    importo = item['prezzo'] * item['qty']
                    st.markdown(format_currency(importo))
                    totale += importo
                
                with col3:
                    st.markdown(f"**{item.get('tempo_nome', '')}**")
                
                with col4:
                    if st.button("🗑️", key=f"del_{id(item)}"):
                        # Rimuovi dal carrello originale
                        nuovi = []
                        rimossi = 0
                        for orig in st.session_state.carrello:
                            if (orig['id'] == item['id'] and 
                                orig.get('tempo_codice') == item.get('tempo_codice') and
                                rimossi < item['qty']):
                                rimossi += orig['qty']
                            else:
                                nuovi.append(orig)
                        st.session_state.carrello = nuovi
                        st.rerun()
    
    st.markdown(f"### Totale: {format_currency(totale)}")
    
    # Bottoni azione
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ SVUOTA CARRELLO", key="svuota_carrello", use_container_width=True):
            st.session_state.carrello = []
            st.rerun()
    
    with col2:
        if st.button("🚀 INVIA ORDINE", key="invia_ordine", type="primary", use_container_width=True):
            if not comanda:
                comanda_id = TavoloService.occupa_tavolo(tavolo['id'], st.session_state.user_id)
            else:
                comanda_id = comanda['id']
            
            # Raccogli piatti per reparto
            piatti_per_reparto = {}
            
            # Invia tutti i piatti con le informazioni di tempo
            for item in st.session_state.carrello:
                # Ottieni info piatto per determinare il reparto
                piatto_info = esegui_query("""
                    SELECT p.*, c.reparto_id 
                    FROM piatti p
                    JOIN categorie c ON p.categoria_id = c.id
                    WHERE p.id = ?
                """, (item['id'],), fetchone=True)
                
                if piatto_info:
                    reparto_id = piatto_info['reparto_id']
                    
                    # Aggiungi al database con tempo
                    esegui_query("""
                        INSERT INTO comandine 
                        (comanda_id, piatto_id, piatto_nome, qty, prezzo_unitario, 
                         note, stato, reparto_id, tempo_consegna, minuti_consegna)
                        VALUES (?, ?, ?, ?, ?, ?, 'NUOVO', ?, ?, ?)
                    """, (comanda_id, item['id'], item['nome'], item['qty'], item['prezzo'],
                          item.get('note', ''), reparto_id, 
                          item.get('tempo_codice', 'TEMPO2'),
                          item.get('minuti_consegna', 10)), commit=True)
                    
                    # Raccogli per stampa
                    if reparto_id not in piatti_per_reparto:
                        piatti_per_reparto[reparto_id] = []
                    
                    piatti_per_reparto[reparto_id].append({
                        'piatto_nome': f"{item['nome']} [{item.get('tempo_nome', 'TEMPO 2')}]",
                        'qty': item['qty'],
                        'note': item.get('note', '')
                    })
            
            # Stampa automatica
            try:
                from db import StampanteService
                for reparto_id, piatti in piatti_per_reparto.items():
                    reparto_nome = {1: "CUCINA", 2: "BAR", 3: "PASTICCERIA", 4: "PIZZERIA"}.get(reparto_id, f"REPARTO {reparto_id}")
                    StampanteService.stampa_comanda(comanda_id, reparto_id, piatti)
                    st.success(f"🖨️ Comanda inviata a {reparto_nome}")
            except Exception as e:
                st.warning(f"⚠️ Stampa non disponibile: {e}")
            
            st.success("✅ Ordine inviato con tempi di servizio!")
            st.session_state.carrello = []
            st.rerun()

def show_storico_comanda(comanda):
    """Mostra storico piatti della comanda e gestisce liberazione tavolo"""
    
    if not comanda:
        st.info("Nessuna comanda attiva")
        return
    
    tavolo_id = comanda['tavolo_id']
    piatti = OrdineService.get_piatti_comanda(comanda['id'])
    
    if not piatti:
        st.warning("Nessun piatto in questa comanda")
        
        # Offri la possibilità di chiudere la comanda vuota
        if st.button("🗑️ CHIUDI COMANDA VUOTA", key="chiudi_comanda_vuota"):
            # Chiudi comanda
            esegui_query("UPDATE comande SET stato = 'CHIUSA' WHERE id = ?", 
                        (comanda['id'],), commit=True)
            # Libera tavolo
            TavoloService.libera_tavolo(tavolo_id)
            st.success("✅ Tavolo liberato!")
            st.session_state.tavolo_attivo = None
            st.session_state.comanda_attiva_id = None
            st.rerun()
        return
    
    # Statistiche rapide
    totali = {
        'NUOVO': 0, 'IN_CORSO': 0, 'PRONTO': 0, 'SERVITO': 0, 'ANNULLATO': 0
    }
    for p in piatti:
        totali[p['stato']] += p['qty']
    
    # Calcola piatti ancora attivi (non SERVITO e non ANNULLATO)
    piatti_attivi = totali['NUOVO'] + totali['IN_CORSO'] + totali['PRONTO']
    
    cols = st.columns(5)
    with cols[0]: st.metric("🆕 Nuovi", totali['NUOVO'])
    with cols[1]: st.metric("👨‍🍳 In corso", totali['IN_CORSO'])
    with cols[2]: st.metric("🔔 Pronti", totali['PRONTO'])
    with cols[3]: st.metric("✅ Serviti", totali['SERVITO'])
    with cols[4]: st.metric("❌ Annullati", totali['ANNULLATO'])
    
    st.divider()
    
    # Lista piatti
    for p in piatti:
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
            
            with col1:
                st.markdown(f"**{p['qty']}x {p['piatto_nome']}**")
                if p['note']:
                    st.caption(f"📝 {p['note']}")
                st.caption(f"{p.get('reparto_icona', '')}")
            
            with col2:
                colore = get_stato_colore(p['stato'])
                icona = get_stato_icona(p['stato'])
                st.markdown(f"<span style='color:{colore}'>{icona} {p['stato']}</span>",
                          unsafe_allow_html=True)
            
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
    
    # CASO 1: TUTTI I PIATTI SONO STATI SERVITI
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
            if st.button("🔄 LIBERA TAVOLO", key="libera_tavolo_servito", use_container_width=True):
                # Libera il tavolo senza richiedere conto
                TavoloService.libera_tavolo(tavolo_id)
                # Chiudi la comanda
                esegui_query("UPDATE comande SET stato = 'CHIUSA' WHERE id = ?", 
                            (comanda['id'],), commit=True)
                st.success("✅ Tavolo liberato!")
                st.session_state.tavolo_attivo = None
                st.session_state.comanda_attiva_id = None
                st.rerun()
    
    # CASO 2: TUTTI I PIATTI SONO STATI ANNULLATI (nessuno servito)
    elif piatti_attivi == 0 and totali['SERVITO'] == 0 and totali['ANNULLATO'] > 0:
        st.warning("⚠️ Tutti i piatti sono stati annullati")
        
        if st.button("🗑️ CHIUDI TAVOLO", key="chiudi_tavolo_annullato", type="primary", use_container_width=True):
            # Chiudi la comanda come ANNULLATA
            esegui_query("UPDATE comande SET stato = 'ANNULLATA' WHERE id = ?", 
                        (comanda['id'],), commit=True)
            # Libera il tavolo
            TavoloService.libera_tavolo(tavolo_id)
            st.success("✅ Tavolo liberato!")
            st.session_state.tavolo_attivo = None
            st.session_state.comanda_attiva_id = None
            st.rerun()

def show_reparto(reparto_nome, reparto_id, mostra_tutti=False):
    """Visualizzazione comande per reparto
       Se mostra_tutti=True, mostra tutti i piatti (per CUCINA)
       Altrimenti mostra solo i piatti del reparto specifico
    """
    
    st.title(f"{reparto_nome}")
    
    # Filtri
    col1, col2, col3 = st.columns(3)
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
    
    # Costruisci la query in base a mostra_tutti
    if mostra_tutti:
        # CUCINA - vede tutti i piatti del tavolo
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
        # Altri reparti - vedono solo i propri piatti
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
    
    # Applica filtro stato
    if filtro_stato != "TUTTI":
        if mostra_tutti:
            query += " AND cmd.stato = ?"
            params.append(filtro_stato)
        else:
            query += " AND cmd.stato = ?"
            params.append(filtro_stato)
    
    # Applica filtro tempo
    if filtro_tempo != "TUTTI":
        tempo_db = filtro_tempo.replace(" ", "")
        if mostra_tutti:
            query += " AND cmd.tempo_consegna = ?"
            params.append(tempo_db)
        else:
            query += " AND cmd.tempo_consegna = ?"
            params.append(tempo_db)
    
    query += " ORDER BY cmd.timestamp_inserimento DESC"
    
    comande = esegui_query(query, tuple(params), fetchall=True)
    
    if not comande:
        st.success(f"🎉 Nessuna comanda in attesa per {reparto_nome}!")
        return
    
    # Statistiche rapide
    totale_piatti = len(comande)
    da_fare = sum(1 for c in comande if c['stato'] in ['NUOVO', 'IN_CORSO'])
    pronti = sum(1 for c in comande if c['stato'] == 'PRONTO')
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📋 Totale piatti", totale_piatti)
    with col2:
        st.metric("👨‍🍳 In lavorazione", da_fare)
    with col3:
        st.metric("🔔 Pronti", pronti)
    
    st.divider()
    
    # Raggruppa per tavolo
    tavoli_dict = {}
    for cmd in comande:
        key = f"{cmd['tavolo_numero']}_{cmd['sala_nome']}"
        if key not in tavoli_dict:
            tavoli_dict[key] = {
                'tavolo_numero': cmd['tavolo_numero'],
                'sala_nome': cmd['sala_nome'],
                'piatti': []
            }
        tavoli_dict[key]['piatti'].append(cmd)
    
    # Mostra i piatti per ogni tavolo
    for tavolo_key, tavolo_data in tavoli_dict.items():
        with st.expander(f"🪑 Tavolo {tavolo_data['tavolo_numero']} - {tavolo_data['sala_nome']} ({len(tavolo_data['piatti'])} piatti)", expanded=True):
            
            # Raggruppa per tempo all'interno del tavolo
            piatti_per_tempo = {}
            for p in tavolo_data['piatti']:
                tempo = p['tempo_consegna'] or 'TEMPO2'
                if tempo not in piatti_per_tempo:
                    piatti_per_tempo[tempo] = []
                piatti_per_tempo[tempo].append(p)
            
            # Ordina i tempi
            ordine_tempi = ["TEMPO1", "TEMPO2", "TEMPO3", "TEMPO4"]
            tempo_visuale = {
                "TEMPO1": "⚡ TEMPO 1",
                "TEMPO2": "⏱️ TEMPO 2",
                "TEMPO3": "📅 TEMPO 3",
                "TEMPO4": "🎂 TEMPO 4"
            }
            
            for tempo in ordine_tempi:
                if tempo in piatti_per_tempo:
                    st.markdown(f"**{tempo_visuale.get(tempo, tempo)}**")
                    
                    for p in piatti_per_tempo[tempo]:
                        col1, col2, col3, col4, col5, col6 = st.columns([3, 1, 1, 1, 1, 1])
                        
                        with col1:
                            st.markdown(f"**{p['qty']}x {p['piatto_nome']}**")
                            if p['note']:
                                st.caption(f"📝 {p['note']}")
                        
                        with col2:
                            # Reparto icon
                            st.markdown(f"{p.get('reparto_icona', '🍽️')}")
                        
                        with col3:
                            # Stato con colore
                            stato_icone = {
                                'NUOVO': '🆕',
                                'IN_CORSO': '👨‍🍳',
                                'PRONTO': '🔔',
                                'SERVITO': '✅',
                                'ANNULLATO': '❌'
                            }
                            stato_colori = {
                                'NUOVO': '#3498db',
                                'IN_CORSO': '#f39c12',
                                'PRONTO': '#27ae60',
                                'SERVITO': '#7f8c8d',
                                'ANNULLATO': '#e74c3c'
                            }
                            icona = stato_icone.get(p['stato'], '❓')
                            colore = stato_colori.get(p['stato'], '#95a5a6')
                            st.markdown(f"<span style='color:{colore}'>{icona}</span>",
                                      unsafe_allow_html=True)
                        
                        with col4:
                            # Pulsanti azione
                            if p['stato'] == 'NUOVO' and (mostra_tutti or p['reparto_id'] == reparto_id):
                                if st.button("👨‍🍳", key=f"prendi_{p['commandina_id']}"):
                                    OrdineService.aggiorna_stato(p['commandina_id'], 'IN_CORSO', st.session_state.user_id)
                                    st.rerun()
                            elif p['stato'] == 'IN_CORSO' and (mostra_tutti or p['reparto_id'] == reparto_id):
                                if st.button("🔔", key=f"pronto_{p['commandina_id']}"):
                                    OrdineService.aggiorna_stato(p['commandina_id'], 'PRONTO', st.session_state.user_id)
                                    st.rerun()
                        
                        with col5:
                            # Mostra tempo
                            tempo_mostra = {
                                "TEMPO1": "⚡1",
                                "TEMPO2": "⏱️2",
                                "TEMPO3": "📅3",
                                "TEMPO4": "🎂4"
                            }.get(p['tempo_consegna'], p['tempo_consegna'] or '⏱️2')
                            st.markdown(tempo_mostra)
                        
                        with col6:
                            # Minuti stimati
                            if p.get('minuti_consegna', 0) > 0:
                                st.markdown(f"{p['minuti_consegna']}min")
                    
                    st.markdown("---")

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
    """Visualizza e gestisce i pre-ordini dei clienti"""
    st.title("📋 Pre-ordini Clienti")
    
    # Tabs per stati
    tab_attesa, tab_revisione, tab_storico = st.tabs(["⏳ IN ATTESA", "👀 DA REVISIONARE", "📜 STORICO"])
    
    with tab_attesa:
        show_preordini_stato('IN_ATTESA')
    
    with tab_revisione:
        show_preordini_stato('REVISIONATO')
    
    with tab_storico:
        show_preordini_storico()

def show_preordini_stato(stato):
    """Mostra pre-ordini con un determinato stato"""
    
    preordini = esegui_query("""
        SELECT p.*, t.numero as tavolo_numero, s.nome as sala_nome
        FROM preordini p
        JOIN tavoli t ON p.tavolo_id = t.id
        JOIN sale s ON t.sala_id = s.id
        WHERE p.stato = ?
        ORDER BY p.timestamp_creazione DESC
    """, (stato,), fetchall=True)
    
    if not preordini:
        st.info(f"Nessun pre-ordine {stato}")
        return
    
    for pre in preordini:
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"**🪑 Tavolo {pre['tavolo_numero']} - {pre['sala_nome']}**")
                # CORREZIONE: converti datetime in stringa formattata
                if pre['timestamp_creazione']:
                    data_ora = pre['timestamp_creazione'].strftime('%d/%m/%Y %H:%M')
                else:
                    data_ora = 'N/A'
                st.caption(f"🕐 {data_ora}")
                if pre['note']:
                    st.caption(f"📝 {pre['note']}")
            
            with col2:
                # Recupera dettagli pre-ordine
                dettagli = esegui_query("""
                    SELECT * FROM preordini_dettaglio
                    WHERE preordine_id = ?
                """, (pre['id'],), fetchall=True)
                
                totale = sum(d['qty'] * d['prezzo_unitario'] for d in dettagli)
                st.metric("💰 Totale", format_currency(totale))
                st.caption(f"{len(dettagli)} piatti")
                
                # Mostra anteprima piatti (opzionale)
                with st.expander("📋 Dettaglio", expanded=False):
                    for d in dettagli[:3]:  # Mostra solo primi 3 per non appesantire
                        st.caption(f"  • {d['qty']}x {d['piatto_nome']}")
                    if len(dettagli) > 3:
                        st.caption(f"  ... e altri {len(dettagli)-3}")
            
            with col3:
                if stato == 'IN_ATTESA':
                    if st.button("👀 REVISIONA", key=f"rev_{pre['id']}"):
                        # Pulisci eventuali stati precedenti
                        st.session_state.preordine_in_revisione = pre
                        if 'rev_carrello' in st.session_state:
                            del st.session_state.rev_carrello
                        if 'rev_cat_selezionata' in st.session_state:
                            del st.session_state.rev_cat_selezionata
                        st.rerun()
                elif stato == 'REVISIONATO':
                    if st.button("✅ CONFERMA", key=f"conf_{pre['id']}"):
                        conferma_preordine(pre['id'])
                        st.rerun()
                    if st.button("❌ ANNULLA", key=f"annulla_{pre['id']}"):
                        esegui_query("UPDATE preordini SET stato = 'ANNULLATO' WHERE id = ?", 
                                    (pre['id'],), commit=True)
                        st.rerun()

def show_preordini_storico():
    """Mostra storico pre-ordini (ultimi 30 giorni)"""
    
    preordini = esegui_query("""
        SELECT p.*, t.numero as tavolo_numero, s.nome as sala_nome,
               u.username as cameriere
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
        with st.expander(f"📅 {pre['timestamp_creazione'].strftime('%d/%m/%Y %H:%M') if pre['timestamp_creazione'] else 'N/A'} - Tavolo {pre['tavolo_numero']} - {pre['stato']}"):
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**Stato:** {pre['stato']}")
                if pre['cameriere']:
                    st.markdown(f"**Gestito da:** {pre['cameriere']}")
                if pre['note']:
                    st.markdown(f"**Note:** {pre['note']}")
            
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
    
    if 'preordine_in_revisione' not in st.session_state:
        st.info("Nessun pre-ordine selezionato")
        return
    
    pre = st.session_state.preordine_in_revisione
    
    st.title(f"📋 Revisione Ordine - Tavolo {pre['tavolo_numero']}")
    
    # Header con info
    col_back, col_info = st.columns([1, 3])
    with col_back:
        if st.button("⬅️ Indietro"):
            del st.session_state.preordine_in_revisione
            st.rerun()
    
    with col_info:
        st.caption(f"Ricevuto: {pre['timestamp_creazione'].strftime('%d/%m/%Y %H:%M') if pre['timestamp_creazione'] else 'N/A'}")
        if pre['note']:
            st.info(f"📝 Note cliente: {pre['note']}")
    
    st.divider()
    
    # Recupera dettagli originali
    dettagli = esegui_query("""
        SELECT * FROM preordini_dettaglio
        WHERE preordine_id = ?
    """, (pre['id'],), fetchall=True)
    
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
                'originale': True  # Flag per distinguere piatti originali
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
                    comanda_id = TavoloService.occupa_tavolo(pre['tavolo_id'], st.session_state.user_id)
                    
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
                            reparto_nome = {1: "CUCINA", 2: "BAR", 3: "PASTICCERIA", 4: "PIZZERIA"}.get(reparto_id, f"REPARTO {reparto_id}")
                            StampanteService.stampa_comanda(comanda_id, reparto_id, piatti)
                            st.success(f"🖨️ Comanda inviata a {reparto_nome}")
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
                    del st.session_state.preordine_in_revisione
                    del st.session_state.rev_carrello
                    if 'rev_cat_selezionata' in st.session_state:
                        del st.session_state.rev_cat_selezionata
                    time.sleep(3)
                    st.rerun()
            
            with col_annulla:
                if st.button("❌ ANNULLA ORDINE", use_container_width=True):
                    esegui_query("UPDATE preordini SET stato = 'ANNULLATO' WHERE id = ?", 
                                (pre['id'],), commit=True)
                    del st.session_state.preordine_in_revisione
                    del st.session_state.rev_carrello
                    st.rerun()

def conferma_preordine(preordine_id):
    """Converte un pre-ordine in comanda vera e propria"""
    
    # Recupera pre-ordine
    preordine = esegui_query("SELECT * FROM preordini WHERE id = ?", (preordine_id,), fetchone=True)
    
    if not preordine:
        return False
    
    # Crea nuova comanda
    comanda_id = TavoloService.occupa_tavolo(preordine['tavolo_id'], st.session_state.user_id)
    
    # Recupera dettagli
    dettagli = esegui_query("SELECT * FROM preordini_dettaglio WHERE preordine_id = ?", 
                           (preordine_id,), fetchall=True)
    
    # Trasferisci in comandine
    for d in dettagli:
        # Determina reparto
        piatto_info = esegui_query("""
            SELECT c.reparto_id 
            FROM piatti p
            JOIN categorie c ON p.categoria_id = c.id
            WHERE p.id = ?
        """, (d['piatto_id'],), fetchone=True)
        
        reparto_id = piatto_info['reparto_id'] if piatto_info else 1
        
        esegui_query("""
            INSERT INTO comandine 
            (comanda_id, piatto_id, piatto_nome, qty, prezzo_unitario, 
             note, stato, reparto_id, tempo_consegna, minuti_consegna)
            VALUES (?, ?, ?, ?, ?, ?, 'NUOVO', ?, ?, ?)
        """, (
            comanda_id, d['piatto_id'], d['piatto_nome'], d['qty'], d['prezzo_unitario'],
            d.get('variazioni', ''), reparto_id, 'TEMPO2', 10
        ), commit=True)
    
    # Aggiorna stato pre-ordine
    esegui_query("""
        UPDATE preordini 
        SET stato = 'CONFERMATO', cameriere_id = ?, timestamp_revisione = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (st.session_state.user_id, preordine_id), commit=True)
    
    st.success("✅ Pre-ordine confermato e inviato ai reparti!")
    return True

# ============================================================================
# MODULO CASSA
# ============================================================================
def show_cassa():
    st.title("💰 Cassa")
    
    # Tabs
    tab_conti, tab_pagamenti, tab_stats = st.tabs(["🪑 CONTI DA PAGARE", "💳 PAGAMENTI", "📊 STATS"])
    
    with tab_conti:
        show_conti_da_pagare()
    
    with tab_pagamenti:
        show_pagamenti()
    
    with tab_stats:
        show_stats_cassa()

def show_conti_da_pagare():
    """Lista tavoli con conto richiesto"""
    
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
                st.caption(f"{conto['piatti_totali']} piatti")
            
            with col2:
                st.markdown(f"### {format_currency(conto['totale'])}")
                # CORREZIONE: converti datetime in stringa
                if conto['timestamp_richiesta_conto']:
                    ora = conto['timestamp_richiesta_conto'].strftime('%H:%M')
                    st.caption(f"Richiesto: {ora}")
                else:
                    st.caption("Richiesto: N/A")
            
            with col3:
                if st.button("💰 PAGA", key=f"paga_{conto['comanda_id']}"):
                    st.session_state.pagamento_in_corso = conto
                    st.rerun()

def show_pagamenti():
    """Pagamento tavolo"""
    
    if not st.session_state.pagamento_in_corso:
        st.info("Seleziona un tavolo dalla lista")
        return
    
    conto = st.session_state.pagamento_in_corso
    
    st.subheader(f"💰 Pagamento Tavolo {conto['tavolo_numero']}")
    
    # Dettaglio conto
    with st.expander("🧾 Dettaglio conto", expanded=True):
        piatti = esegui_query("""
            SELECT piatto_nome, qty, prezzo_unitario
            FROM comandine
            WHERE comanda_id = ?
        """, (conto['comanda_id'],), fetchall=True)
        
        for p in piatti:
            st.markdown(f"{p['qty']}x {p['piatto_nome']} - {format_currency(p['prezzo_unitario'] * p['qty'])}")
        st.markdown(f"**Totale: {format_currency(conto['totale'])}**")
    
    st.divider()
    
    # Inizializza variabili di sessione per il pagamento misto
    if 'importi_pagamento' not in st.session_state:
        st.session_state.importi_pagamento = {
            'contanti': 0.0,
            'carta': 0.0,
            'bancomat': 0.0,
            'altri': 0.0
        }
    if 'metodo_selezionato' not in st.session_state:
        st.session_state.metodo_selezionato = "Contanti"
    
    # Metodi di pagamento
    metodo = st.radio(
        "Metodo di pagamento",
        ["💵 Contanti", "💳 Carta", "🏦 Bancomat", "🔄 Misto", "💰 Altro"],
        horizontal=True,
        key="metodo_pagamento"
    )
    
    st.session_state.metodo_selezionato = metodo
    
    # Gestione dei diversi metodi
    if metodo == "💵 Contanti":
        importo = st.number_input(
            "Importo ricevuto",
            min_value=0.0,
            max_value=float(conto['totale']) * 2,
            value=float(conto['totale']),
            step=5.0,
            key="importo_contanti"
        )
        resto = importo - conto['totale']
        
        if importo < conto['totale']:
            st.error(f"❌ Mancano {format_currency(conto['totale'] - importo)}")
            pagamento_completo = False
        else:
            st.success(f"Resto: {format_currency(resto)}")
            pagamento_completo = True
            
            if st.button("✅ CONFERMA PAGAMENTO", key="conferma_contanti", type="primary", use_container_width=True):
                success = PagamentoService.registra_pagamento(
                    conto['comanda_id'], 'CONTANTI',
                    contanti=importo, operatore_id=st.session_state.user_id
                )
                if success:
                    st.success("✅ Pagamento registrato!")
                    st.balloons()
                    st.session_state.pagamento_in_corso = None
                    st.session_state.importi_pagamento = {'contanti': 0, 'carta': 0, 'bancomat': 0, 'altri': 0}
                    time.sleep(2)
                    st.rerun()
    
    elif metodo == "💳 Carta":
        if st.button("✅ CONFERMA PAGAMENTO CON CARTA", key="conferma_carta", type="primary", use_container_width=True):
            success = PagamentoService.registra_pagamento(
                conto['comanda_id'], 'CARTA',
                carta=conto['totale'], operatore_id=st.session_state.user_id
            )
            if success:
                st.success("✅ Pagamento registrato!")
                st.balloons()
                st.session_state.pagamento_in_corso = None
                st.session_state.importi_pagamento = {'contanti': 0, 'carta': 0, 'bancomat': 0, 'altri': 0}
                time.sleep(2)
                st.rerun()
    
    elif metodo == "🏦 Bancomat":
        if st.button("✅ CONFERMA PAGAMENTO CON BANCOMAT", key="conferma_bancomat", type="primary", use_container_width=True):
            success = PagamentoService.registra_pagamento(
                conto['comanda_id'], 'BANCOMAT',
                bancomat=conto['totale'], operatore_id=st.session_state.user_id
            )
            if success:
                st.success("✅ Pagamento registrato!")
                st.balloons()
                st.session_state.pagamento_in_corso = None
                st.session_state.importi_pagamento = {'contanti': 0, 'carta': 0, 'bancomat': 0, 'altri': 0}
                time.sleep(2)
                st.rerun()
    
    elif metodo == "💰 Altro":
        altri = st.number_input("Importo", min_value=0.0, value=float(conto['totale']), step=5.0, key="importo_altri")
        resto = altri - conto['totale']
        
        if altri < conto['totale']:
            st.error(f"❌ Mancano {format_currency(conto['totale'] - altri)}")
        else:
            st.success(f"Resto: {format_currency(resto)}")
            if st.button("✅ CONFERMA PAGAMENTO", key="conferma_altri", type="primary", use_container_width=True):
                success = PagamentoService.registra_pagamento(
                    conto['comanda_id'], 'ALTRO',
                    altri=altri, operatore_id=st.session_state.user_id
                )
                if success:
                    st.success("✅ Pagamento registrato!")
                    st.balloons()
                    st.session_state.pagamento_in_corso = None
                    st.session_state.importi_pagamento = {'contanti': 0, 'carta': 0, 'bancomat': 0, 'altri': 0}
                    time.sleep(2)
                    st.rerun()
    
    elif metodo == "🔄 Misto":
        st.markdown("### 💰 Inserisci gli importi parziali")
        
        col1, col2 = st.columns(2)
        with col1:
            contanti = st.number_input("💵 Contanti", min_value=0.0, value=st.session_state.importi_pagamento['contanti'], step=5.0, key="misto_contanti")
            carta = st.number_input("💳 Carta", min_value=0.0, value=st.session_state.importi_pagamento['carta'], step=5.0, key="misto_carta")
        with col2:
            bancomat = st.number_input("🏦 Bancomat", min_value=0.0, value=st.session_state.importi_pagamento['bancomat'], step=5.0, key="misto_bancomat")
            altri = st.number_input("💰 Altro", min_value=0.0, value=st.session_state.importi_pagamento['altri'], step=5.0, key="misto_altri")
        
        # Aggiorna session state
        st.session_state.importi_pagamento = {
            'contanti': contanti,
            'carta': carta,
            'bancomat': bancomat,
            'altri': altri
        }
        
        totale_inserito = contanti + carta + bancomat + altri
        resto = max(0, totale_inserito - conto['totale'])
        manca = max(0, conto['totale'] - totale_inserito)
        
        # Barra di progresso
        percentuale = min(100, int((totale_inserito / conto['totale']) * 100))
        st.progress(percentuale / 100, text=f"Pagato: {format_currency(totale_inserito)} / {format_currency(conto['totale'])} ({percentuale}%)")
        
        if totale_inserito < conto['totale']:
            st.warning(f"⏳ Ancora da pagare: {format_currency(manca)}")
            
            # Suggerisci importo mancante
            if st.button(f"💰 Completa con {format_currency(manca)} in Contanti", key="completa_contanti"):
                st.session_state.importi_pagamento['contanti'] += manca
                st.rerun()
            
        elif totale_inserito >= conto['totale']:
            st.success(f"💰 Totale pagato: {format_currency(totale_inserito)}")
            if resto > 0:
                st.info(f"Resto da dare: {format_currency(resto)}")
            
            # Bottone conferma pagamento misto
            if st.button("✅ CONFERMA PAGAMENTO MISTO", key="conferma_misto", type="primary", use_container_width=True):
                success = PagamentoService.registra_pagamento(
                    conto['comanda_id'], 'MISTO',
                    contanti=contanti, carta=carta, bancomat=bancomat, altri=altri,
                    operatore_id=st.session_state.user_id
                )
                if success:
                    st.success("✅ Pagamento registrato!")
                    st.balloons()
                    st.session_state.pagamento_in_corso = None
                    st.session_state.importi_pagamento = {'contanti': 0, 'carta': 0, 'bancomat': 0, 'altri': 0}
                    time.sleep(2)
                    st.rerun()
    
    # Bottone annulla comune a tutti i metodi
    if st.button("❌ ANNULLA", key="annulla_pagamento"):
        st.session_state.pagamento_in_corso = None
        st.session_state.importi_pagamento = {'contanti': 0, 'carta': 0, 'bancomat': 0, 'altri': 0}
        st.rerun()

def show_stats_cassa():
    """Statistiche cassa complete e professionali"""
    
    st.title("📊 Report Giornaliero")
    
    # Tabs per diverse visualizzazioni
    tab_oggi, tab_settimana, tab_metodi, tab_piatti, tab_completo = st.tabs([
        "📅 OGGI", 
        "📆 SETTIMANA", 
        "💳 PER METODO",
        "🍽️ PIATTI VENDUTI",
        "📋 REPORT COMPLETO"
    ])
    
    with tab_oggi:
        show_stats_oggi_complete()
    
    with tab_settimana:
        show_stats_settimana_complete()
    
    with tab_metodi:
        show_stats_metodi_complete()
    
    with tab_piatti:
        show_stats_piatti_venduti()
    
    with tab_completo:
        show_report_completo()

def show_stats_oggi_complete():
    """Statistiche complete della giornata"""
    
    # Ottieni statistiche complete
    stats = ReportService.statistiche_complete_oggi()
    incassi_metodi = ReportService.incassi_per_metodo_oggi()
    
    # Assicurati che tutti i valori siano numeri (non None)
    if stats:
        stats['incasso_totale'] = stats.get('incasso_totale', 0) or 0
        stats['totale_scontrini'] = stats.get('totale_scontrini', 0) or 0
        stats['incasso_contanti'] = stats.get('incasso_contanti', 0) or 0
        stats['incasso_carta'] = stats.get('incasso_carta', 0) or 0
        stats['incasso_bancomat'] = stats.get('incasso_bancomat', 0) or 0
        stats['incasso_misto'] = stats.get('incasso_misto', 0) or 0
        stats['incasso_altro'] = stats.get('incasso_altro', 0) or 0
        stats['media_scontrino'] = stats.get('media_scontrino', 0) or 0
    else:
        stats = {
            'incasso_totale': 0,
            'totale_scontrini': 0,
            'incasso_contanti': 0,
            'incasso_carta': 0,
            'incasso_bancomat': 0,
            'incasso_misto': 0,
            'incasso_altro': 0,
            'media_scontrino': 0
        }
    
    # KPI principali in evidenza
    st.subheader("📊 Riepilogo Giornata")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            label="💰 Incasso Totale",
            value=format_currency(stats['incasso_totale']),
            delta=None
        )
    
    with col2:
        st.metric(
            label="🧾 Numero Scontrini",
            value=f"{stats['totale_scontrini']}",
            delta=None
        )
    
    with col3:
        if stats['totale_scontrini'] > 0:
            media = stats['incasso_totale'] / stats['totale_scontrini']
        else:
            media = 0
        st.metric(
            label="📊 Media a Scontrino",
            value=format_currency(media),
            delta=None
        )
    
    with col4:
        st.metric(
            label="🕒 Aggiornato",
            value=datetime.now().strftime("%H:%M:%S"),
            delta=None
        )
    
    st.divider()
    
    # Dettaglio per metodo di pagamento
    st.subheader("💳 Suddivisione per Metodo di Pagamento")
    
    if incassi_metodi:
        # Griglia metodi
        cols = st.columns(len(incassi_metodi))
        
        for i, metodo_data in enumerate(incassi_metodi):
            with cols[i]:
                metodo = metodo_data['metodo']
                totale = metodo_data['totale'] or 0
                num_trans = metodo_data['numero_transazioni'] or 0
                percentuale = (totale / stats['incasso_totale'] * 100) if stats['incasso_totale'] > 0 else 0
                
                # Icona e colore in base al metodo
                if metodo == 'CONTANTI':
                    icona = "💵"
                    colore = "#27ae60"
                    bg_colore = "#27ae6020"
                elif metodo == 'CARTA':
                    icona = "💳"
                    colore = "#3498db"
                    bg_colore = "#3498db20"
                elif metodo == 'BANCOMAT':
                    icona = "🏦"
                    colore = "#9b59b6"
                    bg_colore = "#9b59b620"
                elif metodo == 'MISTO':
                    icona = "🔄"
                    colore = "#e67e22"
                    bg_colore = "#e67e2220"
                else:
                    icona = "💰"
                    colore = "#7f8c8d"
                    bg_colore = "#7f8c8d20"
                
                st.markdown(f"""
                    <div style='background-color: {bg_colore}; padding: 15px; border-radius: 10px; border-left: 5px solid {colore};'>
                        <h3 style='margin:0; color: {colore};'>{icona} {metodo}</h3>
                        <h2 style='margin:10px 0;'>{format_currency(totale)}</h2>
                        <p style='margin:0;'>{num_trans} transazioni</p>
                        <p style='margin:0; font-size:0.9em;'>({percentuale:.1f}%)</p>
                    </div>
                """, unsafe_allow_html=True)
        
        # Dettaglio pagamenti misti (se presenti)
        for metodo_data in incassi_metodi:
            if metodo_data['metodo'] == 'MISTO' and (metodo_data['totale_contanti'] or 0 > 0 or 
                                                     metodo_data['totale_carta'] or 0 > 0 or 
                                                     metodo_data['totale_bancomat'] or 0 > 0 or 
                                                     metodo_data['totale_altri'] or 0 > 0):
                st.divider()
                st.subheader("🔄 Composizione Pagamenti Misti")
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.info(f"💵 Contanti: {format_currency(metodo_data['totale_contanti'] or 0)}")
                with col2:
                    st.info(f"💳 Carta: {format_currency(metodo_data['totale_carta'] or 0)}")
                with col3:
                    st.info(f"🏦 Bancomat: {format_currency(metodo_data['totale_bancomat'] or 0)}")
                with col4:
                    st.info(f"💰 Altro: {format_currency(metodo_data['totale_altri'] or 0)}")
    else:
        st.info("Nessun pagamento registrato oggi")

def show_stats_settimana_complete():
    """Statistiche degli ultimi 7 giorni"""
    
    # Incassi ultimi 7 giorni
    incasso_settimana = esegui_query("""
        SELECT date(timestamp_pagamento) as giorno,
               SUM(totale) as incasso,
               COUNT(*) as scontrini,
               SUM(CASE WHEN metodo = 'CONTANTI' THEN totale ELSE 0 END) as contanti,
               SUM(CASE WHEN metodo = 'CARTA' THEN totale ELSE 0 END) as carta,
               SUM(CASE WHEN metodo = 'BANCOMAT' THEN totale ELSE 0 END) as bancomat,
               SUM(CASE WHEN metodo = 'MISTO' THEN totale ELSE 0 END) as misto
        FROM pagamenti
        WHERE timestamp_pagamento >= date('now', '-7 days')
        GROUP BY date(timestamp_pagamento)
        ORDER BY giorno DESC
    """, fetchall=True)
    
    if incasso_settimana:
        # Calcoli totali
        totale_settimana = sum(d['incasso'] for d in incasso_settimana)
        media_giornaliera = totale_settimana / len(incasso_settimana)
        totale_scontrini = sum(d['scontrini'] for d in incasso_settimana)
        
        # Metriche principali
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("💰 Totale settimana", format_currency(totale_settimana))
        with col2:
            st.metric("📊 Media giornaliera", format_currency(media_giornaliera))
        with col3:
            st.metric("🧾 Totale scontrini", totale_scontrini)
        with col4:
            st.metric("📈 Giorni con dati", len(incasso_settimana))
        
        st.divider()
        
        # Grafico andamento
        st.subheader("📈 Andamento Incassi Giornalieri")
        df = pd.DataFrame(incasso_settimana)
        st.bar_chart(df.set_index('giorno')['incasso'])
        
        st.divider()
        
        # Grafico composizione per metodo (impilato)
        st.subheader("📊 Composizione per Metodo (Giornaliero)")
        df_metodi = df.set_index('giorno')[['contanti', 'carta', 'bancomat', 'misto']]
        st.bar_chart(df_metodi)
        
        st.divider()
        
        # Tabella dettaglio
        st.subheader("📋 Dettaglio Giornaliero")
        for giorno in incasso_settimana:
            with st.expander(f"📅 {giorno['giorno']} - Totale: {format_currency(giorno['incasso'])} ({giorno['scontrini']} scontrini)"):
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("💵 Contanti", format_currency(giorno['contanti'] or 0))
                    st.metric("💳 Carta", format_currency(giorno['carta'] or 0))
                with col2:
                    st.metric("🏦 Bancomat", format_currency(giorno['bancomat'] or 0))
                    st.metric("🔄 Misto", format_currency(giorno['misto'] or 0))
    else:
        st.info("Nessun dato per gli ultimi 7 giorni")

def show_stats_metodi_complete():
    """Statistiche per metodo di pagamento (periodo selezionabile)"""
    
    # Selezione periodo
    periodo = st.radio(
        "Seleziona periodo",
        ["Oggi", "Ultimi 7 giorni", "Ultimi 30 giorni", "Tutti"],
        horizontal=True,
        key="periodo_metodi"
    )
    
    # Query in base al periodo
    if periodo == "Oggi":
        incassi_metodi = ReportService.incassi_per_metodo_oggi()
        totale_giorno = ReportService.incasso_oggi()
        titolo = "📊 Oggi"
    elif periodo == "Ultimi 7 giorni":
        incassi_metodi = ReportService.incassi_per_metodo_settimana()
        totale_giorno = sum(m['totale'] for m in incassi_metodi) if incassi_metodi else 0
        titolo = "📊 Ultimi 7 giorni"
    elif periodo == "Ultimi 30 giorni":
        incassi_metodi = esegui_query("""
            SELECT 
                metodo,
                COUNT(*) as numero_transazioni,
                SUM(totale) as totale,
                SUM(contanti) as totale_contanti,
                SUM(carta) as totale_carta,
                SUM(bancomat) as totale_bancomat,
                SUM(altri) as totale_altri
            FROM pagamenti
            WHERE date(timestamp_pagamento) >= date('now', '-30 days')
            GROUP BY metodo
            ORDER BY totale DESC
        """, fetchall=True)
        totale_giorno = sum(m['totale'] for m in incassi_metodi) if incassi_metodi else 0
        titolo = "📊 Ultimi 30 giorni"
    else:  # Tutti
        incassi_metodi = esegui_query("""
            SELECT 
                metodo,
                COUNT(*) as numero_transazioni,
                SUM(totale) as totale,
                SUM(contanti) as totale_contanti,
                SUM(carta) as totale_carta,
                SUM(bancomat) as totale_bancomat,
                SUM(altri) as totale_altri
            FROM pagamenti
            GROUP BY metodo
            ORDER BY totale DESC
        """, fetchall=True)
        totale_giorno = sum(m['totale'] for m in incassi_metodi) if incassi_metodi else 0
        titolo = "📊 Tutto il periodo"
    
    st.subheader(titolo)
    
    if not incassi_metodi:
        st.info("Nessun dato disponibile per il periodo selezionato")
        return
    
    # Totale periodo
    st.metric("💰 Incasso Totale Periodo", format_currency(totale_giorno))
    
    st.divider()
    
    # Grafico a barre
    st.subheader("📈 Distribuzione per Metodo")
    
    # Prepara dati per il grafico
    df_metodi = pd.DataFrame([
        {'metodo': m['metodo'], 'totale': m['totale']} 
        for m in incassi_metodi
    ])
    
    if not df_metodi.empty:
        st.bar_chart(df_metodi.set_index('metodo')['totale'])
    
    st.divider()
    
    # Tabella dettagliata
    st.subheader("📋 Dettaglio per Metodo")
    
    for metodo_data in incassi_metodi:
        metodo = metodo_data['metodo']
        totale = metodo_data['totale'] or 0
        num_trans = metodo_data['numero_transazioni']
        percentuale = (totale / totale_giorno * 100) if totale_giorno > 0 else 0
        
        # Icona e colore
        if metodo == 'CONTANTI':
            icona = "💵"
            colore = "#27ae60"
        elif metodo == 'CARTA':
            icona = "💳"
            colore = "#3498db"
        elif metodo == 'BANCOMAT':
            icona = "🏦"
            colore = "#9b59b6"
        elif metodo == 'MISTO':
            icona = "🔄"
            colore = "#e67e22"
        else:
            icona = "💰"
            colore = "#7f8c8d"
        
        with st.container(border=True):
            col1, col2, col3, col4 = st.columns([2, 1, 1, 2])
            
            with col1:
                st.markdown(f"<span style='color:{colore}; font-size:1.2em;'>{icona} <b>{metodo}</b></span>", unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"<b>{format_currency(totale)}</b>", unsafe_allow_html=True)
            
            with col3:
                st.markdown(f"{percentuale:.1f}%")
            
            with col4:
                st.markdown(f"{num_trans} transazioni")
            
            # Se è pagamento misto, mostra composizione
            if metodo == 'MISTO' and (metodo_data['totale_contanti'] > 0 or 
                                       metodo_data['totale_carta'] > 0 or 
                                       metodo_data['totale_bancomat'] > 0 or 
                                       metodo_data['totale_altri'] > 0):
                st.caption(f"  💵 {format_currency(metodo_data['totale_contanti'] or 0)} | "
                          f"💳 {format_currency(metodo_data['totale_carta'] or 0)} | "
                          f"🏦 {format_currency(metodo_data['totale_bancomat'] or 0)} | "
                          f"💰 {format_currency(metodo_data['totale_altri'] or 0)}")

def show_stats_piatti_venduti():
    """Statistiche piatti più venduti"""
    
    st.subheader("🍽️ Classifica Piatti più Venduti")
    
    # Selezione periodo
    periodo = st.radio(
        "Periodo",
        ["Oggi", "7 giorni", "30 giorni", "Tutti"],
        horizontal=True,
        key="periodo_piatti"
    )
    
    # Determina data inizio
    if periodo == "Oggi":
        data_inizio = "date('now')"
    elif periodo == "7 giorni":
        data_inizio = "date('now', '-7 days')"
    elif periodo == "30 giorni":
        data_inizio = "date('now', '-30 days')"
    else:
        data_inizio = "date('now', '-9999 days')"
    
    # Query piatti venduti
    piatti = esegui_query(f"""
        SELECT 
            piatto_nome,
            SUM(qty) as quantita_totale,
            COUNT(DISTINCT comanda_id) as numero_ordini,
            SUM(qty * prezzo_unitario) as incasso_totale
        FROM comandine
        WHERE date(timestamp_inserimento) >= {data_inizio}
        GROUP BY piatto_nome
        ORDER BY quantita_totale DESC
        LIMIT 20
    """, fetchall=True)
    
    if not piatti:
        st.info("Nessun piatto venduto nel periodo selezionato")
        return
    
    # Metriche totali
    totale_piatti = sum(p['quantita_totale'] for p in piatti)
    totale_incasso = sum(p['incasso_totale'] for p in piatti)
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric("🍽️ Totale piatti venduti", int(totale_piatti))
    with col2:
        st.metric("💰 Incasso totale", format_currency(totale_incasso))
    
    st.divider()
    
    # Top 10 grafico
    st.subheader("📊 Top 10 Piatti")
    top10 = piatti[:10]
    df_top = pd.DataFrame(top10)
    st.bar_chart(df_top.set_index('piatto_nome')['quantita_totale'])
    
    st.divider()
    
    # Tabella dettaglio
    st.subheader("📋 Dettaglio Piatti")
    
    for i, p in enumerate(piatti, 1):
        with st.container(border=True):
            col1, col2, col3, col4, col5 = st.columns([1, 3, 1, 1, 1])
            
            with col1:
                st.markdown(f"**#{i}**")
            
            with col2:
                st.markdown(f"**{p['piatto_nome']}**")
            
            with col3:
                st.markdown(f"{p['quantita_totale']}x")
            
            with col4:
                st.markdown(format_currency(p['incasso_totale']))
            
            with col5:
                percentuale = (p['quantita_totale'] / totale_piatti * 100)
                st.progress(percentuale / 100, text=f"{percentuale:.1f}%")

def show_report_completo():
    """Report completo giornaliero per stampa/export"""
    
    st.subheader("📋 Report Completo Giornata")
    
    # Data selezione
    data_report = st.date_input(
        "Seleziona data",
        value=datetime.now().date(),
        max_value=datetime.now().date()
    )
    
    if st.button("🔄 GENERA REPORT", type="primary", use_container_width=True):
        # Query report completo
        report = esegui_query("""
            SELECT 
                p.timestamp_pagamento as ora,
                t.numero as tavolo,
                p.metodo,
                p.totale,
                p.contanti,
                p.carta,
                p.bancomat,
                p.altri,
                p.resto,
                u.username as operatore
            FROM pagamenti p
            JOIN comande c ON p.comanda_id = c.id
            JOIN tavoli t ON c.tavolo_id = t.id
            LEFT JOIN utenti u ON p.operatore_id = u.id
            WHERE date(p.timestamp_pagamento) = ?
            ORDER BY p.timestamp_pagamento
        """, (data_report,), fetchall=True)
        
        if report:
            # Calcoli totali
            totale_giorno = sum(r['totale'] for r in report)
            totale_contanti = sum(r['contanti'] or 0 for r in report)
            totale_carta = sum(r['carta'] or 0 for r in report)
            totale_bancomat = sum(r['bancomat'] or 0 for r in report)
            totale_altri = sum(r['altri'] or 0 for r in report)
            
            # Intestazione report
            st.markdown(f"""
            ### 📅 Report Cassa - {data_report.strftime('%d/%m/%Y')}
            
            | Ora | Tavolo | Metodo | Importo | Operatore |
            |-----|--------|--------|---------|-----------|
            """)
            
            # Dettaglio transazioni
            for r in report:
                # CORREZIONE: converti datetime in stringa
                ora = r['ora'].strftime('%H:%M') if r['ora'] else 'N/A'
                st.markdown(f"| {ora} | {r['tavolo']} | {r['metodo']} | {format_currency(r['totale'])} | {r['operatore'] or 'N/A'} |")
            
            # Totali
            st.divider()
            col1, col2, col3, col4, col5 = st.columns(5)
            with col1:
                st.metric("💰 Totale", format_currency(totale_giorno))
            with col2:
                st.metric("💵 Contanti", format_currency(totale_contanti))
            with col3:
                st.metric("💳 Carta", format_currency(totale_carta))
            with col4:
                st.metric("🏦 Bancomat", format_currency(totale_bancomat))
            with col5:
                st.metric("💰 Altro", format_currency(totale_altri))
            
            # Bottone esportazione (simulato)
            if st.button("📥 ESPORTA CSV", use_container_width=True):
                st.success("Report esportato con successo!")
        else:
            st.warning(f"Nessun pagamento registrato per il {data_report.strftime('%d/%m/%Y')}")

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
    """Gestione utenti"""
    
    st.subheader("👥 Utenti")
    
    # Nuovo utente
    with st.expander("➕ Nuovo Utente"):
        with st.form("nuovo_utente"):
            col1, col2 = st.columns(2)
            with col1:
                username = st.text_input("Username")
                nome = st.text_input("Nome")
                password = st.text_input("Password", type="password")
            with col2:
                ruolo = st.selectbox("Ruolo", 
                    ["SUPERADMIN", "ADMIN", "CAMERIERE", "CUCINA", "BAR", "CASSA"])
                cognome = st.text_input("Cognome")
                conferma = st.text_input("Conferma Password", type="password")
            
            if st.form_submit_button("Crea"):
                if password != conferma:
                    st.error("Password non coincidono")
                else:
                    pwd_hash = hashlib.sha256(password.encode()).hexdigest()
                    esegui_query("""
                        INSERT INTO utenti (username, password_hash, nome, cognome, ruolo, brand_id)
                        VALUES (?, ?, ?, ?, ?, 1)
                    """, (username, pwd_hash, nome, cognome, ruolo), commit=True)
                    st.success("Utente creato!")
    
    # Lista utenti
    utenti = esegui_query("""
        SELECT * FROM utenti ORDER BY ruolo, username
    """, fetchall=True)
    
    for u in utenti:
        with st.container(border=True):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{u['nome']} {u['cognome']}** - {u['ruolo']}")
                st.caption(f"@{u['username']}")
            with col2:
                if u['username'] != 'admin' and st.button("🗑️", key=f"del_user_{u['id']}"):
                    esegui_query("UPDATE utenti SET attivo = 0 WHERE id = ?", (u['id'],), commit=True)
                    st.rerun()

def show_gestione_menu():
    """Gestione menu"""
    
    tabs = st.tabs(["📁 CATEGORIE", "🍽️ PIATTI", "✨ VARIAZIONI"])
    
    with tabs[0]:
        show_categorie()
    
    with tabs[1]:
        show_piatti()
    
    with tabs[2]:
        show_variazioni()

def show_categorie():
    """Gestione categorie"""
    
    # Nuova categoria
    with st.form("nuova_categoria"):
        col1, col2, col3 = st.columns(3)
        with col1:
            nome = st.text_input("Nome categoria")
        with col2:
            reparti = esegui_query("SELECT * FROM reparti", fetchall=True)
            reparto_id = st.selectbox("Reparto", 
                options=[r['id'] for r in reparti],
                format_func=lambda x: next(r['nome'] for r in reparti if r['id'] == x)
            )
        with col3:
            ordine = st.number_input("Ordine", min_value=1, value=10)
        
        if st.form_submit_button("➕ Aggiungi"):
            esegui_query("""
                INSERT INTO categorie (nome, reparto_id, ordine)
                VALUES (?, ?, ?)
            """, (nome, reparto_id, ordine), commit=True)
            st.rerun()
    
    # Lista categorie
    categorie = esegui_query("""
        SELECT c.*, r.nome as reparto_nome
        FROM categorie c
        JOIN reparti r ON c.reparto_id = r.id
        ORDER BY c.ordine
    """, fetchall=True)
    
    for cat in categorie:
        with st.container(border=True):
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.markdown(f"**{cat['nome']}** - {cat['reparto_nome']}")
            with col2:
                st.caption(f"Ordine: {cat['ordine']}")
            with col3:
                if st.button("🗑️", key=f"del_cat_{cat['id']}"):
                    esegui_query("UPDATE categorie SET attiva = 0 WHERE id = ?", (cat['id'],), commit=True)
                    st.rerun()

def show_piatti():
    """Gestione piatti con foto e ricette segrete"""
    
    st.subheader("🍽️ Gestione Menu")
    
    # Tabs per gestione
    tab_lista, tab_nuovo = st.tabs(["📋 LISTA PIATTI", "➕ NUOVO PIATTO"])
    
    with tab_nuovo:
        show_nuovo_piatto()
    
    with tab_lista:
        show_lista_piatti()

def show_nuovo_piatto():
    """Form per inserire nuovo piatto con foto"""
    
    with st.form("nuovo_piatto_form", clear_on_submit=True):
        st.markdown("### 📝 Dati Principali")
        
        col1, col2 = st.columns(2)
        with col1:
            nome = st.text_input("Nome piatto *", placeholder="es. Spaghetti Carbonara")
            categorie = esegui_query("SELECT * FROM categorie WHERE attiva = 1", fetchall=True)
            categoria_id = st.selectbox("Categoria *",
                options=[c['id'] for c in categorie],
                format_func=lambda x: next(c['nome'] for c in categorie if c['id'] == x)
            )
            
        with col2:
            prezzo = st.number_input("Prezzo (€) *", min_value=0.0, step=0.5, value=10.0)
            tempo_prep = st.number_input("Tempo preparazione (min)", min_value=1, value=15)
        
        st.divider()
        
        st.markdown("### 📖 Descrizione Pubblica (visibile ai clienti)")
        descrizione_pubblica = st.text_area(
            "Descrizione per il menu",
            placeholder="Ingredienti e descrizione che vedranno i clienti...",
            height=100
        )
        
        st.divider()
        
        st.markdown("### 🔒 Ricetta Segreta (visibile solo a staff)")
        st.warning("⚠️ Questa sezione è visibile solo a cucina, bar e amministrazione")
        
        col_ric1, col_ric2 = st.columns(2)
        with col_ric1:
            ingredienti = st.text_area(
                "Ingredienti",
                placeholder="Elenco ingredienti con quantità...",
                height=150
            )
            preparazione = st.text_area(
                "Procedimento",
                placeholder="Passaggi per la preparazione...",
                height=150
            )
        
        with col_ric2:
            note_cucina = st.text_area(
                "Note per la cucina",
                placeholder="Temperatura, cottura, presentazione...",
                height=150
            )
            allergeni = st.multiselect(
                "Allergeni",
                ["Glutine", "Lattosio", "Uova", "Soia", "Frutta a guscio", "Crostacei", "Pesce", "Sedano"]
            )
        
        st.divider()
        
        st.markdown("### 📸 Foto del Piatto")
        foto_file = st.file_uploader(
            "Carica immagine (JPG, PNG)",
            type=['jpg', 'jpeg', 'png'],
            help="Seleziona una foto dal tuo computer"
        )
        
        if foto_file:
            # Mostra anteprima
            st.image(foto_file, width=200, caption="Anteprima")
            
            # Converti in bytes per salvare nel DB
            foto_bytes = foto_file.getvalue()
            st.session_state['temp_foto'] = foto_bytes
        
        st.divider()
        
        col_disp, col_submit = st.columns(2)
        with col_disp:
            disponibile = st.checkbox("Piatto disponibile", value=True)
        
        with col_submit:
            submitted = st.form_submit_button("💾 SALVA PIATTO", type="primary", use_container_width=True)
        
        if submitted:
            if not nome or not categoria_id or prezzo <= 0:
                st.error("❌ Compila tutti i campi obbligatori (*)")
            else:
                # Combina ricetta segreta in un unico campo JSON
                ricetta_json = json.dumps({
                    'ingredienti': ingredienti,
                    'preparazione': preparazione,
                    'note_cucina': note_cucina,
                    'allergeni': allergeni
                })
                
                # Salva piatto con foto
                if 'temp_foto' in st.session_state and st.session_state['temp_foto']:
                    esegui_query("""
                        INSERT INTO piatti 
                        (nome, categoria_id, prezzo, descrizione_pubblica, 
                         descrizione_privata, tempo_preparazione, foto_data, disponibile)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (nome, categoria_id, prezzo, descrizione_pubblica, 
                          ricetta_json, tempo_prep, st.session_state['temp_foto'], 
                          1 if disponibile else 0), commit=True)
                    del st.session_state['temp_foto']
                else:
                    esegui_query("""
                        INSERT INTO piatti 
                        (nome, categoria_id, prezzo, descrizione_pubblica, 
                         descrizione_privata, tempo_preparazione, disponibile)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (nome, categoria_id, prezzo, descrizione_pubblica, 
                          ricetta_json, tempo_prep, 1 if disponibile else 0), commit=True)
                
                st.success(f"✅ Piatto '{nome}' creato con successo!")
                st.balloons()
                time.sleep(2)
                st.rerun()

def show_lista_piatti():
    """Lista piatti con opzioni di modifica"""
    
    # Filtri
    col1, col2, col3 = st.columns(3)
    with col1:
        categorie = esegui_query("SELECT * FROM categorie WHERE attiva = 1", fetchall=True)
        cat_options = {0: "TUTTE"} | {c['id']: c['nome'] for c in categorie}
        filtro_cat = st.selectbox(
            "Filtra categoria",
            options=list(cat_options.keys()),
            format_func=lambda x: cat_options[x]
        )
    
    # Query piatti
    query = """
        SELECT p.*, c.nome as categoria_nome
        FROM piatti p
        JOIN categorie c ON p.categoria_id = c.id
    """
    params = []
    
    if filtro_cat != 0:
        query += " WHERE p.categoria_id = ?"
        params.append(filtro_cat)
    
    query += " ORDER BY c.nome, p.nome"
    
    piatti = esegui_query(query, tuple(params), fetchall=True)
    
    if not piatti:
        st.info("Nessun piatto trovato")
        return
    
    for p in piatti:
        with st.expander(f"🍽️ {p['nome']} - {p['categoria_nome']} ({format_currency(p['prezzo'])})", expanded=False):
            
            col1, col2 = st.columns([1, 2])
            
            with col1:
                # Mostra foto se presente
                if p.get('foto_data'):
                    st.image(p['foto_data'], width=150)
                else:
                    st.image("https://via.placeholder.com/150?text=Nessuna+foto", width=150)
                
                # Stato disponibilità
                if p['disponibile']:
                    st.success("✅ Disponibile")
                else:
                    st.error("❌ Non disponibile")
            
            with col2:
                # Tabs per diverse info
                tab_pub, tab_priv, tab_mod = st.tabs(["📖 Pubblico", "🔒 Ricetta", "✏️ Modifica"])
                
                with tab_pub:
                    st.markdown("**Descrizione:**")
                    st.write(p['descrizione_pubblica'] or "Nessuna descrizione")
                    st.markdown(f"**Prezzo:** {format_currency(p['prezzo'])}")
                    st.markdown(f"**Tempo preparazione:** {p['tempo_preparazione']} min")
                
                with tab_priv:
                    # Solo per staff autorizzato
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
                                    st.markdown("**⚠️ Allergeni:**")
                                    st.write(", ".join(ricetta['allergeni']))
                            except:
                                st.write(p['descrizione_privata'])
                        else:
                            st.info("Nessuna ricetta segreta")
                    else:
                        st.error("⛔ Accesso negato - Area riservata")
                
                with tab_mod:
                    # Bottoni modifica
                    col_mod1, col_mod2, col_mod3 = st.columns(3)
                    with col_mod1:
                        if st.button("✏️ Modifica", key=f"edit_{p['id']}"):
                            st.session_state.edit_piatto_id = p['id']
                            st.rerun()
                    with col_mod2:
                        nuovo_stato = "❌ Disabilita" if p['disponibile'] else "✅ Abilita"
                        if st.button(nuovo_stato, key=f"toggle_{p['id']}"):
                            esegui_query("UPDATE piatti SET disponibile = ? WHERE id = ?", 
                                        (0 if p['disponibile'] else 1, p['id']), commit=True)
                            st.rerun()
                    with col_mod3:
                        if st.button("🗑️ Elimina", key=f"del_{p['id']}"):
                            if st.checkbox(f"Confermi eliminazione di {p['nome']}?", key=f"conf_{p['id']}"):
                                esegui_query("DELETE FROM piatti WHERE id = ?", (p['id'],), commit=True)
                                st.rerun()

# ============================================================================
# FUNZIONE VARIAZIONI (AGGIUNTA)
# ============================================================================
def show_variazioni():
    """Gestione variazioni"""
    
    st.subheader("✨ Gestione Variazioni")
    
    tabs = st.tabs(["📋 LISTA VARIAZIONI", "➕ NUOVA VARIAZIONE"])
    
    with tabs[1]:
        with st.form("nuova_variazione"):
            col1, col2, col3 = st.columns(3)
            with col1:
                nome = st.text_input("Nome variazione *", placeholder="es. Mozzarella extra")
            with col2:
                prezzo = st.number_input("Prezzo extra (€)", min_value=0.0, step=0.1, value=0.5)
            with col3:
                reparti = esegui_query("SELECT * FROM reparti ORDER BY nome", fetchall=True)
                reparto_id = st.selectbox("Reparto *",
                    options=[r['id'] for r in reparti],
                    format_func=lambda x: next(r['nome'] for r in reparti if r['id'] == x)
                )
            
            col4, col5 = st.columns(2)
            with col4:
                attivo = st.checkbox("Attiva", value=True)
            
            with col5:
                submitted = st.form_submit_button("💾 SALVA VARIAZIONE", type="primary", use_container_width=True)
            
            if submitted:
                if not nome:
                    st.error("❌ Inserisci il nome della variazione")
                else:
                    esegui_query("""
                        INSERT INTO variazioni (nome, prezzo, reparto_id, attivo)
                        VALUES (?, ?, ?, ?)
                    """, (nome, prezzo, reparto_id, 1 if attivo else 0), commit=True)
                    st.success(f"✅ Variazione '{nome}' creata!")
                    st.rerun()
    
    with tabs[0]:
        # Filtri
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            reparti_list = esegui_query("SELECT * FROM reparti", fetchall=True)
            reparti_nomi = ["TUTTI"] + [r['nome'] for r in reparti_list]
            filtro_reparto = st.selectbox("Filtra reparto", reparti_nomi)
        
        # Query variazioni
        query = """
            SELECT v.*, r.nome as reparto_nome
            FROM variazioni v
            JOIN reparti r ON v.reparto_id = r.id
        """
        params = []
        
        if filtro_reparto != "TUTTI":
            query += " WHERE r.nome = ?"
            params.append(filtro_reparto)
        
        query += " ORDER BY r.nome, v.nome"
        
        variazioni = esegui_query(query, tuple(params), fetchall=True)
        
        if not variazioni:
            st.info("Nessuna variazione trovata")
            return
        
        for v in variazioni:
            with st.container(border=True):
                col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 1, 1])
                
                with col1:
                    st.markdown(f"**{v['nome']}**")
                    st.caption(f"📦 {v['reparto_nome']}")
                
                with col2:
                    st.markdown(f"💰 +{format_currency(v['prezzo'])}")
                
                with col3:
                    if v['attivo']:
                        st.success("✅ Attiva")
                    else:
                        st.error("❌ Inattiva")
                
                with col4:
                    if st.button("✏️", key=f"edit_var_{v['id']}"):
                        st.session_state.edit_var_id = v['id']
                        st.rerun()
                
                with col5:
                    if st.button("🗑️", key=f"del_var_{v['id']}"):
                        if st.checkbox(f"Confermi eliminazione?", key=f"conf_del_{v['id']}"):
                            esegui_query("DELETE FROM variazioni WHERE id = ?", (v['id'],), commit=True)
                            st.rerun()

# ============================================================================
# FUNZIONE BACKUP
# ============================================================================
def show_backup():
    """Gestione backup"""
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("💾 Crea Backup")
        if st.button("🔄 CREA BACKUP", use_container_width=True):
            from db import backup_automatico
            path = backup_automatico()
            if path:
                st.success(f"Backup creato: {path}")
    
    with col2:
        st.subheader("📂 Backup Disponibili")
        if os.path.exists("backup"):
            backups = sorted([f for f in os.listdir("backup") if f.endswith('.db')], reverse=True)
            for b in backups[:5]:
                st.caption(b)

# ============================================================================
# FUNZIONE GESTIONE STAMPANTI
# ============================================================================
def show_gestione_stampanti():
    """Configurazione stampanti per reparti"""
    st.subheader("🖨️ Configurazione Stampanti")
    
    from db import StampanteService, esegui_query
    
    # Reparti disponibili
    reparti = esegui_query("SELECT * FROM reparti ORDER BY id", fetchall=True)
    
    # Nuova stampante
    with st.expander("➕ Nuova Stampante"):
        with st.form("nuova_stampante"):
            col1, col2 = st.columns(2)
            with col1:
                nome = st.text_input("Nome stampante")
                reparto_id = st.selectbox(
                    "Reparto",
                    options=[r['id'] for r in reparti],
                    format_func=lambda x: next(r['nome'] for r in reparti if r['id'] == x)
                )
                tipo = st.selectbox("Tipo", ["TERMICA", "FISCALE", "ETICHETTE"])
            with col2:
                indirizzo_ip = st.text_input("Indirizzo IP (es. 192.168.1.100)")
                porta = st.number_input("Porta", value=9100, min_value=1, max_value=65535)
                caratteri = st.number_input("Caratteri per riga", value=42, min_value=20, max_value=80)
            
            st.caption("Per stampanti USB, lascia IP vuoto e specifica VID/PID (opzionale)")
            
            if st.form_submit_button("➕ Aggiungi Stampante"):
                esegui_query("""
                    INSERT INTO stampanti 
                    (nome, reparto_id, tipo, indirizzo_ip, porta, caratteri_per_riga, attivo)
                    VALUES (?, ?, ?, ?, ?, ?, 1)
                """, (nome, reparto_id, tipo, indirizzo_ip, porta, caratteri), commit=True)
                st.success(f"✅ Stampante {nome} aggiunta!")
                st.rerun()
    
    # Lista stampanti
    stampanti = esegui_query("""
        SELECT s.*, r.nome as reparto_nome
        FROM stampanti s
        JOIN reparti r ON s.reparto_id = r.id
        ORDER BY r.id, s.id
    """, fetchall=True)
    
    if stampanti:
        for s in stampanti:
            with st.container(border=True):
                col1, col2, col3, col4, col5 = st.columns([3, 2, 1, 1, 1])
                
                with col1:
                    st.markdown(f"**{s['nome']}**")
                    st.caption(f"{s['reparto_nome']} - {s['indirizzo_ip'] or 'USB'}:{s['porta']}")
                
                with col2:
                    if s['tipo'] == 'TERMICA':
                        st.markdown("🖨️ Termica")
                    elif s['tipo'] == 'FISCALE':
                        st.markdown("🧾 Fiscale")
                    else:
                        st.markdown("🏷️ Etichette")
                
                with col3:
                    st.markdown("✅ Attiva" if s['attivo'] else "❌ Disattiva")
                
                with col4:
                    if st.button("🔄 Test", key=f"test_{s['id']}"):
                        try:
                            from db import StampanteService
                            success, msg = StampanteService.test_stampante(s['id'])
                            if success:
                                st.success(msg)
                            else:
                                st.error(msg)
                        except Exception as e:
                            st.error(f"Errore: {e}")
                
                with col5:
                    if st.button("🗑️", key=f"del_stampante_{s['id']}"):
                        esegui_query("UPDATE stampanti SET attivo = 0 WHERE id = ?", (s['id'],), commit=True)
                        st.rerun()
    else:
        st.info("Nessuna stampante configurata. Aggiungine una usando il form sopra.")
        
        # Suggerimenti configurazione
        with st.expander("📋 Esempi di configurazione"):
            st.markdown("""
            **Per stampanti di rete:**
            - Nome: Stampante Cucina
            - Reparto: CUCINA
            - Tipo: TERMICA
            - IP: 192.168.1.100
            - Porta: 9100
            
            **Per stampanti USB (Windows):**
            - Lascia IP vuoto
            - La libreria rileverà automaticamente la stampante
            """)

# ============================================================================
# GENERATORE QR CODE PER TAVOLI
# ============================================================================
def show_qr_code_generator():
    """Genera QR code per ogni tavolo"""
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
    
    # Raggruppa per sala
    sale = {}
    for t in tavoli:
        if t['sala_nome'] not in sale:
            sale[t['sala_nome']] = []
        sale[t['sala_nome']].append(t)
    
    # URL base (in produzione, mettere URL reale)
    base_url = "http://localhost:8501"
    
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
        
        # Griglia 3 colonne
        cols = st.columns(3)
        
        for i, tavolo in enumerate(tavoli_sala):
            with cols[i % 3]:
                # Genera URL unico
                url = f"{base_url}/?tavolo={tavolo['id']}&mode=cliente"
                
                # Crea QR code
                qr = qrcode.QRCode(
                    version=1,
                    box_size=box_size,
                    border=border
                )
                qr.add_data(url)
                qr.make(fit=True)
                
                img = qr.make_image(fill_color="black", back_color="white")
                
                # Converti per download
                buffered = BytesIO()
                img.save(buffered, format="PNG")
                img_str = base64.b64encode(buffered.getvalue()).decode()
                
                # Mostra
                st.markdown(f"**Tavolo {tavolo['numero']}**")
                st.image(f"data:image/png;base64,{img_str}", width=150)
                
                # Bottone download
                st.download_button(
                    label="📥 Download QR",
                    data=buffered.getvalue(),
                    file_name=f"tavolo_{tavolo['numero']}.png",
                    mime="image/png",
                    key=f"qr_{tavolo['id']}",
                    use_container_width=True
                )
                
                # Mostra URL in un expander
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
            st.caption(n['timestamp_creazione'][:16])
            if st.button("✓ Segna come letta", key=f"read_{n['id']}"):
                NotificaService.segna_letta(n['id'])
                st.rerun()

# ============================================================================
# MAIN
# ============================================================================
def main():
    """Funzione principale"""
    
    # Metodo per leggere i parametri
    params = {}
    for key, value in st.query_params.items():
        if isinstance(value, list):
            params[key] = value[0] if value else None
        else:
            params[key] = value
    
    # Verifica se siamo in modalità cliente
    tavolo_id = params.get('tavolo')
    mode = params.get('mode')
    
    if tavolo_id and mode == 'cliente':
        try:
            from cliente import show_cliente_page
            show_cliente_page()
            return
        except Exception as e:
            st.error(f"❌ Errore nel caricamento della pagina: {e}")
            return
    
    # Se non siamo in modalità cliente, procedi con il login normale
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
        # Se c'è un pre-ordine in revisione, mostra la schermata di revisione
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