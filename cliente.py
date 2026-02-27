"""
Modulo Cliente - Menu Digitale con Login Sociale
Versione 2.0 - Integrazione OAuth
"""

import streamlit as st
import sqlite3
import json
from datetime import datetime
import time
from oauth_handler import OAuthHandler

# ============================================================================
# FUNZIONI PER IL CLIENTE
# ============================================================================

def get_menu_completo():
    """Recupera il menu completo con foto e descrizioni"""
    conn = sqlite3.connect('ristorante.db')
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
            p.foto_data,
            p.tempo_preparazione
        FROM categorie c
        LEFT JOIN piatti p ON c.id = p.categoria_id AND p.disponibile = 1
        WHERE c.attiva = 1
        ORDER BY c.ordine, p.nome
    """)
    
    menu = {}
    rows = cursor.fetchall()
    
    for row in rows:
        cat_id = row['cat_id']
        if cat_id not in menu:
            menu[cat_id] = {
                'nome': row['cat_nome'],
                'icona': row['cat_icona'],
                'piatti': []
            }
        if row['piatto_id']:
            menu[cat_id]['piatti'].append({
                'id': row['piatto_id'],
                'nome': row['piatto_nome'],
                'descrizione': row['descrizione_pubblica'] or " ",
                'prezzo': row['prezzo'],
                'foto': row['foto_data'],
                'tempo': row['tempo_preparazione']
            })
    
    conn.close()
    return menu

def salva_preordine(tavolo_id, carrello, cliente_info, note=""):
    """Salva un pre-ordine con info cliente"""
    conn = None
    try:
        conn = sqlite3.connect('ristorante.db')
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # Crea preordine con info cliente
        cursor.execute("""
            INSERT INTO preordini (
                tavolo_id, stato, note, timestamp_creazione,
                cliente_nome, cliente_email, cliente_provider
            )
            VALUES (?, 'IN_ATTESA', ?, ?, ?, ?, ?)
        """, (
            tavolo_id, 
            note, 
            timestamp,
            cliente_info.get('name', 'Cliente'),
            cliente_info.get('email', ''),
            cliente_info.get('provider', '')
        ))
        
        preordine_id = cursor.lastrowid
        
        # Salva dettagli
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
        
        # Notifica camerieri
        try:
            cursor.execute("SELECT numero FROM tavoli WHERE id = ?", (tavolo_id,))
            tavolo_row = cursor.fetchone()
            tavolo_display = tavolo_row[0] if tavolo_row else tavolo_id
            
            cursor.execute("""
                INSERT INTO notifiche (tipo, titolo, messaggio, destinatario_ruolo, letto, timestamp_creazione)
                VALUES (?, ?, ?, ?, 0, ?)
            """, (
                'PREORDINE',
                f"📱 Nuovo ordine da {cliente_info.get('name', 'Cliente')} - Tavolo {tavolo_display}",
                f"{len(carrello)} piatti - Totale: {format_currency(sum(i['prezzo'] * i['qty'] for i in carrello))}",
                'CAMERIERE',
                timestamp
            ))
            conn.commit()
        except Exception as e:
            print(f"⚠️ Errore notifica: {e}")
        
        return preordine_id
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Errore salvataggio preordine: {e}")
        return None
    finally:
        if conn:
            conn.close()

def format_currency(amount):
    """Formatta importo in euro"""
    return f"€ {amount:.2f}"

# ============================================================================
# PAGINA LOGIN CLIENTE
# ============================================================================

def show_login_page(tavolo_id, tavolo_numero):
    """Mostra pagina di login sociale"""
    
    st.markdown(f"""
        <div style='text-align: center; padding: 2rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px; margin-bottom: 2rem;'>
            <h1>🍽️ Benvenuto al Tavolo {tavolo_numero}</h1>
            <p style='font-size: 1.2rem;'>Accedi in 1 secondo per iniziare il tuo ordine</p>
        </div>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 🔐 Accedi con")
        
        # Inizializza handler OAuth
        oauth = OAuthHandler()
        
        # Pulsanti login sociale
        col_google, col_apple, col_facebook = st.columns(3)
        
        with col_google:
            google_url = oauth.get_google_auth_url()
            if google_url and not oauth.demo_mode:
                st.markdown(f"""
                    <a href="{google_url}" target="_self">
                        <button style="width:100%; padding:12px; background:#fff; border:1px solid #ddd; border-radius:5px; cursor:pointer; font-size:16px;">
                            <img src="https://www.google.com/favicon.ico" width="20" style="vertical-align:middle;"> Google
                        </button>
                    </a>
                """, unsafe_allow_html=True)
            else:
                if st.button("🟦 Google", key="google_demo", use_container_width=True):
                    with st.spinner("Accesso in corso..."):
                        time.sleep(1)
                        user_info = oauth._demo_login('google')
                        oauth.save_user_session(user_info, tavolo_id)
                        st.rerun()
        
        with col_apple:
            apple_url = oauth.get_apple_auth_url()
            if apple_url and not oauth.demo_mode:
                st.markdown(f"""
                    <a href="{apple_url}" target="_self">
                        <button style="width:100%; padding:12px; background:#000; color:white; border:none; border-radius:5px; cursor:pointer; font-size:16px;">
                            🍎 Apple
                        </button>
                    </a>
                """, unsafe_allow_html=True)
            else:
                if st.button("🍎 Apple", key="apple_demo", use_container_width=True):
                    with st.spinner("Accesso in corso..."):
                        time.sleep(1)
                        user_info = oauth._demo_login('apple')
                        oauth.save_user_session(user_info, tavolo_id)
                        st.rerun()
        
        with col_facebook:
            fb_url = oauth.get_facebook_auth_url()
            if fb_url and not oauth.demo_mode:
                st.markdown(f"""
                    <a href="{fb_url}" target="_self">
                        <button style="width:100%; padding:12px; background:#1877f2; color:white; border:none; border-radius:5px; cursor:pointer; font-size:16px;">
                            📘 Facebook
                        </button>
                    </a>
                """, unsafe_allow_html=True)
            else:
                if st.button("📘 Facebook", key="fb_demo", use_container_width=True):
                    with st.spinner("Accesso in corso..."):
                        time.sleep(1)
                        user_info = oauth._demo_login('facebook')
                        oauth.save_user_session(user_info, tavolo_id)
                        st.rerun()
        
        st.divider()
        
        # Modalità ospite
        st.markdown("##### 👤 Preferisci non registrarti?")
        if st.button("Continua come ospite", use_container_width=True):
            with st.spinner("Accesso in corso..."):
                time.sleep(1)
                st.session_state.cliente_logged_in = True
                st.session_state.cliente_info = {
                    'provider': 'guest',
                    'id': f"guest_{tavolo_id}_{int(time.time())}",
                    'name': 'Ospite',
                    'email': ''
                }
                st.session_state.cliente_login_time = datetime.now()
                st.session_state.cliente_tavolo = tavolo_id
                st.rerun()
        
        st.divider()
        
        # Info privacy
        st.caption("🔒 I tuoi dati sono al sicuro. Utilizziamo solo informazioni base per gestire il tuo ordine.")

