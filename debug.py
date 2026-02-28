# debug.py
import sys
import os
import traceback
from datetime import datetime

def write_debug(message, error=None):
    """Scrive messaggi di debug in un file"""
    try:
        with open('/tmp/debug_log.txt', 'a') as f:
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"\n[{timestamp}] {message}")
            if error:
                f.write(f"\nERROR: {error}")
                f.write(f"\n{traceback.format_exc()}")
    except:
        pass

def log_environment():
    """Logga l'ambiente"""
    write_debug("=== ENVIRONMENT DEBUG ===")
    write_debug(f"Python version: {sys.version}")
    write_debug(f"Current dir: {os.getcwd()}")
    write_debug(f"Files: {os.listdir('.')}")
    write_debug(f"STREAMLIT_CLOUD: {os.environ.get('STREAMLIT_CLOUD', 'NOT SET')}")
    write_debug("=" * 30)