"""
Script per aggiornare la tabella piatti con la colonna ordine
"""
import sqlite3
import os
import tempfile

def get_db_path():
    """Restituisce il percorso del database"""
    if os.environ.get('STREAMLIT_CLOUD'):
        return os.path.join(tempfile.gettempdir(), "ristorante.db")
    else:
        return "ristorante.db"

DB_PATH = get_db_path()
print("=" * 60)
print("🔄 AGGIORNAMENTO DATABASE")
print("=" * 60)
print(f"📦 Database: {DB_PATH}")

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Verifica se la colonna esiste già
    cursor.execute("PRAGMA table_info(piatti)")
    colonne = [col[1] for col in cursor.fetchall()]
    print(f"📋 Colonne attuali in 'piatti': {', '.join(colonne)}")
    
    if 'ordine' not in colonne:
        print("➕ Aggiungo colonna 'ordine' alla tabella piatti...")
        cursor.execute("ALTER TABLE piatti ADD COLUMN ordine INTEGER DEFAULT 10")
        print("✅ Colonna 'ordine' aggiunta con successo!")
    else:
        print("✅ Colonna 'ordine' già esistente")
    
    # Verifica anche la tabella categorie
    cursor.execute("PRAGMA table_info(categorie)")
    colonne_cat = [col[1] for col in cursor.fetchall()]
    print(f"📋 Colonne in 'categorie': {', '.join(colonne_cat)}")
    
    conn.commit()
    conn.close()
    
    print("=" * 60)
    print("🎉 OPERAZIONE COMPLETATA CON SUCCESSO!")
    print("=" * 60)
    
except Exception as e:
    print(f"❌ Errore: {e}")
    import traceback
    traceback.print_exc()