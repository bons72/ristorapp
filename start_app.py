"""
Avvio applicazione con database permanente
"""

import os
import sys
import subprocess
import time

def main():
    print("=" * 60)
    print("🍽️  PALAZZO FIORINI - Avvio Applicazione")
    print("=" * 60)
    
    # Percorso database nella cartella Documenti (permanente)
    docs_path = os.path.join(os.path.expanduser("~"), "Documents", "ristorante.db")
    local_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ristorante.db")
    
    # Scegli il percorso che preferisci
    DB_PATH = docs_path  # o local_path
    
    print(f"📦 Database path: {DB_PATH}")
    
    # Imposta variabile d'ambiente per forzare il percorso
    os.environ['RISTORANTE_DB_PATH'] = DB_PATH
    
    # Verifica se il database esiste
    if not os.path.exists(DB_PATH):
        print("🔄 Database non trovato. Inizializzazione...")
        try:
            # Inizializza il database
            from db import init_db
            init_db(force=False)
            print("✅ Database inizializzato!")
        except Exception as e:
            print(f"❌ Errore inizializzazione: {e}")
            return
    
    # Avvia Streamlit
    print("\n🚀 Avvio Streamlit...")
    print("🌐 Apri il browser all'indirizzo: http://localhost:8501")
    print("=" * 60)
    
    # Comando per avviare streamlit
    cmd = [sys.executable, "-m", "streamlit", "run", "app.py"]
    
    try:
        subprocess.run(cmd)
    except KeyboardInterrupt:
        print("\n🛑 Applicazione fermata")
    except Exception as e:
        print(f"❌ Errore: {e}")

if __name__ == "__main__":
    main()