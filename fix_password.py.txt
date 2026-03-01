import sqlite3
import hashlib

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# Connessione al database
conn = sqlite3.connect('ristorante.db')
cursor = conn.cursor()

# Correggi la password di admin
correct_hash = hash_password('admin123')
cursor.execute("UPDATE utenti SET password_hash = ? WHERE username = 'admin'", (correct_hash,))
conn.commit()

# Verifica
cursor.execute("SELECT username, password_hash FROM utenti WHERE username = 'admin'")
admin = cursor.fetchone()
print(f"✅ Admin aggiornato: {admin}")

conn.close()