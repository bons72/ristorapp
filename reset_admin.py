"""
Script per resettare l'utente admin
"""

import sqlite3
import os
import tempfile
import hashlib

def hash_password(password: str) -> str:
    """Hash sicuro per le password"""
    return hashlib.sha256(password.encode()).hexdigest()

def reset_admin():
    """Resetta l'utente admin nel database"""
    
    # Determina il percorso del database
    if os.environ.get('STREAMLIT_CLOUD'):
        db_path = os.path.join(tempfile.gettempdir(), "ristorante.db")
    else:
        db_path = "ristorante.db"
    
    print("=" * 60)
    print("🔐 RESET UTENTE ADMIN")
    print("=" * 60)
    print(f"📦 Database path: {db_path}")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Assicurati che la tabella utenti esista
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS utenti (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                nome TEXT NOT NULL,
                cognome TEXT NOT NULL,
                ruolo TEXT NOT NULL,
                brand_id INTEGER DEFAULT 1,
                attivo INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Cancella utente admin esistente (se presente)
        cursor.execute("DELETE FROM utenti WHERE username = 'admin'")
        
        # Crea nuovo utente admin
        cursor.execute("""
            INSERT INTO utenti (username, password_hash, nome, cognome, ruolo, brand_id, attivo)
            VALUES (?, ?, ?, ?, ?, 1, 1)
        """, ('admin', hash_password('admin123'), 'Admin', 'Super', 'SUPERADMIN'))
        
        # Assicurati che anche gli altri utenti esistano
        altri_utenti = [
            ('cameriere', hash_password('123'), 'Mario', 'Rossi', 'CAMERIERE'),
            ('cucina', hash_password('123'), 'Luigi', 'Verdi', 'CUCINA'),
            ('bar', hash_password('123'), 'Giovanni', 'Bianchi', 'BAR'),
            ('cassa', hash_password('123'), 'Anna', 'Neri', 'CASSA'),
        ]
        
        for username, pwd, nome, cognome, ruolo in altri_utenti:
            cursor.execute("DELETE FROM utenti WHERE username = ?", (username,))
            cursor.execute("""
                INSERT INTO utenti (username, password_hash, nome, cognome, ruolo, brand_id, attivo)
                VALUES (?, ?, ?, ?, ?, 1, 1)
            """, (username, pwd, nome, cognome, ruolo))
        
        conn.commit()
        conn.close()
        
        print("✅ Utente admin creato con successo!")
        print("   Username: admin")
        print("   Password: admin123")
        print("\n✅ Altri utenti:")
        print("   cameriere/123, cucina/123, bar/123, cassa/123")
        
        return True
        
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False

if __name__ == "__main__":
    reset_admin()