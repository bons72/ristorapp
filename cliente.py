"""
PALAZZO FIORINI - Menu Digitale per Clienti
Versione 2.2 - UI Pulita e Professionale
"""

import streamlit as st
import sqlite3
import os
import tempfile
from datetime import datetime
import time
import traceback
import json

# ============================================================================
# CONFIGURAZIONE DATABASE - MODIFICATA PER STREAMLIT CLOUD
# ============================================================================
def get_db_path():
    """Restituisce il percorso del database"""
    # Per Streamlit Cloud
    if os.environ.get('STREAMLIT_CLOUD'):
        return os.path.join(tempfile.gettempdir(), "ristorante.db")
    # Per variabile d'ambiente impostata (da app.py)
    elif os.environ.get('DB_PATH'):
        return os.environ.get('DB_PATH')
    # Per sviluppo locale
    else:
        return "ristorante.db"

DB_PATH = get_db_path()

# ============================================================================
# FUNZIONI PER IL MENU E ORDINI
# ============================================================================

@st.cache_data(ttl=60)
def get_menu_completo():
    """Recupera il menu completo con piatti e relative variazioni"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Query principale per categorie e piatti
        cursor.execute("""
            SELECT 
                c.id as cat_id,
                c.nome as cat_nome,
                c.icona as cat_icona,
                c.attiva as cat_attiva,
                p.id as piatto_id,
                p.nome as piatto_nome,
                p.descrizione_pubblica,
                p.prezzo,
                p.disponibile as piatto_disponibile,
                p.foto_data
            FROM categorie c
            LEFT JOIN piatti p ON c.id = p.categoria_id AND p.disponibile = 1
            WHERE c.attiva = 1
            ORDER BY c.ordine, p.nome
        """)
        
        results = cursor.fetchall()
        
        menu = []
        current_cat = None
        current_cat_data = None
        
        for row in results:
            cat_id = row['cat_id']
            
            if current_cat != cat_id:
                if current_cat_data:
                    menu.append(current_cat_data)
                current_cat = cat_id
                current_cat_data = {
                    'id': cat_id,
                    'nome': row['cat_nome'],
                    'icona': row['cat_icona'] or '🍽️',
                    'piatti': []
                }
            
            if row['piatto_id']:
                # Recupera le variazioni per questo piatto
                variazioni = get_variazioni_per_piatto(row['piatto_id'])
                
                current_cat_data['piatti'].append({
                    'id': row['piatto_id'],
                    'nome': row['piatto_nome'],
                    'descrizione': row['descrizione_pubblica'] or '',
                    'prezzo': row['prezzo'],
                    'foto': row['foto_data'],
                    'variazioni': variazioni
                })
        
        if current_cat_data:
            menu.append(current_cat_data)
        
        conn.close()
        return menu
    except Exception as e:
        print(f"❌ Errore in get_menu_completo: {e}")
        traceback.print_exc()
        return []

def get_variazioni_per_piatto(piatto_id):
    """Recupera le variazioni disponibili per un piatto"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Prima ottieni la categoria del piatto per determinare il reparto
        cursor.execute("""
            SELECT c.reparto_id 
            FROM piatti p
            JOIN categorie c ON p.categoria_id = c.id
            WHERE p.id = ?
        """, (piatto_id,))
        
        reparto = cursor.fetchone()
        if not reparto:
            return []
        
        # Poi ottieni le variazioni del reparto
        cursor.execute("""
            SELECT * FROM variazioni 
            WHERE reparto_id = ? AND attivo = 1
            ORDER BY ordine, nome
        """, (reparto['reparto_id'],))
        
        variazioni = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return variazioni
    except Exception as e:
        print(f"❌ Errore in get_variazioni_per_piatto: {e}")
        return []

def format_currency(amount):
    """Formatta importo in euro"""
    return f"€{amount:.2f}"

def calcola_totale_con_variazioni(prezzo_base, qty, variazioni_selezionate):
    """Calcola il totale includendo le variazioni"""
    totale = prezzo_base * qty
    for var in variazioni_selezionate:
        totale += var['prezzo'] * qty
    return totale

