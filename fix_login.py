"""
Script per fixare login su Streamlit Cloud
"""

import sqlite3
import os
import tempfile
import hashlib

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def fix_login():
    """Crea utenti nel database cloud"""
    
    # Percorso database in cloud
    db_path = os.path.join(tempfile.gettempdir(), "ristorante.db")
    
    print("=" * 60)
    print("🔐 FIX LOGIN - STREAMLIT CLOUD")
    print("=" * 60)
    print(f"📦 Database path: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Verifica se la tabella utenti esiste
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='utenti'")
        if not cursor.fetchone():
            print("❌ Tabella utenti non trovata!")
            return False
        
        # Conta utenti esistenti
        cursor.execute("SELECT COUNT(*) FROM utenti")
        count = cursor.fetchone()[0]
        print(f"📊 Utenti trovati: {count}")
        
        # Cancella utenti esistenti (opzionale)
        # cursor.execute("DELETE FROM utenti")
        
        # Crea utente admin (se non esiste)
        cursor.execute("SELECT * FROM utenti WHERE username = 'admin'")
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO utenti (username, password_hash, nome, cognome, ruolo, brand_id, attivo)
                VALUES (?, ?, ?, ?, ?, 1, 1)
            """, ('admin', hash_password('admin123'), 'Admin', 'Super', 'SUPERADMIN'))
            print("✅ Admin creato")
        else:
            print("⚠️ Admin già esistente")
        
        # Altri utenti
        altri_utenti = [
            ('cameriere', hash_password('123'), 'Mario', 'Rossi', 'CAMERIERE'),
            ('cucina', hash_password('123'), 'Luigi', 'Verdi', 'CUCINA'),
            ('bar', hash_password('123'), 'Giovanni', 'Bianchi', 'BAR'),
            ('cassa', hash_password('123'), 'Anna', 'Neri', 'CASSA'),
        ]
        
        for username, pwd, nome, cognome, ruolo in altri_utenti:
            cursor.execute("SELECT * FROM utenti WHERE username = ?", (username,))
            if not cursor.fetchone():
                cursor.execute("""
                    INSERT INTO utenti (username, password_hash, nome, cognome, ruolo, brand_id, attivo)
                    VALUES (?, ?, ?, ?, ?, 1, 1)
                """, (username, pwd, nome, cognome, ruolo))
                print(f"✅ {username} creato")
            else:
                print(f"⚠️ {username} già esistente")
        
        conn.commit()
        
        # Verifica finale
        cursor.execute("SELECT username, ruolo FROM utenti")
        utenti = cursor.fetchall()
        print("\n📋 Utenti nel database:")
        for u in utenti:
            print(f"   - {u['username']} ({u['ruolo']})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False

if __name__ == "__main__":
    fix_login()