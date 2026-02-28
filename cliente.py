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
# FUNZIONI VELOCI PER IL MENU
# ============================================================================

@st.cache_data(ttl=60)  # Cache per 60 secondi
def get_menu_semplificato():
    """Recupera il menu in formato semplice e veloce"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Query unica per tutto il menu
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
        
        # Organizza i dati in modo efficiente
        menu = []
        current_cat = None
        current_cat_data = None
        
        for row in cursor.fetchall():
            cat_id = row['cat_id']
            
            # Nuova categoria
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
            
            # Aggiungi piatto se esiste
            if row['piatto_id']:
                current_cat_data['piatti'].append({
                    'id': row['piatto_id'],
                    'nome': row['piatto_nome'],
                    'descrizione': row['descrizione_pubblica'] or '',
                    'prezzo': row['prezzo'],
                    'foto': bool(row['foto_data'])  # Solo per sapere se c'è foto
                })
        
        # Aggiungi l'ultima categoria
        if current_cat_data:
            menu.append(current_cat_data)
        
        conn.close()
        return menu
    except Exception as e:
        print(f"❌ Errore in get_menu_semplificato: {e}")
        traceback.print_exc()
        return []

def format_currency(amount):
    """Formatta importo in euro (veloce)"""
    return f"€{amount:.2f}"

def salva_preordine_veloce(tavolo_id, carrello, note=""):
    """Salva pre-ordine in modo ottimizzato con verifica"""
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        print("=" * 60)
        print(f"📝 SALVATAGGIO PRE-ORDINE - Tavolo: {tavolo_id}")
        print(f"   Piatti: {len(carrello)}")
        print(f"   Note: {note}")
        for item in carrello:
            print(f"   - {item['qty']}x {item['nome']} @ €{item['prezzo']}")
        
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
        
        conn.commit()
        print(f"✅ Pre-ordine salvato con successo!")
        
        # VERIFICA IMMEDIATA - Controlla che il pre-ordine sia stato effettivamente salvato
        cursor.execute("SELECT COUNT(*) as cnt FROM preordini WHERE id = ?", (preordine_id,))
        verifica = cursor.fetchone()
        if verifica and verifica[0] > 0:
            print(f"✅ VERIFICA OK - Pre-ordine {preordine_id} presente nel database")
            
            # Controlla anche i dettagli
            cursor.execute("SELECT COUNT(*) as cnt FROM preordini_dettaglio WHERE preordine_id = ?", (preordine_id,))
            verifica_dettagli = cursor.fetchone()
            print(f"✅ Dettagli salvati: {verifica_dettagli[0]} piatti")
        else:
            print(f"❌ VERIFICA FALLITA - Pre-ordine {preordine_id} NON trovato nel database!")
        
        print("=" * 60)
        
        return preordine_id
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ ERRORE in salva_preordine_veloce: {e}")
        traceback.print_exc()
        return None
    finally:
        if conn:
            conn.close()

def debug_verifica_tabelle():
    """Funzione di debug per verificare lo stato delle tabelle"""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        print("=" * 60)
        print("🔍 DEBUG VERIFICA TABELLE")
        print("=" * 60)
        
        # Verifica tabella preordini
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='preordini'")
        if cursor.fetchone():
            print("✅ Tabella 'preordini' esiste")
            cursor.execute("SELECT COUNT(*) FROM preordini")
            count = cursor.fetchone()[0]
            print(f"   Record in preordini: {count}")
        else:
            print("❌ Tabella 'preordini' NON esiste")
        
        # Verifica tabella preordini_dettaglio
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='preordini_dettaglio'")
        if cursor.fetchone():
            print("✅ Tabella 'preordini_dettaglio' esiste")
            cursor.execute("SELECT COUNT(*) FROM preordini_dettaglio")
            count = cursor.fetchone()[0]
            print(f"   Record in preordini_dettaglio: {count}")
        else:
            print("❌ Tabella 'preordini_dettaglio' NON esiste")
        
        conn.close()
        print("=" * 60)
    except Exception as e:
        print(f"❌ Errore in debug_verifica_tabelle: {e}")

# ============================================================================
# PAGINA CLIENTE VELOCE
# ============================================================================

def show_cliente_page():
    """Pagina cliente super veloce e intuitiva"""
    
    # DEBUG - Verifica tabelle all'avvio
    debug_verifica_tabelle()
    
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
    # HEADER SEMPLICE
    # ========================================================================
    st.markdown(f"""
        <div style='text-align: center; padding: 0.8rem; background-color: #d35400; color: white; border-radius: 0 0 10px 10px; margin-bottom: 1rem;'>
            <h1 style='margin:0; font-size:1.8rem;'>🍽️ PALAZZO FIORINI</h1>
            <p style='margin:0; font-size:1.2rem;'>Tavolo {tavolo_id}</p>
        </div>
    """, unsafe_allow_html=True)
    
    # ========================================================================
    # INIZIALIZZA CARRELLO (in session state)
    # ========================================================================
    if 'cliente_carrello' not in st.session_state:
        st.session_state.cliente_carrello = []
    if 'cliente_nota' not in st.session_state:
        st.session_state.cliente_nota = ""
    
    # ========================================================================
    # LAYOUT: MENU A SINISTRA, CARRELLO A DESTRA
    # ========================================================================
    col_menu, col_carrello = st.columns([2, 1])
    
    # ========================================================================
    # COLONNA SINISTRA - MENU
    # ========================================================================
    with col_menu:
        # Carica menu (con cache)
        menu = get_menu_semplificato()
        
        if not menu:
            st.warning("Menu non disponibile")
            return
        
        # Crea tabs per le categorie (navigazione veloce)
        categorie = [cat['nome'] for cat in menu]
        icone = [cat['icona'] for cat in menu]
        
        # Tabs con icone
        tabs = st.tabs([f"{icona} {nome}" for icona, nome in zip(icone, categorie)])
        
        # Mostra piatti per ogni categoria
        for idx, (tab, categoria) in enumerate(zip(tabs, menu)):
            with tab:
                for piatto in categoria['piatti']:
                    with st.container(border=True):
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.markdown(f"**{piatto['nome']}**")
                            if piatto['descrizione']:
                                st.caption(piatto['descrizione'][:60])
                        
                        with col2:
                            st.markdown(f"**{format_currency(piatto['prezzo'])}**")
                            
                            # Pulsanti + e - (interfaccia tattile)
                            if st.button("➕", key=f"add_{piatto['id']}"):
                                st.session_state.cliente_carrello.append({
                                    'id': piatto['id'],
                                    'nome': piatto['nome'],
                                    'prezzo': piatto['prezzo'],
                                    'qty': 1,
                                    'note': ''
                                })
                                st.rerun()
    
    # ========================================================================
    # COLONNA DESTRA - CARRELLO
    # ========================================================================
    with col_carrello:
        st.markdown("### 🛒 Ordine")
        
        if not st.session_state.cliente_carrello:
            st.info("👆 Tocca ➕ per ordinare")
        else:
            # Raggruppa piatti uguali
            carrello_riassunto = {}
            for item in st.session_state.cliente_carrello:
                key = f"{item['id']}_{item.get('note', '')}"
                if key not in carrello_riassunto:
                    carrello_riassunto[key] = item.copy()
                else:
                    carrello_riassunto[key]['qty'] += item['qty']
            
            totale = 0
            for key, item in carrello_riassunto.items():
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
                            # Rimuove tutti gli item con quella chiave
                            nuovi = []
                            for i in st.session_state.cliente_carrello:
                                k = f"{i['id']}_{i.get('note', '')}"
                                if k != key:
                                    nuovi.append(i)
                            st.session_state.cliente_carrello = nuovi
                            st.rerun()
            
            st.markdown(f"### Totale: {format_currency(totale)}")
            
            # Note (in expander per non occupare spazio)
            with st.expander("📝 Note", expanded=False):
                note = st.text_area(
                    "Allergie, preferenze...",
                    value=st.session_state.cliente_nota,
                    key="note_input",
                    label_visibility="collapsed",
                    placeholder="Es. Senza glutine, ben cotto..."
                )
                st.session_state.cliente_nota = note
            
            # Bottone invio grande e visibile
            if st.button("📨 INVIA ORDINE", type="primary", use_container_width=True):
                if st.session_state.cliente_carrello:
                    with st.spinner("Invio in corso..."):
                        preordine_id = salva_preordine_veloce(
                            tavolo_id,
                            st.session_state.cliente_carrello,
                            st.session_state.cliente_nota
                        )
                        
                        if preordine_id:
                            st.success("✅ Ordine inviato!")
                            st.balloons()
                            st.session_state.cliente_carrello = []
                            st.session_state.cliente_nota = ""
                            time.sleep(2)
                            st.rerun()
                        else:
                            st.error("❌ Errore nell'invio. Riprova o contatta il personale.")