def get_storico_ordini(tavolo_id):
    """Recupera lo storico degli ordini per un tavolo"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT p.*, 
                   COUNT(d.id) as numero_piatti,
                   SUM(d.qty * d.prezzo_unitario) as totale
            FROM preordini p
            LEFT JOIN preordini_dettaglio d ON p.id = d.preordine_id
            WHERE p.tavolo_id = ?
            GROUP BY p.id
            ORDER BY p.timestamp_creazione DESC
            LIMIT 10
        """, (tavolo_id,))
        
        ordini = []
        for row in cursor.fetchall():
            ordine = dict(row)
            # Recupera i dettagli per questo ordine
            cursor.execute("""
                SELECT * FROM preordini_dettaglio 
                WHERE preordine_id = ?
            """, (row['id'],))
            dettagli = [dict(d) for d in cursor.fetchall()]
            
            # Parsing delle variazioni (che sono salvate come JSON)
            for d in dettagli:
                if d.get('variazioni') and d['variazioni'] != '[]':
                    try:
                        d['variazioni_parsed'] = json.loads(d['variazioni'])
                    except:
                        d['variazioni_parsed'] = []
                else:
                    d['variazioni_parsed'] = []
            
            ordine['dettagli'] = dettagli
            ordini.append(ordine)
        
        conn.close()
        return ordini
    except Exception as e:
        print(f"❌ Errore in get_storico_ordini: {e}")
        traceback.print_exc()
        return []

def salva_preordine_con_verifica(tavolo_id, carrello, note=""):
    """Salva pre-ordine con verifica e restituisce l'ID"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)  # USA DB_PATH
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Inserisci preordine
        cursor.execute("""
            INSERT INTO preordini (tavolo_id, stato, note, timestamp_creazione)
            VALUES (?, 'IN_ATTESA', ?, ?)
        """, (tavolo_id, note, timestamp))
        
        preordine_id = cursor.lastrowid
        
        # Inserisci dettagli
        for item in carrello:
            # Prepara JSON per le variazioni
            variazioni_json = json.dumps(item.get('variazioni', []))
            
            cursor.execute("""
                INSERT INTO preordini_dettaglio 
                (preordine_id, piatto_id, piatto_nome, qty, prezzo_unitario, variazioni, note)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                preordine_id,
                item['id'],
                item['nome'],
                item['qty'],
                item['prezzo'],
                variazioni_json,
                item.get('note', '')
            ))
        
        conn.commit()
        return preordine_id
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ ERRORE: {e}")
        traceback.print_exc()
        return None
    finally:
        if conn:
            conn.close()

# ============================================================================
# PAGINA CLIENTE PRINCIPALE
# ============================================================================

