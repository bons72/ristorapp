"""
Script per aggiungere la colonna ordine alla tabella piatti
"""
import sqlite3
import os
import tempfile

def get_db_path():
    if os.environ.get('STREAMLIT_CLOUD'):
        return os.path.join(tempfile.gettempdir(), "ristorante.db")
    else:
        return "ristorante.db"

DB_PATH = get_db_path()
print("=" * 60)
print("🔧 AGGIUNTA COLONNA ORDINE")
print("=" * 60)
print(f"📦 Database: {DB_PATH}")

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Verifica se la colonna esiste già
    cursor.execute("PRAGMA table_info(piatti)")
    colonne = [col[1] for col in cursor.fetchall()]
    print(f"📋 Colonne attuali: {', '.join(colonne)}")
    
    if 'ordine' not in colonne:
        print("➕ Aggiungo colonna 'ordine'...")
        cursor.execute("ALTER TABLE piatti ADD COLUMN ordine INTEGER DEFAULT 10")
        conn.commit()
        print("✅ Colonna 'ordine' aggiunta con successo!")
    else:
        print("✅ Colonna 'ordine' già esistente")
    
    # Verifica finale
    cursor.execute("PRAGMA table_info(piatti)")
    colonne = [col[1] for col in cursor.fetchall()]
    print(f"📋 Colonne finali: {', '.join(colonne)}")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Errore: {e}")

print("=" * 60)