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
# CREA DIRETTAMENTE LE TABELLE SE NON ESISTONO
# ============================================================================
def crea_tabelle_se_needed():
    """Crea le tabelle necessarie per il cliente"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Crea tabella categorie
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS categorie (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                reparto_id INTEGER NOT NULL,
                icona TEXT DEFAULT '🍽️',
                ordine INTEGER DEFAULT 999,
                attiva INTEGER DEFAULT 1
            )
        """)
        
        # Crea tabella piatti
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS piatti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                categoria_id INTEGER NOT NULL,
                descrizione_pubblica TEXT,
                prezzo REAL NOT NULL,
                disponibile INTEGER DEFAULT 1,
                foto_data BLOB
            )
        """)
        
        # Crea tabella variazioni
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS variazioni (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                prezzo REAL DEFAULT 0,
                reparto_id INTEGER NOT NULL,
                attivo INTEGER DEFAULT 1
            )
        """)
        
        # Crea tabella preordini
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preordini (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tavolo_id INTEGER NOT NULL,
                stato TEXT DEFAULT 'IN_ATTESA',
                note TEXT,
                timestamp_creazione TIMESTAMP
            )
        """)
        
        # Crea tabella preordini_dettaglio
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preordini_dettaglio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                preordine_id INTEGER NOT NULL,
                piatto_id INTEGER NOT NULL,
                piatto_nome TEXT NOT NULL,
                qty INTEGER DEFAULT 1,
                prezzo_unitario REAL NOT NULL,
                variazioni TEXT DEFAULT '[]',
                note TEXT
            )
        """)
        
        # Inserisci dati di esempio se necessario
        cursor.execute("SELECT COUNT(*) FROM categorie")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO categorie (id, nome, reparto_id, icona, ordine) VALUES (1, 'ANTIPASTI', 1, '🥗', 1)")
            cursor.execute("INSERT INTO categorie (id, nome, reparto_id, icona, ordine) VALUES (2, 'PRIMI', 1, '🍝', 2)")
            cursor.execute("INSERT INTO categorie (id, nome, reparto_id, icona, ordine) VALUES (3, 'SECONDI', 1, '🥩', 3)")
        
        cursor.execute("SELECT COUNT(*) FROM piatti")
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO piatti (id, nome, categoria_id, prezzo) VALUES (1, 'Bruschetta', 1, 6.50)")
            cursor.execute("INSERT INTO piatti (id, nome, categoria_id, prezzo) VALUES (2, 'Spaghetti Carbonara', 2, 12.00)")
            cursor.execute("INSERT INTO piatti (id, nome, categoria_id, prezzo) VALUES (3, 'Bistecca alla Griglia', 3, 18.00)")
        
        conn.commit()
        conn.close()
        print("✅ Tabelle create/verificate da cliente.py")
        return True
    except Exception as e:
        print(f"❌ Errore creazione tabelle: {e}")
        return False

# CHIAMA SUBITO LA FUNZIONE
crea_tabelle_se_needed()

# ============================================================================
# ATTENDI CHE IL DATABASE SIA PRONTO
# ============================================================================
def attendi_database():
    """Aspetta che le tabelle necessarie siano create"""
    max_tentativi = 10
    tentativo = 0
    
    while tentativo < max_tentativi:
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='categorie'")
            if cursor.fetchone():
                conn.close()
                print(f"✅ Database pronto al tentativo {tentativo + 1}")
                return True
            conn.close()
        except:
            pass
        
        tentativo += 1
        time.sleep(1)  # Aspetta 1 secondo tra tentativi
    
    print("❌ Database non pronto dopo 10 tentativi")
    return False

# Chiama la funzione all'avvio
attendidb = attendi_database()

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
        
        # Inserisci record default se non esiste (ORA CON RISTORAPP)
        cursor.execute("INSERT OR IGNORE INTO brand (id, nome) VALUES (1, 'RISTORAPP')")
        conn.commit()
        
        cursor.execute("SELECT * FROM brand WHERE id = 1")
        brand = cursor.fetchone()
        conn.close()
        
        return dict(brand) if brand else {'nome': 'RISTORAPP', 'logo_data': None}
    except Exception as e:
        print(f"Errore get_brand_info: {e}")
        return {'nome': 'RISTORAPP', 'logo_data': None}

