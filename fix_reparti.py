"""
Script per creare i reparti manualmente
"""

import sqlite3
import os
import tempfile

def fix_reparti():
    """Crea i reparti nel database"""
    
    # Determina il percorso del database
    if os.environ.get('STREAMLIT_CLOUD'):
        db_path = os.path.join(tempfile.gettempdir(), "ristorante.db")
    else:
        db_path = "ristorante.db"
    
    print("=" * 60)
    print("🔧 CREAZIONE REPARTI")
    print("=" * 60)
    print(f"📦 Database path: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Crea tabella reparti se non esiste
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS reparti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT UNIQUE NOT NULL,
                icona TEXT DEFAULT '👨‍🍳',
                colore TEXT DEFAULT '#3498db',
                ordine INTEGER DEFAULT 999,
                attivo INTEGER DEFAULT 1
            )
        """)
        
        # Inserisci reparti
        reparti = [
            (1, 'CUCINA', '👨‍🍳', '#e74c3c', 1),
            (2, 'BAR', '🍸', '#3498db', 2),
            (3, 'PASTICCERIA', '🍰', '#9b59b6', 3),
            (4, 'PIZZERIA', '🍕', '#e67e22', 4),
        ]
        
        for id, nome, icona, colore, ordine in reparti:
            cursor.execute("""
                INSERT OR REPLACE INTO reparti (id, nome, icona, colore, ordine, attivo)
                VALUES (?, ?, ?, ?, ?, 1)
            """, (id, nome, icona, colore, ordine))
            print(f"✅ Reparto {id}: {nome}")
        
        conn.commit()
        
        # Verifica
        cursor.execute("SELECT COUNT(*) FROM reparti")
        count = cursor.fetchone()[0]
        print(f"\n📊 Totale reparti: {count}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False

if __name__ == "__main__":
    fix_reparti()