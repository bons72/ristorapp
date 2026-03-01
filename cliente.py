"""
PALAZZO FIORINI - Menu Digitale per Clienti
Versione 3.0 - UI Migliorata e Brandizzata
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
# CONFIGURAZIONE DATABASE
# ============================================================================
def get_db_path():
    """Restituisce il percorso del database"""
    if os.environ.get('STREAMLIT_CLOUD'):
        return os.path.join(tempfile.gettempdir(), "ristorante.db")
    elif os.environ.get('DB_PATH'):
        return os.environ.get('DB_PATH')
    else:
        return "ristorante.db"

DB_PATH = get_db_path()

# ============================================================================
# FUNZIONI PER IL BRAND
# ============================================================================
@st.cache_data(ttl=3600)
def get_brand_info():
    """Recupera le informazioni del brand dal database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Verifica se la tabella brand esiste, altrimenti creala
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
        
        # Inserisci record default se non esiste
        cursor.execute("INSERT OR IGNORE INTO brand (id, nome) VALUES (1, 'PALAZZO FIORINI')")
        conn.commit()
        
        cursor.execute("SELECT * FROM brand WHERE id = 1")
        brand = cursor.fetchone()
        conn.close()
        
        return dict(brand) if brand else {'nome': 'PALAZZO FIORINI', 'logo_data': None}
    except Exception as e:
        print(f"Errore get_brand_info: {e}")
        return {'nome': 'PALAZZO FIORINI', 'logo_data': None}

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
        
        cursor.execute("""
            SELECT 
                c.id as cat_id,
                c.nome as cat_nome,
                c.icona as cat_icona,
                p.id as piatto_id,
                p.nome as piatto_nome,
                p.descrizione_pubblica,
                p.prezzo,
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
        
        cursor.execute("""
            SELECT c.reparto_id 
            FROM piatti p
            JOIN categorie c ON p.categoria_id = c.id
            WHERE p.id = ?
        """, (piatto_id,))
        
        reparto = cursor.fetchone()
        if not reparto:
            return []
        
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
            cursor.execute("""
                SELECT * FROM preordini_dettaglio 
                WHERE preordine_id = ?
            """, (row['id'],))
            dettagli = [dict(d) for d in cursor.fetchall()]
            
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
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute("""
            INSERT INTO preordini (tavolo_id, stato, note, timestamp_creazione)
            VALUES (?, 'IN_ATTESA', ?, ?)
        """, (tavolo_id, note, timestamp))
        
        preordine_id = cursor.lastrowid
        
        for item in carrello:
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
# PAGINA CLIENTE PRINCIPALE - VERSIONE MIGLIORATA
# ============================================================================
def show_cliente_page():
    """Pagina cliente con UI migliorata e brandizzazione"""
    
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
    # RECUPERA INFO BRAND
    # ========================================================================
    brand = get_brand_info()
    ristorante_nome = brand.get('nome', 'PALAZZO FIORINI')
    logo_data = brand.get('logo_data')
    
    # ========================================================================
    # CSS PERSONALIZZATO PER UI MIGLIORATA
    # ========================================================================
    st.markdown("""
        <style>
            /* Header compatto */
            .compact-header {
                background: linear-gradient(135deg, #d35400 0%, #e67e22 100%);
                padding: 0.8rem 1rem;
                border-radius: 0 0 15px 15px;
                margin-bottom: 1.5rem;
                display: flex;
                align-items: center;
                justify-content: space-between;
                color: white;
                box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            }
            .header-logo {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .header-logo img {
                height: 40px;
                width: auto;
                border-radius: 5px;
            }
            .header-logo h2 {
                margin: 0;
                font-size: 1.4rem;
                font-weight: 600;
            }
            .header-tavolo {
                background: rgba(255,255,255,0.2);
                padding: 0.3rem 1rem;
                border-radius: 30px;
                font-size: 1rem;
                font-weight: 500;
            }
            
            /* Categorie - Più grandi */
            .category-tab {
                font-size: 1.2rem !important;
                font-weight: 600 !important;
                padding: 0.8rem !important;
            }
            
            /* Card piatti - Più leggibili */
            .piatto-card {
                border: 1px solid #e0e0e0;
                border-radius: 12px;
                padding: 1rem;
                margin-bottom: 1rem;
                background: white;
                box-shadow: 0 2px 6px rgba(0,0,0,0.05);
            }
            .piatto-nome {
                font-size: 1.2rem;
                font-weight: 600;
                margin-bottom: 0.3rem;
            }
            .piatto-descrizione {
                font-size: 0.9rem;
                color: #666;
                margin-bottom: 0.5rem;
            }
            .piatto-prezzo {
                font-size: 1.3rem;
                font-weight: 700;
                color: #d35400;
            }
            
            /* Pulsanti più grandi */
            .stButton > button {
                font-size: 1.1rem !important;
                padding: 0.6rem 1rem !important;
                border-radius: 8px !important;
            }
            
            /* Quantità più leggibile */
            .stNumberInput input {
                font-size: 1.2rem !important;
                padding: 0.6rem !important;
            }
            
            /* Carrello più compatto */
            .carrello-item {
                border-left: 3px solid #d35400;
                padding-left: 0.8rem;
                margin-bottom: 0.8rem;
            }
            .carrello-totale {
                font-size: 1.4rem;
                font-weight: 700;
                color: #d35400;
                text-align: right;
                margin-top: 1rem;
            }
            
            /* Variazioni */
            .variazione-checkbox {
                font-size: 0.95rem !important;
            }
            
            /* Tabs più grandi */
            .stTabs [data-baseweb="tab-list"] {
                gap: 2rem;
            }
            .stTabs [data-baseweb="tab"] {
                font-size: 1.1rem !important;
                padding: 0.5rem 1rem !important;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # ========================================================================
    # HEADER COMPATTO CON LOGO
    # ========================================================================
    header_html = '<div class="compact-header"><div class="header-logo">'
    
    if logo_data:
        import base64
        from io import BytesIO
        encoded = base64.b64encode(logo_data).decode()
        header_html += f'<img src="data:image/png;base64,{encoded}" alt="Logo">'
    
    header_html += f'<h2>{ristorante_nome}</h2></div>'
    header_html += f'<div class="header-tavolo">Tavolo {tavolo_id}</div></div>'
    
    st.markdown(header_html, unsafe_allow_html=True)
    
    # ========================================================================
    # TABS: NUOVO ORDINE | STORICO
    # ========================================================================
    tab_nuovo, tab_storico = st.tabs(["📝 NUOVO ORDINE", "📜 I MIEI ORDINI"])
    
    # ========================================================================
    # TAB 1: NUOVO ORDINE
    # ========================================================================
    with tab_nuovo:
        # Inizializza carrello
        if 'cliente_carrello' not in st.session_state:
            st.session_state.cliente_carrello = []
        if 'cliente_nota' not in st.session_state:
            st.session_state.cliente_nota = ""
        
        # Layout a due colonne (menu 60% - carrello 40%)
        col_menu, col_carrello = st.columns([0.6, 0.4])
        
        with col_menu:
            menu = get_menu_completo()
            
            if not menu:
                st.warning("Menu non disponibile")
                return
            
            # Categorie con icone grandi
            categorie = [cat['nome'] for cat in menu]
            icone = [cat['icona'] for cat in menu]
            
            tabs = st.tabs([f"{icona} {nome}" for icona, nome in zip(icone, categorie)])
            
            for idx, (tab, categoria) in enumerate(zip(tabs, menu)):
                with tab:
                    if not categoria['piatti']:
                        st.info("Nessun piatto disponibile")
                        continue
                    
                    for piatto in categoria['piatti']:
                        with st.container():
                            # Card piatto
                            st.markdown(f"""
                                <div class="piatto-card">
                                    <div style="display: flex; justify-content: space-between; align-items: start;">
                                        <div style="flex: 1;">
                                            <div class="piatto-nome">{piatto['nome']}</div>
                                            <div class="piatto-descrizione">{piatto['descrizione']}</div>
                                        </div>
                                        <div class="piatto-prezzo">{format_currency(piatto['prezzo'])}</div>
                                    </div>
                                </div>
                            """, unsafe_allow_html=True)
                            
                            # Variazioni
                            variazioni_selezionate = []
                            if piatto.get('variazioni') and len(piatto['variazioni']) > 0:
                                with st.expander("✨ Personalizza"):
                                    cols = st.columns(2)
                                    for i, var in enumerate(piatto['variazioni']):
                                        with cols[i % 2]:
                                            if st.checkbox(
                                                f"{var['nome']} (+{format_currency(var['prezzo'])})",
                                                key=f"var_{piatto['id']}_{var['id']}_{idx}",
                                                help=f"Aggiungi {var['nome']} al piatto"
                                            ):
                                                variazioni_selezionate.append(var)
                            
                            # Quantità e pulsante aggiungi
                            col_qty, col_btn = st.columns([1, 2])
                            with col_qty:
                                qty = st.number_input(
                                    "Quantità",
                                    min_value=0,
                                    max_value=10,
                                    value=0,
                                    step=1,
                                    key=f"qty_{piatto['id']}_{idx}",
                                    label_visibility="collapsed"
                                )
                            
                            with col_btn:
                                if st.button("➕ AGGIUNGI", key=f"add_{piatto['id']}_{idx}", use_container_width=True):
                                    if qty > 0:
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
        
        with col_carrello:
            st.markdown("### 🛒 IL TUO ORDINE")
            
            if not st.session_state.cliente_carrello:
                st.info("👆 Tocca i piatti per iniziare")
            else:
                # Raggruppa piatti
                riassunto = {}
                for item in st.session_state.cliente_carrello:
                    var_key = "_".join([str(v['id']) for v in item.get('variazioni', [])]) or "base"
                    key = f"{item['id']}_{var_key}"
                    
                    if key not in riassunto:
                        riassunto[key] = item.copy()
                    else:
                        riassunto[key]['qty'] += item['qty']
                
                totale = 0
                for key, item in riassunto.items():
                    st.markdown(f"""
                        <div class="carrello-item">
                            <div style="display: flex; justify-content: space-between;">
                                <div><strong>{item['qty']}x {item['nome']}</strong></div>
                                <div>{format_currency(item['prezzo'] * item['qty'])}</div>
                            </div>
                    """, unsafe_allow_html=True)
                    
                    if item.get('variazioni'):
                        for v in item['variazioni']:
                            st.markdown(f"<div style='font-size:0.85rem; color:#666; margin-left:1rem;'>✦ {v['nome']} (+{format_currency(v['prezzo'])})</div>", unsafe_allow_html=True)
                    
                    if st.button("🗑️", key=f"del_{key}"):
                        nuovi = []
                        for i in st.session_state.cliente_carrello:
                            var_key_i = "_".join([str(v['id']) for v in i.get('variazioni', [])]) or "base"
                            key_i = f"{i['id']}_{var_key_i}"
                            if key_i != key:
                                nuovi.append(i)
                        st.session_state.cliente_carrello = nuovi
                        st.rerun()
                    
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    importo = calcola_totale_con_variazioni(
                        item['prezzo_base'], 
                        item['qty'], 
                        item.get('variazioni', [])
                    )
                    totale += importo
                
                st.markdown(f"<div class='carrello-totale'>TOTALE: {format_currency(totale)}</div>", unsafe_allow_html=True)
                
                with st.expander("📝 Note"):
                    note = st.text_area(
                        "Allergie, preferenze...",
                        value=st.session_state.cliente_nota,
                        key="note_input",
                        placeholder="Es. Senza glutine, ben cotto...",
                        height=80
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
                                st.success(f"✅ Ordine #{preordine_id} inviato!")
                                st.balloons()
                                st.session_state.cliente_carrello = []
                                st.session_state.cliente_nota = ""
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.error("❌ Errore nell'invio. Riprova.")
                    else:
                        st.warning("Il carrello è vuoto")
    
    # ========================================================================
    # TAB 2: STORICO ORDINI
    # ========================================================================
    with tab_storico:
        st.markdown("### 📜 I TUOI ORDINI")
        
        ordini = get_storico_ordini(tavolo_id)
        
        if not ordini:
            st.info("Non hai ancora effettuato ordini")
        else:
            for ordine in ordini:
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
                        
                        if d.get('variazioni_parsed'):
                            for v in d['variazioni_parsed']:
                                st.caption(f"  ✦ {v.get('nome', '')} (+{format_currency(v.get('prezzo', 0))})")
                        
                        if d.get('note'):
                            st.caption(f"  📝 {d['note']}")
                    
                    if ordine.get('note'):
                        st.info(f"📝 Note: {ordine['note']}")