# ============================================================================
# FUNZIONI PER IL MENU E ORDINI
# ============================================================================
@st.cache_data(ttl=60)
def get_menu_completo():
    """Recupera il menu completo con piatti e relative variazioni"""
    try:
        # Verifica che le tabelle esistano
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='categorie'")
        if not cursor.fetchone():
            print("⚠️ Tabella categorie non ancora pronta")
            conn.close()
            return []
        conn.close()
        
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
        # DEBUG SU FILE
        with open('/tmp/cliente_debug.log', 'a') as f:
            f.write(f"\n[{datetime.now()}] 🚀 FUNZIONE CHIAMATA - Tavolo: {tavolo_id}, Carrello: {len(carrello)} piatti\n")
            f.write(f"   Note: {note}\n")
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # DEBUG
        with open('/tmp/cliente_debug.log', 'a') as f:
            f.write(f"   📝 Inserimento in preordini...\n")
        
        cursor.execute("""
            INSERT INTO preordini (tavolo_id, stato, note, timestamp_creazione)
            VALUES (?, 'IN_ATTESA', ?, ?)
        """, (tavolo_id, note, timestamp))
        
        preordine_id = cursor.lastrowid
        
        with open('/tmp/cliente_debug.log', 'a') as f:
            f.write(f"   ✅ Pre-ordine creato ID: {preordine_id}\n")
        
        for idx, item in enumerate(carrello):
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
            
            with open('/tmp/cliente_debug.log', 'a') as f:
                f.write(f"   ➕ Piatto {idx+1}: {item['qty']}x {item['nome']} (prezzo: {item['prezzo']})\n")
        
        conn.commit()
        
        with open('/tmp/cliente_debug.log', 'a') as f:
            f.write(f"   ✅ COMMIT completato per ordine {preordine_id}\n")
            f.write(f"   🎉 ORDINE SALVATO CON SUCCESSO!\n")
        
        return preordine_id
        
    except Exception as e:
        if conn:
            conn.rollback()
        with open('/tmp/cliente_debug.log', 'a') as f:
            f.write(f"   ❌ ERRORE: {e}\n")
            f.write(f"{traceback.format_exc()}\n")
        print(f"❌ ERRORE: {e}")
        traceback.print_exc()
        return None
    finally:
        if conn:
            conn.close()

