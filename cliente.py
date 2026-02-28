"""
PALAZZO FIORINI - Menu Digitale per Clienti
Versione 2.0 - Ottimizzata per massima velocità
"""

import streamlit as st
import sqlite3
import os
import tempfile
from datetime import datetime
import time
import traceback

# ============================================================================
# CONFIGURAZIONE DATABASE (veloce)
# ============================================================================
def get_db_path():
    """Restituisce il percorso del database"""
    if os.environ.get('STREAMLIT_CLOUD'):
        return os.path.join(tempfile.gettempdir(), "ristorante.db")
    else:
        return "ristorante.db"

DB_PATH = get_db_path()

# ============================================================================
# FUNZIONI PER IL MENU E ORDINI
# ============================================================================

@st.cache_data(ttl=60)
def get_menu_semplificato():
    """Recupera il menu in formato semplice e veloce"""
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
        
        menu = []
        current_cat = None
        current_cat_data = None
        
        for row in cursor.fetchall():
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
                current_cat_data['piatti'].append({
                    'id': row['piatto_id'],
                    'nome': row['piatto_nome'],
                    'descrizione': row['descrizione_pubblica'] or '',
                    'prezzo': row['prezzo'],
                    'foto': bool(row['foto_data'])
                })
        
        if current_cat_data:
            menu.append(current_cat_data)
        
        conn.close()
        return menu
    except Exception as e:
        print(f"❌ Errore in get_menu_semplificato: {e}")
        traceback.print_exc()
        return []

def format_currency(amount):
    """Formatta importo in euro"""
    return f"€{amount:.2f}"

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
            ordine['dettagli'] = dettagli
            ordini.append(ordine)
        
        conn.close()
        return ordini
    except Exception as e:
        print(f"❌ Errore in get_storico_ordini: {e}")
        return []

def salva_preordine_con_verifica(tavolo_id, carrello, note=""):
    """Salva pre-ordine con verifica e restituisce l'ID"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print("=" * 60)
        print(f"📝 SALVATAGGIO PRE-ORDINE - Tavolo: {tavolo_id}")
        print(f"   Piatti: {len(carrello)}")
        
        # Inserisci preordine
        cursor.execute("""
            INSERT INTO preordini (tavolo_id, stato, note, timestamp_creazione)
            VALUES (?, 'IN_ATTESA', ?, ?)
        """, (tavolo_id, note, timestamp))
        
        preordine_id = cursor.lastrowid
        print(f"✅ Pre-ordine ID: {preordine_id}")
        
        # Inserisci dettagli
        for item in carrello:
            cursor.execute("""
                INSERT INTO preordini_dettaglio 
                (preordine_id, piatto_id, piatto_nome, qty, prezzo_unitario, note)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                preordine_id,
                item['id'],
                item['nome'],
                item['qty'],
                item['prezzo'],
                item.get('note', '')
            ))
            print(f"   - {item['qty']}x {item['nome']} @ €{item['prezzo']}")
        
        conn.commit()
        
        # VERIFICA IMMEDIATA
        cursor.execute("SELECT COUNT(*) FROM preordini WHERE id = ?", (preordine_id,))
        if cursor.fetchone()[0] > 0:
            print(f"✅ VERIFICA OK - Pre-ordine salvato")
            cursor.execute("SELECT COUNT(*) FROM preordini_dettaglio WHERE preordine_id = ?", (preordine_id,))
            print(f"✅ Dettagli salvati: {cursor.fetchone()[0]} piatti")
        else:
            print(f"❌ VERIFICA FALLITA - Pre-ordine NON trovato!")
        
        print("=" * 60)
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