def show_cliente_page():
    """Pagina cliente con menu, variazioni e storico"""
    
    # ========================================================================
    # OTTIENI TAVOLO
    # ========================================================================
    tavolo_id = st.query_params.get('tavolo', [None])
    if isinstance(tavolo_id, list):
        tavolo_id = tavolo_id[0] if tavolo_id else None
    
    if not tavolo_id:
        st.error("❌ QR Code non valido")
        st.info("Contatta il personale")
        return
    
    try:
        tavolo_id = int(tavolo_id)
    except:
        st.error("❌ Tavolo non valido")
        return
    
    # ========================================================================
    # HEADER CON STILE PROFESSIONALE
    # ========================================================================
    st.markdown(f"""
        <style>
            .header {{
                background: linear-gradient(135deg, #d35400 0%, #e67e22 100%);
                padding: 1.5rem;
                border-radius: 0 0 20px 20px;
                margin-bottom: 2rem;
                text-align: center;
                color: white;
                box-shadow: 0 4px 6px rgba(0,0,0,0.1);
            }}
            .header h1 {{
                margin: 0;
                font-size: 2.2rem;
                font-weight: 600;
                letter-spacing: 1px;
            }}
            .header p {{
                margin: 0.5rem 0 0 0;
                font-size: 1.2rem;
                opacity: 0.9;
            }}
            .header .tavolo {{
                background: rgba(255,255,255,0.2);
                display: inline-block;
                padding: 0.3rem 1.5rem;
                border-radius: 50px;
                margin-top: 0.8rem;
                font-weight: 500;
            }}
            .card {{
                border: 1px solid #e0e0e0;
                border-radius: 10px;
                padding: 1rem;
                margin-bottom: 1rem;
                background: white;
                box-shadow: 0 2px 4px rgba(0,0,0,0.05);
            }}
        </style>
        
        <div class="header">
            <h1>🍽️ PALAZZO FIORINI</h1>
            <p>Benvenuti nel nostro ristorante</p>
            <div class="tavolo">Tavolo {tavolo_id}</div>
        </div>
    """, unsafe_allow_html=True)
    
    # ========================================================================
    # TABS: NUOVO ORDINE | STORICO
    # ========================================================================
    tab_nuovo, tab_storico = st.tabs(["📝 Nuovo Ordine", "📜 Storico Ordini"])
    
    # ========================================================================
    # TAB 1: NUOVO ORDINE
    # ========================================================================
    with tab_nuovo:
        # Inizializza carrello
        if 'cliente_carrello' not in st.session_state:
            st.session_state.cliente_carrello = []
        if 'cliente_nota' not in st.session_state:
            st.session_state.cliente_nota = ""
        
        # Layout a due colonne
        col_menu, col_carrello = st.columns([2, 1])
        
        with col_menu:
            menu = get_menu_completo()
            
            if not menu:
                st.warning("Menu non disponibile")
                return
            
            # Tabs per categorie
            categorie = [cat['nome'] for cat in menu]
            icone = [cat['icona'] for cat in menu]
            tabs = st.tabs([f"{icona} {nome}" for icona, nome in zip(icone, categorie)])
            
            for idx, (tab, categoria) in enumerate(zip(tabs, menu)):
                with tab:
                    if not categoria['piatti']:
                        st.info("Nessun piatto disponibile in questa categoria")
                        continue
                    
                    for piatto in categoria['piatti']:
                        with st.container():
                            col_img, col_info, col_prezzo = st.columns([1, 3, 1])
                            
                            with col_img:
                                if piatto.get('foto'):
                                    try:
                                        st.image(piatto['foto'], width=60)
                                    except:
                                        st.markdown(f"<h2>{categoria['icona']}</h2>", unsafe_allow_html=True)
                                else:
                                    st.markdown(f"<h2>{categoria['icona']}</h2>", unsafe_allow_html=True)
                            
                            with col_info:
                                st.markdown(f"**{piatto['nome']}**")
                                if piatto['descrizione']:
                                    st.caption(piatto['descrizione'][:80] + ("..." if len(piatto['descrizione']) > 80 else ""))
                            
                            with col_prezzo:
                                st.markdown(f"**{format_currency(piatto['prezzo'])}**")
                            
                            # Variazioni (se disponibili)
                            variazioni_selezionate = []
                            if piatto.get('variazioni') and len(piatto['variazioni']) > 0:
                                with st.expander("✨ Personalizza", expanded=False):
                                    cols = st.columns(2)
                                    for i, var in enumerate(piatto['variazioni']):
                                        with cols[i % 2]:
                                            if st.checkbox(
                                                f"{var['nome']} (+{format_currency(var['prezzo'])})",
                                                key=f"var_{piatto['id']}_{var['id']}_{idx}"
                                            ):
                                                variazioni_selezionate.append(var)
                            
                            # Quantità e bottone aggiungi
                            col_qty, col_btn = st.columns([1, 2])
                            with col_qty:
                                qty = st.number_input(
                                    "Qtà",
                                    min_value=0,
                                    max_value=10,
                                    value=0,
                                    key=f"qty_{piatto['id']}_{idx}",
                                    label_visibility="collapsed"
                                )
                            
                            with col_btn:
                                if st.button("➕ Aggiungi", key=f"add_{piatto['id']}_{idx}", use_container_width=True):
                                    if qty > 0:
                                        # Calcola prezzo con variazioni
                                        prezzo_totale = piatto['prezzo']
                                        for v in variazioni_selezionate:
                                            prezzo_totale += v['prezzo']
                                        
                                        st.session_state.cliente_carrello.append({
                                            'id': piatto['id'],
                                            'nome': piatto['nome'],
                                            'prezzo_base': piatto['prezzo'],
                                            'prezzo': prezzo_totale,
                                            'qty': qty,
                                            'variazioni': variazioni_selezionate,
                                            'note': ''
                                        })
                                        st.success(f"✅ {qty}x {piatto['nome']} aggiunto!")
                                        st.rerun()
                                    else:
                                        st.warning("Seleziona una quantità")
                            
                            st.markdown("---")
        
        with col_carrello:
            st.markdown("### 🛒 Il tuo ordine")
            
            if not st.session_state.cliente_carrello:
                st.info("👆 Seleziona i piatti per iniziare")
            else:
                # Raggruppa piatti uguali (considerando anche variazioni)
                riassunto = {}
                for item in st.session_state.cliente_carrello:
                    # Crea una chiave unica che includa ID e variazioni
                    var_key = "_".join([str(v['id']) for v in item.get('variazioni', [])]) or "base"
                    key = f"{item['id']}_{var_key}"
                    
                    if key not in riassunto:
                        riassunto[key] = item.copy()
                    else:
                        riassunto[key]['qty'] += item['qty']
                
                totale = 0
                for key, item in riassunto.items():
                    with st.container(border=True):
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            st.markdown(f"**{item['nome']}**")
                            st.caption(f"x{item['qty']}")
                            if item.get('variazioni'):
                                for v in item['variazioni']:
                                    st.caption(f"  ✦ {v['nome']} (+{format_currency(v['prezzo'])})")
                        
                        with col2:
                            importo = calcola_totale_con_variazioni(
                                item['prezzo_base'], 
                                item['qty'], 
                                item.get('variazioni', [])
                            )
                            st.markdown(f"**{format_currency(importo)}**")
                            totale += importo
                        
                        with col3:
                            if st.button("🗑️", key=f"del_{key}"):
                                # Rimuove tutti gli item con quella chiave
                                nuovi = []
                                for i in st.session_state.cliente_carrello:
                                    var_key_i = "_".join([str(v['id']) for v in i.get('variazioni', [])]) or "base"
                                    key_i = f"{i['id']}_{var_key_i}"
                                    if key_i != key:
                                        nuovi.append(i)
                                st.session_state.cliente_carrello = nuovi
                                st.rerun()
                
                st.markdown(f"### Totale: {format_currency(totale)}")
                
                with st.expander("📝 Note aggiuntive", expanded=False):
                    note = st.text_area(
                        "Allergie, preferenze...",
                        value=st.session_state.cliente_nota,
                        key="note_input",
                        placeholder="Es. Senza glutine, ben cotto..."
                    )
                    st.session_state.cliente_nota = note
                
                if st.button("📨 INVIA ORDINE", type="primary", use_container_width=True):
                    if st.session_state.cliente_carrello:
                        with st.spinner("Invio in corso..."):
                            preordine_id = salva_preordine_con_verifica(
                                tavolo_id,
                                st.session_state.cliente_carrello,
                                st.session_state.cliente_nota
                            )
                            
                            if preordine_id:
                                st.success(f"✅ Ordine #{preordine_id} inviato con successo!")
                                st.balloons()
                                st.session_state.cliente_carrello = []
                                st.session_state.cliente_nota = ""
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("❌ Errore nell'invio. Riprova o contatta il personale.")
                    else:
                        st.warning("Il carrello è vuoto")
    
    # ========================================================================
    # TAB 2: STORICO ORDINI
    # ========================================================================
    with tab_storico:
        st.markdown("### 📜 I tuoi ordini")
        
        ordini = get_storico_ordini(tavolo_id)
        
        if not ordini:
            st.info("Non hai ancora effettuato ordini")
        else:
            for ordine in ordini:
                # Formatta data
                if ordine['timestamp_creazione']:
                    if hasattr(ordine['timestamp_creazione'], 'strftime'):
                        data_ora = ordine['timestamp_creazione'].strftime('%d/%m/%Y %H:%M')
                    else:
                        data_ora = str(ordine['timestamp_creazione'])[:16]
                else:
                    data_ora = 'N/A'
                
                stato_emoji = {
                    'IN_ATTESA': '⏳',
                    'REVISIONATO': '👀',
                    'CONFERMATO': '✅',
                    'ANNULLATO': '❌'
                }.get(ordine['stato'], '📋')
                
                with st.expander(f"{stato_emoji} Ordine del {data_ora}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Stato:** {ordine['stato']}")
                        st.write(f"**Piatti:** {ordine['numero_piatti']}")
                    
                    with col2:
                        st.write(f"**Totale:** {format_currency(ordine['totale'])}")
                    
                    st.markdown("##### Dettaglio:")
                    for d in ordine['dettagli']:
                        prezzo_totale = d['qty'] * d['prezzo_unitario']
                        st.markdown(f"• {d['qty']}x **{d['piatto_nome']}** - {format_currency(prezzo_totale)}")
                        
                        # Mostra variazioni se presenti
                        if d.get('variazioni_parsed'):
                            for v in d['variazioni_parsed']:
                                st.caption(f"  ✦ {v.get('nome', '')} (+{format_currency(v.get('prezzo', 0))})")
                        
                        if d.get('note'):
                            st.caption(f"  📝 {d['note']}")
                    
                    if ordine.get('note'):
                        st.info(f"📝 Note: {ordine['note']}")