# ============================================================================
# NOTIFICHE E STAMPA
# ============================================================================
def invia_notifiche_e_stampe(preordine_id, tavolo_id, carrello, note):
    """Invia notifiche in sala e comande in cucina"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # 1. Crea notifica per i camerieri (ordine ricevuto)
        cursor.execute("""
            INSERT INTO notifiche (tipo, titolo, messaggio, destinatario_ruolo)
            VALUES (?, ?, ?, ?)
        """, (
            'INFO',
            f"📋 Nuovo ordine dal Tavolo {tavolo_id}",
            f"Pre-ordine #{preordine_id} ricevuto - {len(carrello)} piatti da revisionare",
            'CAMERIERE'
        ))
        
        # 2. Raccogli piatti per reparto per le stampe
        piatti_per_reparto = {}
        for item in carrello:
            # Determina reparto del piatto
            piatto_info = cursor.execute("""
                SELECT c.reparto_id 
                FROM piatti p
                JOIN categorie c ON p.categoria_id = c.id
                WHERE p.id = ?
            """, (item['id'],)).fetchone()
            
            if piatto_info:
                reparto_id = piatto_info[0]
                
                if reparto_id not in piatti_per_reparto:
                    piatti_per_reparto[reparto_id] = []
                
                # Prepara note come JSON
                note_json = json.dumps({
                    'note': item.get('note', ''),
                    'variazioni': item.get('variazioni', [])
                })
                
                piatti_per_reparto[reparto_id].append({
                    'piatto_nome': item['nome'],
                    'qty': item['qty'],
                    'note': note_json
                })
        
        conn.close()
        
        # 3. Invia stampe ai reparti (se ci sono stampanti configurate)
        try:
            from db import StampanteService
            for reparto_id, piatti in piatti_per_reparto.items():
                # Crea una comanda temporanea per la stampa
                StampanteService.stampa_comanda(
                    comanda_id=preordine_id,  # Usiamo l'ID preordine come riferimento
                    reparto_id=reparto_id,
                    piatti=piatti
                )
        except Exception as e:
            print(f"⚠️ Errore stampa: {e}")
        
        return True
    except Exception as e:
        print(f"❌ Errore notifiche: {e}")
        return False

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
    ristorante_nome = brand.get('nome', 'RISTORAPP')
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
            .stTabs [data-baseweb="tab"] {
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
            
            /* DEBUG - evidenzia i messaggi di debug */
            .debug-message {
                background-color: #fff3cd;
                border-left: 5px solid #ffc107;
                padding: 10px;
                margin: 10px 0;
                font-family: monospace;
            }
        </style>
    """, unsafe_allow_html=True)
    
    # ========================================================================
    # HEADER COMPATTO CON LOGO
    # ========================================================================
    header_html = '<div class="compact-header"><div class="header-logo">'
    
    if logo_data:
        import base64
        encoded = base64.b64encode(logo_data).decode()
        header_html += f'<img src="data:image/png;base64,{encoded}" alt="Logo">'
    
    header_html += f'<h2>{ristorante_nome}</h2></div>'
    header_html += f'<div class="header-tavolo">Tavolo {tavolo_id}</div></div>'
    
    st.markdown(header_html, unsafe_allow_html=True)
    
    # ========================================================================
    # DEBUG VISIBILE IN ALTO
    # ========================================================================
    with st.expander("🔍 DEBUG INFORMAZIONI", expanded=True):
        st.markdown('<div class="debug-message">', unsafe_allow_html=True)
        st.write(f"📦 **Database path:** {DB_PATH}")
        st.write(f"🪑 **Tavolo ID:** {tavolo_id}")
        st.write(f"🛒 **Carrello in sessione:** {len(st.session_state.get('cliente_carrello', []))} piatti")
        
        # Test connessione database
        try:
            conn_test = sqlite3.connect(DB_PATH)
            cursor_test = conn_test.cursor()
            cursor_test.execute("SELECT COUNT(*) FROM preordini")
            count = cursor_test.fetchone()[0]
            st.write(f"📊 **Record in preordini:** {count}")
            conn_test.close()
            st.success("✅ Connessione database OK")
        except Exception as e:
            st.error(f"❌ Errore database: {e}")
        
        st.markdown('</div>', unsafe_allow_html=True)
    
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
                            
                            # Quantità e pulsante aggiungi con DEBUG
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
                                # DEBUG visibile per questo piatto
                                st.caption(f"🔍 qty={qty}")
                                
                                if st.button("➕ AGGIUNGI", key=f"add_{piatto['id']}_{idx}", use_container_width=True):
                                    st.write(f"✅ **BOTTONE PREMUTO per {piatto['nome']}**")
                                    st.write(f"   Quantità selezionata: {qty}")
                                    st.write(f"   Variazioni selezionate: {len(variazioni_selezionate)}")
                                    
                                    if qty > 0:
                                        prezzo_totale = piatto['prezzo']
                                        for v in variazioni_selezionate:
                                            prezzo_totale += v['prezzo']
                                        
                                        nuovo_item = {
                                            'id': piatto['id'],
                                            'nome': piatto['nome'],
                                            'prezzo_base': piatto['prezzo'],
                                            'prezzo': prezzo_totale,
                                            'qty': qty,
                                            'variazioni': variazioni_selezionate,
                                            'note': ''
                                        }
                                        
                                        st.write(f"   ➕ Nuovo item: {nuovo_item}")
                                        st.write(f"   Carrello prima: {len(st.session_state.cliente_carrello)} elementi")
                                        
                                        st.session_state.cliente_carrello.append(nuovo_item)
                                        
                                        st.write(f"   Carrello dopo: {len(st.session_state.cliente_carrello)} elementi")
                                        st.success(f"✅ {qty}x {piatto['nome']} aggiunto!")
                                        st.rerun()
                                    else:
                                        st.warning("Seleziona una quantità maggiore di 0")
        
        with col_carrello:
            st.markdown("### 🛒 IL TUO ORDINE")
            
            if not st.session_state.cliente_carrello:
                st.info("👆 Tocca i piatti per iniziare")
                st.caption("🔍 DEBUG: carrello vuoto")
            else:
                st.caption(f"🔍 DEBUG: {len(st.session_state.cliente_carrello)} elementi nel carrello")
                
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
                
                # ========================================================================
                # BOTTONE INVIA ORDINE CON DEBUG SU FILE
                # ========================================================================
                st.markdown("---")
                st.markdown("##### 🔍 DEBUG BOTTONE INVIO")
                
                # Scrivi su file all'avvio della pagina (solo per debug)
                with open('/tmp/cliente_click.log', 'a') as f:
                    f.write(f"\n[{datetime.now()}] PAGINA CARICATA - Tavolo: {tavolo_id}, Carrello: {len(st.session_state.cliente_carrello)}\n")
                
                st.write(f"Carrello ha **{len(st.session_state.cliente_carrello)}** elementi")
                
                if st.button("📨 INVIA ORDINE (DEBUG)", type="primary", use_container_width=True):
                    # Scrivi su file quando il bottone viene premuto
                    with open('/tmp/cliente_click.log', 'a') as f:
                        f.write(f"\n[{datetime.now()}] ✅ BOTTONE PREMUTO!\n")
                        f.write(f"   Tavolo: {tavolo_id}\n")
                        f.write(f"   Note: {st.session_state.cliente_nota}\n")
                        f.write(f"   Carrello: {len(st.session_state.cliente_carrello)} piatti\n")
                    
                    st.write("✅ **BOTTONE INVIO PREMUTO!** (controlla /tmp/cliente_click.log)")
                    st.write(f"Tavolo: {tavolo_id}")
                    st.write(f"Note: {st.session_state.cliente_nota}")
                    st.write(f"Carrello: {len(st.session_state.cliente_carrello)} piatti")
                    
                    if st.session_state.cliente_carrello:
                        with st.spinner("Invio in corso... (controlla i log)"):
                            # Mostra i primi 2 piatti per debug
                            st.write("**Primi 2 piatti del carrello:**")
                            for i, item in enumerate(st.session_state.cliente_carrello[:2]):
                                st.write(f"  {i+1}. {item['qty']}x {item['nome']} - €{item['prezzo']}")
                            
                            # 1. Salva il pre-ordine nel database
                            preordine_id = salva_preordine_con_verifica(
                                tavolo_id,
                                st.session_state.cliente_carrello,
                                st.session_state.cliente_nota
                            )
                            
                            if preordine_id:
                                st.success(f"✅ **SUCCESSO!** Ordine #{preordine_id} salvato!")
                                
                                # 2. Invia notifiche in sala e stampe in cucina
                                with st.spinner("Invio notifiche e stampe in corso..."):
                                    if invia_notifiche_e_stampe(
                                        preordine_id,
                                        tavolo_id,
                                        st.session_state.cliente_carrello,
                                        st.session_state.cliente_nota
                                    ):
                                        st.success("✅ Notifiche inviate in sala e stampe in cucina!")
                                    else:
                                        st.warning("⚠️ Ordine salvato ma problemi con notifiche/stampe")
                                
                                st.balloons()
                                st.session_state.cliente_carrello = []
                                st.session_state.cliente_nota = ""
                                time.sleep(3)
                                st.rerun()
                            else:
                                st.error("❌ **ERRORE** nell'invio. Controlla i log.")
                                st.info("Guarda i log su Streamlit Cloud (Manage app → Logs)")
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