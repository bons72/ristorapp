"""
PALAZZO FIORINI - Menu Digitale per Clienti (SOLO PROMEMORIA)
Versione 4.0 - Visualizzazione menu con carrello locale e immagini
"""

import streamlit as st
import sqlite3
import os
import tempfile
from datetime import datetime
import json
import base64
from io import BytesIO

# ============================================================================
# CONFIGURAZIONE DATABASE
# ============================================================================
def get_db_path():
    """Restituisce il percorso del database"""
    if os.environ.get('STREAMLIT_CLOUD'):
        return os.path.join(tempfile.gettempdir(), "ristorante.db")
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
        cursor.execute("SELECT * FROM brand WHERE id = 1")
        brand = cursor.fetchone()
        conn.close()
        return dict(brand) if brand else {'nome': 'RISTORAPP', 'logo_data': None}
    except:
        return {'nome': 'RISTORAPP', 'logo_data': None}

# ============================================================================
# FUNZIONI PER IL MENU
# ============================================================================
@st.cache_data(ttl=60)
def get_menu_completo():
    """Recupera il menu completo con piatti e immagini"""
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
        conn.close()
        
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
                # Converti foto_data in base64 se presente
                foto_data = row['foto_data']
                foto_base64 = None
                if foto_data:
                    try:
                        foto_base64 = base64.b64encode(foto_data).decode()
                    except:
                        foto_base64 = None
                
                current_cat_data['piatti'].append({
                    'id': row['piatto_id'],
                    'nome': row['piatto_nome'],
                    'descrizione': row['descrizione_pubblica'] or '',
                    'prezzo': row['prezzo'],
                    'foto_base64': foto_base64
                })
        
        if current_cat_data:
            menu.append(current_cat_data)
        
        return menu
    except Exception as e:
        print(f"❌ Errore menu: {e}")
        return []

def format_currency(amount):
    """Formatta importo in euro"""
    return f"€ {amount:.2f}"

