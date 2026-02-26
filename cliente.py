"""
Modulo Cliente - Menu Digitale e Pre-ordini
"""

import streamlit as st
import sqlite3
import json
from datetime import datetime
import time

# ============================================================================
# FUNZIONI PER IL CLIENTE
# ============================================================================

def get_menu_completo():
    """Recupera il menu completo con foto e descrizioni"""
    conn = sqlite3.connect('ristorante.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Recupera categorie e piatti
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
    
    # Organizza i dati
    menu = {}
    for row in cursor.fetchall():
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
                'descrizione': row['descrizione_pubblica'],
                'prezzo': row['prezzo'],
                'foto': row['foto_data'],
                'tempo': row['tempo_preparazione']
            })
    
    conn.close()
    return menu

def get_variazioni_per_piatto(piatto_id):
    """Recupera le variazioni disponibili per un piatto"""
    conn = sqlite3.connect('ristorante.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT v.* 
        FROM variazioni v
        JOIN piatti p ON v.reparto_id = (
            SELECT reparto_id FROM categorie WHERE id = p.categoria_id
        )
        WHERE p.id = ? AND v.attivo = 1
        ORDER BY v.nome
    """, (piatto_id,))
    
    variazioni = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return variazioni

def salva_preordine(tavolo_id, carrello, note=""):
    """Salva un pre-ordine dal cliente e notifica il cameriere"""
    conn = None
    try:
        conn = sqlite3.connect('ristorante.db')
        cursor = conn.cursor()
        
        # Crea preordine
        cursor.execute("""
            INSERT INTO preordini (tavolo_id, stato, note, timestamp_creazione)
            VALUES (?, 'IN_ATTESA', ?, CURRENT_TIMESTAMP)
        """, (tavolo_id, note))
        
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
        
        # INVIA NOTIFICA AL CAMERIERE
        try:
            # Recupera info tavolo per il messaggio
            cursor.execute("SELECT numero FROM tavoli WHERE id = ?", (tavolo_id,))
            tavolo_num = cursor.fetchone()
            tavolo_display = tavolo_num[0] if tavolo_num else tavolo_id
            
            # Invia notifica a TUTTI i camerieri
            cursor.execute("""
                INSERT INTO notifiche (tipo, titolo, messaggio, destinatario_ruolo, letto)
                VALUES (?, ?, ?, ?, 0)
            """, (
                'PREORDINE',
                f"📱 Nuovo ordine dal Tavolo {tavolo_display}",
                f"Il tavolo {tavolo_display} ha appena inviato un ordine di {len(carrello)} piatti. Revisionalo subito!",
                'CAMERIERE'
            ))
            conn.commit()
            print(f"✅ Notifica inviata per preordine {preordine_id}")
        except Exception as e:
            print(f"⚠️ Errore notifica: {e}")
            # Non bloccare il salvataggio se la notifica fallisce
        
        return preordine_id
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"❌ Errore salvataggio preordine: {e}")
        return None
    finally:
        if conn:
            conn.close()

# ============================================================================
# FUNZIONE PER FORMARE GLI IMPORTI
# ============================================================================
def format_currency(amount):
    """Formatta importo in euro"""
    return f"€ {amount:.2f}"

# ============================================================================
# PAGINA CLIENTE
# ============================================================================

def show_cliente_page():
    """Pagina per il cliente (accessibile via QR code)"""
    
    # Ottieni parametri dall'URL
    query_params = st.query_params
    tavolo_id = query_params.get('tavolo', [None])
    if isinstance(tavolo_id, list):
        tavolo_id = tavolo_id[0] if tavolo_id else None
    
    if not tavolo_id:
        st.error("❌ QR Code non valido")
        st.info("Contattare il personale di sala")
        return
    
    # Inizializza session state per il cliente
    if 'cliente_carrello' not in st.session_state:
        st.session_state.cliente_carrello = []
    if 'cliente_nota' not in st.session_state:
        st.session_state.cliente_nota = ""
    
    # Header con info tavolo
    st.markdown(f"""
        <div style='text-align: center; padding: 1rem; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 10px; margin-bottom: 2rem;'>
            <h1>🍽️ Benvenuto al Tavolo {tavolo_id}</h1>
            <p>Scopri il nostro menu e crea il tuo ordine</p>
        </div>
    """, unsafe_allow_html=True)
    
    # Layout principale: menu a sinistra, carrello a destra
    col_menu, col_carrello = st.columns([2, 1])
    
    with col_menu:
        st.markdown("### 📖 Il Nostro Menu")
        menu = get_menu_completo()
        
        for cat_id, categoria in menu.items():
            with st.expander(f"{categoria.get('icona', '🍽️')} {categoria['nome']}", expanded=True):
                for piatto in categoria['piatti']:
                    with st.container():
                        col_img, col_info = st.columns([1, 3])
                        
                        with col_img:
                            if piatto.get('foto'):
                                st.image(piatto['foto'], width=100)
                            else:
                                st.image("https://via.placeholder.com/100?text=Piatto", width=100)
                        
                        with col_info:
                            st.markdown(f"**{piatto['nome']}**")
                            st.caption(piatto.get('descrizione', '') or " ")
                            st.markdown(f"💰 **{format_currency(piatto['prezzo'])}**")
                            
                            # Quantità
                            qty = st.number_input(
                                "Qtà",
                                min_value=0,
                                max_value=10,
                                value=0,
                                key=f"cliente_qty_{piatto['id']}",
                                label_visibility="collapsed"
                            )
                            
                            if qty > 0:
                                # Bottone per aggiungere
                                if st.button("➕ Aggiungi", key=f"cliente_add_{piatto['id']}"):
                                    st.session_state.cliente_carrello.append({
                                        'id': piatto['id'],
                                        'nome': piatto['nome'],
                                        'prezzo': piatto['prezzo'],
                                        'qty': qty,
                                        'variazioni': [],
                                        'note': ''
                                    })
                                    st.rerun()
    
    with col_carrello:
        st.markdown("### 🛒 Il Tuo Ordine")
        
        if not st.session_state.cliente_carrello:
            st.info("Carrello vuoto")
        else:
            totale = 0
            for idx, item in enumerate(st.session_state.cliente_carrello):
                with st.container(border=True):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        st.markdown(f"**{item['nome']}**")
                        if item.get('variazioni'):
                            for v in item['variazioni']:
                                st.caption(f"  ✦ {v['nome']} (+{format_currency(v['prezzo'])})")
                    
                    with col2:
                        importo = item['prezzo'] * item['qty']
                        st.markdown(f"{format_currency(importo)}")
                        totale += importo
                    
                    with col3:
                        if st.button("🗑️", key=f"cliente_del_{idx}"):
                            st.session_state.cliente_carrello.pop(idx)
                            st.rerun()
            
            st.markdown(f"### Totale: {format_currency(totale)}")
            
            # Note aggiuntive
            st.text_area(
                "Note per il cameriere",
                key="cliente_nota",
                placeholder="Allergie, preferenze, ecc...",
                value=st.session_state.cliente_nota
            )
            
            # Bottone invia ordine
            if st.button("📨 INVIA ORDINE AL CAMERIERE", type="primary", use_container_width=True):
                if st.session_state.cliente_carrello:
                    preordine_id = salva_preordine(
                        tavolo_id,
                        st.session_state.cliente_carrello,
                        st.session_state.cliente_nota
                    )
                    st.success("✅ Ordine inviato! Il cameriere lo revisionerà a breve.")
                    st.balloons()
                    st.session_state.cliente_carrello = []
                    st.session_state.cliente_nota = ""
                    time.sleep(3)
                    st.rerun()