def debug_verifica_database():
    """Verifica che tutte le tabelle necessarie esistano"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        tabelle_necessarie = ['preordini', 'preordini_dettaglio', 'tavoli', 'piatti']
        risultato = {}
        
        for tabella in tabelle_necessarie:
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{tabella}'")
            risultato[tabella] = cursor.fetchone() is not None
        
        conn.close()
        return risultato
    except Exception as e:
        print(f"❌ Errore verifica database: {e}")
        return {}

# ============================================================================
# PAGINA CLIENTE PRINCIPALE
# ============================================================================

def show_cliente_page():
    """Pagina cliente con menu e storico"""
    
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
    # DEBUG INFO (visibile solo in sviluppo)
    # ========================================================================
    with st.sidebar.expander("🔧 DEBUG INFO", expanded=False):
        st.write(f"📦 Database: {DB_PATH}")
        tabelle = debug_verifica_database()
        for tabella, esiste in tabelle.items():
            if esiste:
                st.success(f"✅ {tabella}")
            else:
                st.error(f"❌ {tabella}")
    
    # ========================================================================
    # HEADER
    # ========================================================================
    st.markdown(f"""
        <div style='text-align: center; padding: 0.8rem; background-color: #d35400; color: white; border-radius: 0 0 10px 10px; margin-bottom: 1rem;'>
            <h1 style='margin:0; font-size:1.8rem;'>🍽️ PALAZZO FIORINI</h1>
            <p style='margin:0; font-size:1.2rem;'>Tavolo {tavolo_id}</p>
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
            menu = get_menu_semplificato()
            
            if not menu:
                st.warning("Menu non disponibile")
                st.info("Verifica che il database sia stato inizializzato correttamente")
                return
            
            # Tabs per categorie
            categorie = [cat['nome'] for cat in menu]
            icone = [cat['icona'] for cat in menu]
            tabs = st.tabs([f"{icona} {nome}" for icona, nome in zip(icone, categorie)])
            
            for idx, (tab, categoria) in enumerate(zip(tabs, menu)):
                with tab:
                    if not categoria['piatti']:
                        st.info("Nessun piatto disponibile")
                        continue
                    
                    for piatto in categoria['piatti']:
                        with st.container(border=True):
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                st.markdown(f"**{piatto['nome']}**")
                                if piatto['descrizione']:
                                    st.caption(piatto['descrizione'][:60])
                            
                            with col2:
                                st.markdown(f"**{format_currency(piatto['prezzo'])}**")
                                if st.button("➕", key=f"add_{piatto['id']}_{idx}"):
                                    st.session_state.cliente_carrello.append({
                                        'id': piatto['id'],
                                        'nome': piatto['nome'],
                                        'prezzo': piatto['prezzo'],
                                        'qty': 1,
                                        'note': ''
                                    })
                                    st.rerun()
        
        with col_carrello:
            st.markdown("### 🛒 Il tuo ordine")
            
            if not st.session_state.cliente_carrello:
                st.info("👆 Tocca ➕ sui piatti per iniziare")
            else:
                # Raggruppa piatti uguali
                riassunto = {}
                for item in st.session_state.cliente_carrello:
                    key = f"{item['id']}"
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
                        
                        with col2:
                            importo = item['prezzo'] * item['qty']
                            st.markdown(f"**{format_currency(importo)}**")
                            totale += importo
                        
                        with col3:
                            if st.button("🗑️", key=f"del_{key}"):
                                nuovi = []
                                for i in st.session_state.cliente_carrello:
                                    if str(i['id']) != key:
                                        nuovi.append(i)
                                st.session_state.cliente_carrello = nuovi
                                st.rerun()
                
                st.markdown(f"### Totale: {format_currency(totale)}")
                
                with st.expander("📝 Note", expanded=False):
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
                                st.error("❌ Errore nell'invio. Verifica il database.")
    
    # ========================================================================
    # TAB 2: STORICO ORDINI
    # ========================================================================
    with tab_storico:
        st.markdown("### 📜 I tuoi ordini precedenti")
        
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
                
                with st.expander(f"{stato_emoji} Ordine del {data_ora} - {ordine['stato']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Stato:** {ordine['stato']}")
                        st.write(f"**Piatti ordinati:** {ordine['numero_piatti']}")
                    
                    with col2:
                        st.write(f"**Totale:** {format_currency(ordine['totale'])}")
                    
                    st.markdown("##### Dettaglio piatti:")
                    for d in ordine['dettagli']:
                        st.markdown(f"• {d['qty']}x {d['piatto_nome']} - {format_currency(d['prezzo_unitario'] * d['qty'])}")
                        if d.get('note'):
                            st.caption(f"  📝 {d['note']}")
                    
                    if ordine.get('note'):
                        st.info(f"📝 Note ordine: {ordine['note']}")