# ============================================================================
# PAGINA CLIENTE PRINCIPALE
# ============================================================================
def show_cliente_page():
    """Pagina cliente con menu digitale, immagini e carrello promemoria"""
    
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
    ristorante_nome = brand.get('nome', 'RISTORAPP')
    logo_data = brand.get('logo_data')
    
    # ========================================================================
    # CSS PERSONALIZZATO CON CARATTERI GRANDI
    # ========================================================================
    st.markdown("""
        <style>
            /* Font base più grande */
            html, body, [class*="css"]  {
                font-size: 18px !important;
            }
            
            /* Header compatto ma leggibile */
            .compact-header {
                background: linear-gradient(135deg, #d35400 0%, #e67e22 100%);
                padding: 1.2rem 1.5rem;
                border-radius: 0 0 20px 20px;
                margin-bottom: 2rem;
                display: flex;
                align-items: center;
                justify-content: space-between;
                color: white;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }
            .header-logo {
                display: flex;
                align-items: center;
                gap: 15px;
            }
            .header-logo img {
                height: 60px;
                width: auto;
                border-radius: 8px;
            }
            .header-logo h2 {
                margin: 0;
                font-size: 2.2rem !important;
                font-weight: 700;
                color: white;
            }
            .header-tavolo {
                background: rgba(255,255,255,0.25);
                padding: 0.6rem 2rem;
                border-radius: 50px;
                font-size: 1.8rem !important;
                font-weight: 600;
                border: 2px solid rgba(255,255,255,0.5);
            }
            
            /* Tabs più grandi */
            .stTabs [data-baseweb="tab-list"] {
                gap: 2rem;
                margin-bottom: 2rem;
            }
            .stTabs [data-baseweb="tab"] {
                font-size: 1.5rem !important;
                font-weight: 600 !important;
                padding: 0.8rem 1.5rem !important;
                background-color: #f8f9fa;
                border-radius: 50px !important;
                margin-right: 1rem;
            }
            .stTabs [aria-selected="true"] {
                background-color: #d35400 !important;
                color: white !important;
            }
            
            /* Card piatti - formato grande */
            .piatto-card {
                border: 2px solid #e0e0e0;
                border-radius: 20px;
                padding: 1.5rem;
                margin-bottom: 1.8rem;
                background: white;
                box-shadow: 0 4px 12px rgba(0,0,0,0.08);
                transition: transform 0.2s;
            }
            .piatto-card:hover {
                transform: scale(1.02);
                box-shadow: 0 6px 16px rgba(0,0,0,0.15);
            }
            .piatto-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1rem;
            }
            .piatto-nome {
                font-size: 1.8rem !important;
                font-weight: 700;
                color: #2c3e50;
            }
            .piatto-prezzo {
                font-size: 2rem !important;
                font-weight: 800;
                color: #d35400;
                background: #fff3e0;
                padding: 0.3rem 1rem;
                border-radius: 50px;
            }
            .piatto-descrizione {
                font-size: 1.2rem !important;
                color: #555;
                margin-bottom: 1.2rem;
                line-height: 1.5;
            }
            .piatto-immagine {
                margin: 1rem 0;
                text-align: center;
            }
            .piatto-immagine img {
                max-width: 100%;
                max-height: 250px;
                border-radius: 15px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            }
            
            /* Pulsanti più grandi */
            .stButton > button {
                font-size: 1.4rem !important;
                font-weight: 600 !important;
                padding: 0.8rem 1.5rem !important;
                border-radius: 50px !important;
                background-color: #d35400 !important;
                color: white !important;
                border: none !important;
            }
            .stButton > button:hover {
                background-color: #e67e22 !important;
            }
            
            /* Quantità input più grande */
            .stNumberInput input {
                font-size: 1.4rem !important;
                padding: 0.8rem !important;
                border-radius: 50px !important;
                border: 2px solid #ddd !important;
            }
            
            /* Carrello promemoria */
            .promemoria-container {
                background-color: #f8f9fa;
                padding: 1.5rem;
                border-radius: 20px;
                border-left: 8px solid #d35400;
                margin-top: 2rem;
            }
            .promemoria-title {
                font-size: 2rem !important;
                font-weight: 700;
                color: #2c3e50;
                margin-bottom: 1.5rem;
            }
            .promemoria-item {
                font-size: 1.3rem !important;
                padding: 1rem;
                background: white;
                border-radius: 15px;
                margin-bottom: 1rem;
                border-left: 5px solid #d35400;
                box-shadow: 0 2px 8px rgba(0,0,0,0.05);
            }
            .promemoria-totale {
                font-size: 1.8rem !important;
                font-weight: 700;
                color: #d35400;
                text-align: right;
                margin-top: 1.5rem;
                padding-top: 1rem;
                border-top: 3px dashed #d35400;
            }
            
            /* Messaggi di avviso */
            .stAlert {
                font-size: 1.3rem !important;
                padding: 1rem !important;
                border-radius: 15px !important;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # ========================================================================
    # HEADER CON LOGO E TAVOLO
    # ========================================================================
    header_html = '<div class="compact-header"><div class="header-logo">'
    
    if logo_data:
        try:
            encoded = base64.b64encode(logo_data).decode()
            header_html += f'<img src="data:image/png;base64,{encoded}" alt="Logo">'
        except:
            pass
    
    header_html += f'<h2>{ristorante_nome}</h2></div>'
    header_html += f'<div class="header-tavolo">Tavolo {tavolo_id}</div></div>'
    
    st.markdown(header_html, unsafe_allow_html=True)
    
    # ========================================================================
    # MESSAGGIO INFORMATIVO
    # ========================================================================
    st.info("""
        📋 **MENU DIGITALE** - Usa questa pagina come promemoria per il tuo ordine.
        Seleziona i piatti che desideri e mostra la lista al cameriere.
    """)
    
    # ========================================================================
    # INIZIALIZZA CARRELLO PROMEMORIA
    # ========================================================================
    if 'promemoria' not in st.session_state:
        st.session_state.promemoria = []
    
    # ========================================================================
    # CARICA MENU
    # ========================================================================
    menu = get_menu_completo()
    
    if not menu:
        st.error("❌ Menu non disponibile al momento. Riprova più tardi.")
        return
    
    # ========================================================================
    # LAYOUT PRINCIPALE
    # ========================================================================
    col_menu, col_promemoria = st.columns([2, 1])
    
    with col_menu:
        # Crea tabs per le categorie
        categorie = [cat['nome'] for cat in menu]
        icone = [cat['icona'] for cat in menu]
        
        tabs = st.tabs([f"{icona} {nome}" for icona, nome in zip(icone, categorie)])
        
        for idx, (tab, categoria) in enumerate(zip(tabs, menu)):
            with tab:
                if not categoria['piatti']:
                    st.info("Nessun piatto disponibile in questa categoria")
                    continue
                
                for piatto in categoria['piatti']:
                    # Card piatto
                    st.markdown(f"""
                        <div class="piatto-card">
                            <div class="piatto-header">
                                <span class="piatto-nome">{piatto['nome']}</span>
                                <span class="piatto-prezzo">{format_currency(piatto['prezzo'])}</span>
                            </div>
                            <div class="piatto-descrizione">{piatto['descrizione']}</div>
                        </div>
                    """, unsafe_allow_html=True)
                    
                    # Immagine del piatto (se disponibile)
                    if piatto.get('foto_base64'):
                        st.markdown(f"""
                            <div class="piatto-immagine">
                                <img src="data:image/png;base64,{piatto['foto_base64']}" alt="{piatto['nome']}">
                            </div>
                        """, unsafe_allow_html=True)
                    
                    # Quantità e pulsante aggiungi
                    col_qty, col_btn = st.columns([1, 2])
                    with col_qty:
                        qty = st.number_input(
                            "Qtà",
                            min_value=0,
                            max_value=10,
                            value=0,
                            step=1,
                            key=f"qty_{piatto['id']}_{idx}",
                            label_visibility="collapsed"
                        )
                    
                    with col_btn:
                        if st.button("➕ AGGIUNGI AL PROMEMORIA", key=f"add_{piatto['id']}_{idx}", use_container_width=True):
                            if qty > 0:
                                # Aggiungi al promemoria
                                nuovo_item = {
                                    'id': piatto['id'],
                                    'nome': piatto['nome'],
                                    'prezzo': piatto['prezzo'],
                                    'qty': qty,
                                    'note': ''
                                }
                                st.session_state.promemoria.append(nuovo_item)
                                st.success(f"✅ {qty}x {piatto['nome']} aggiunto al promemoria!")
                                st.rerun()
                            else:
                                st.warning("Seleziona una quantità maggiore di 0")
    
    with col_promemoria:
        st.markdown('<div class="promemoria-title">📋 IL MIO PROMEMORIA</div>', unsafe_allow_html=True)
        
        if not st.session_state.promemoria:
            st.info("👆 Tocca i piatti per aggiungerli al promemoria")
        else:
            # Raggruppa piatti
            riassunto = {}
            for item in st.session_state.promemoria:
                key = f"{item['id']}"
                if key not in riassunto:
                    riassunto[key] = item.copy()
                else:
                    riassunto[key]['qty'] += item['qty']
            
            totale = 0
            for key, item in riassunto.items():
                st.markdown(f"""
                    <div class="promemoria-item">
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                            <div>
                                <strong style="font-size: 1.5rem;">{item['qty']}x {item['nome']}</strong>
                            </div>
                            <div style="font-size: 1.4rem; font-weight: 600; color: #d35400;">
                                {format_currency(item['prezzo'] * item['qty'])}
                            </div>
                        </div>
                    </div>
                """, unsafe_allow_html=True)
                
                # Bottone elimina (più piccolo)
                col1, col2, col3 = st.columns([3, 1, 1])
                with col3:
                    if st.button("🗑️", key=f"del_{key}"):
                        nuovi = []
                        for i in st.session_state.promemoria:
                            if str(i['id']) != key:
                                nuovi.append(i)
                        st.session_state.promemoria = nuovi
                        st.rerun()
                
                totale += item['prezzo'] * item['qty']
            
            st.markdown(f'<div class="promemoria-totale">TOTALE: {format_currency(totale)}</div>', unsafe_allow_html=True)
            
            # Note opzionali
            with st.expander("📝 Aggiungi note (opzionale)"):
                note = st.text_area(
                    "Allergie, preferenze...",
                    placeholder="Es. Senza glutine, ben cotto...",
                    height=100
                )
                if note:
                    st.caption(f"📌 Nota salvata: {note}")
            
            # Pulsanti azione
            col_svuota, col_cameriere = st.columns(2)
            
            with col_svuota:
                if st.button("🗑️ SVUOTA", use_container_width=True):
                    st.session_state.promemoria = []
                    st.rerun()
            
            with col_cameriere:
                if st.button("👨‍🍳 CHIAMA CAMERIERE", type="primary", use_container_width=True):
                    st.balloons()
                    st.success("""
                        ✅ Il cameriere è stato chiamato!
                        
                        Mostragli il promemoria con la lista dei piatti.
                    """)
    
    # ========================================================================
    # ISTRUZIONI FINALI
    # ========================================================================
    st.markdown("---")
    st.markdown("""
        <div style="text-align: center; padding: 1rem; background: #f8f9fa; border-radius: 15px;">
            <p style="font-size: 1.3rem; margin: 0;">
                📌 Mostra questa lista al cameriere per comunicare il tuo ordine
            </p>
        </div>
    """, unsafe_allow_html=True)