# ============================================================================
# PAGINA MENU CLIENTE (con login effettuato)
# ============================================================================

def show_menu_page(tavolo_id, tavolo_numero):
    """Mostra il menu dopo il login"""
    
    cliente_info = st.session_state.cliente_info
    
    # Header con profilo
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        st.markdown(f"""
            <div style='padding: 0.5rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px;'>
                <h2>🍽️ Tavolo {tavolo_numero}</h2>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        if cliente_info.get('picture'):
            st.image(cliente_info['picture'], width=40)
        else:
            provider_icon = {
                'google': '🟦',
                'apple': '🍎',
                'facebook': '📘',
                'guest': '👤'
            }.get(cliente_info.get('provider', 'guest'), '👤')
            st.markdown(f"### {provider_icon} {cliente_info.get('name', 'Cliente')}")
    
    with col3:
        if st.button("🚪 Esci", key="logout_cliente"):
            oauth = OAuthHandler()
            oauth.logout()
            st.rerun()
    
    st.divider()
    
    # Inizializza carrello
    if 'cliente_carrello' not in st.session_state:
        st.session_state.cliente_carrello = []
    if 'cliente_nota' not in st.session_state:
        st.session_state.cliente_nota = ""
    
    # Layout menu e carrello
    col_menu, col_carrello = st.columns([2, 1])
    
    with col_menu:
        st.markdown("### 📖 Il Nostro Menu")
        menu = get_menu_completo()
        
        if not menu:
            st.warning("Menu non disponibile")
            return
        
        # Tabs per categorie
        categorie = list(menu.keys())
        if len(categorie) > 1:
            tabs = st.tabs([menu[cat]['nome'] for cat in categorie])
            for idx, (tab, cat_id) in enumerate(zip(tabs, categorie)):
                with tab:
                    mostra_piatti_categoria(menu[cat_id])
        else:
            # Una sola categoria
            for cat_id in categorie:
                mostra_piatti_categoria(menu[cat_id])
    
    with col_carrello:
        mostra_carrello(tavolo_id, cliente_info)

def mostra_piatti_categoria(categoria):
    """Mostra i piatti di una categoria"""
    for piatto in categoria['piatti']:
        with st.container(border=True):
            col_img, col_info, col_btn = st.columns([1, 3, 1])
            
            with col_img:
                if piatto.get('foto'):
                    try:
                        st.image(piatto['foto'], width=60)
                    except:
                        st.markdown("🍽️")
                else:
                    st.markdown("🍽️")
            
            with col_info:
                st.markdown(f"**{piatto['nome']}**")
                if piatto.get('descrizione'):
                    st.caption(piatto['descrizione'][:60])
                st.markdown(f"💰 **{format_currency(piatto['prezzo'])}**")
            
            with col_btn:
                # Pulsanti rapidi + e -
                if st.button("➕", key=f"add_{piatto['id']}"):
                    st.session_state.cliente_carrello.append({
                        'id': piatto['id'],
                        'nome': piatto['nome'],
                        'prezzo': piatto['prezzo'],
                        'qty': 1,
                        'variazioni': [],
                        'note': ''
                    })
                    st.rerun()

def mostra_carrello(tavolo_id, cliente_info):
    """Mostra carrello cliente"""
    
    st.markdown("### 🛒 Il Tuo Ordine")
    
    if not st.session_state.cliente_carrello:
        st.info("👆 Tocca ➕ sui piatti per ordinare")
        return
    
    # Raggruppa piatti uguali
    carrello_raggruppato = {}
    for item in st.session_state.cliente_carrello:
        key = f"{item['id']}_{item.get('note', '')}"
        if key not in carrello_raggruppato:
            carrello_raggruppato[key] = item.copy()
        else:
            carrello_raggruppato[key]['qty'] += item['qty']
    
    totale = 0
    for key, item in carrello_raggruppato.items():
        with st.container(border=True):
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.markdown(f"**{item['nome']}**")
                st.caption(f"x{item['qty']}")
            
            with col2:
                importo = item['prezzo'] * item['qty']
                st.markdown(f"**{format_currency(importo)}**")
                totale += importo
            
            with col3:
                if st.button("🗑️", key=f"del_{key}"):
                    # Rimuovi tutti gli item con questo key
                    nuovi = [i for i in st.session_state.cliente_carrello 
                            if f"{i['id']}_{i.get('note', '')}" != key]
                    st.session_state.cliente_carrello = nuovi
                    st.rerun()
    
    st.markdown(f"### Totale: {format_currency(totale)}")
    
    # Note
    note = st.text_area(
        "📝 Note (allergie, preferenze...)",
        key="cliente_nota",
        placeholder="Es. Senza glutine, ben cotto...",
        value=st.session_state.cliente_nota,
        height=80
    )
    st.session_state.cliente_nota = note
    
    # Bottone invio
    if st.button("📨 INVIA ORDINE", type="primary", use_container_width=True):
        if st.session_state.cliente_carrello:
            with st.spinner("Invio ordine in corso..."):
                preordine_id = salva_preordine(
                    tavolo_id,
                    st.session_state.cliente_carrello,
                    cliente_info,
                    st.session_state.cliente_nota
                )
                
                if preordine_id:
                    st.success("✅ Ordine inviato! Il cameriere lo revisionerà a breve.")
                    st.balloons()
                    st.session_state.cliente_carrello = []
                    st.session_state.cliente_nota = ""
                    time.sleep(3)
                    st.rerun()
                else:
                    st.error("❌ Errore nell'invio. Riprova o chiama il cameriere.")

# ============================================================================
# PAGINA PRINCIPALE CLIENTE
# ============================================================================

def show_cliente_page():
    """Pagina cliente con login sociale"""
    
    # Ottieni tavolo ID dai parametri URL
    tavolo_id = st.query_params.get('tavolo', [None])
    if isinstance(tavolo_id, list):
        tavolo_id = tavolo_id[0] if tavolo_id else None
    
    if not tavolo_id:
        st.error("❌ QR Code non valido")
        st.info("Contatta il personale di sala")
        return
    
    try:
        tavolo_id = int(tavolo_id)
    except ValueError:
        st.error("❌ Tavolo non valido")
        return
    
    # Recupera info tavolo
    conn = sqlite3.connect('ristorante.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT numero FROM tavoli WHERE id = ?", (tavolo_id,))
    tavolo_info = cursor.fetchone()
    conn.close()
    
    if not tavolo_info:
        st.error("❌ Tavolo non trovato")
        return
    
    tavolo_numero = tavolo_info['numero']
    
    # Gestione callback OAuth
    query_params = st.query_params
    if 'code' in query_params and 'state' in query_params:
        # Callback OAuth
        oauth = OAuthHandler()
        provider = st.session_state.get('oauth_provider', 'google')
        user_info = oauth.handle_callback(
            query_params['code'],
            query_params['state'],
            provider
        )
        if user_info:
            oauth.save_user_session(user_info, tavolo_id)
            # Pulisci URL
            st.query_params.clear()
            st.rerun()
    
    # Verifica validità sessione
    oauth = OAuthHandler()
    if not oauth.is_session_valid():
        if st.session_state.get('cliente_logged_in'):
            oauth.logout()
    
    # Routing in base al login
    if not st.session_state.get('cliente_logged_in', False):
        show_login_page(tavolo_id, tavolo_numero)
    else:
        show_menu_page(tavolo_id, tavolo_numero)