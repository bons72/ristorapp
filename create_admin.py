import sqlite3
import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Connetti al database
conn = sqlite3.connect('ristorante.db')
cursor = conn.cursor()

# Crea utente admin (se non esiste)
admin_hash = hash_password('admin123')

try:
    cursor.execute("""
        INSERT OR REPLACE INTO utenti (id, username, password_hash, nome, cognome, ruolo, brand_id, attivo)
        VALUES (1, 'admin', ?, 'Admin', 'Super', 'SUPERADMIN', 1, 1)
    """, (admin_hash,))
    conn.commit()
    print("✅ Utente admin creato con successo!")
except Exception as e:
    print(f"❌ Errore: {e}")
finally:
    conn.close()