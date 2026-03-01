"""
Configurazione OAuth per login sociale
Versione 2.0 - Professionale con supporto variabili d'ambiente
"""

import os
from typing import Dict, Any

# ============================================================================
# CONFIGURAZIONE OAUTH
# ============================================================================

def get_redirect_uri() -> str:
    """
    Restituisce l'URI di reindirizzamento corretto in base all'ambiente.
    In produzione, usa l'URL pubblico di Streamlit Cloud.
    """
    if os.environ.get('STREAMLIT_CLOUD'):
        # In Streamlit Cloud, l'URL è impostato automaticamente
        return os.environ.get('APP_URL', 'https://bons72-ristorapp.streamlit.app/')
    else:
        # In sviluppo locale
        return os.environ.get('OAUTH_REDIRECT_URI', 'http://localhost:8501/')

# Configurazione OAuth con supporto variabili d'ambiente
OAUTH_CONFIG: Dict[str, Dict[str, Any]] = {
    # ------------------------------------------------------------------------
    # GOOGLE OAUTH
    # ------------------------------------------------------------------------
    'google': {
        'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
        'client_secret': os.environ.get('GOOGLE_CLIENT_SECRET', ''),
        'authorize_url': 'https://accounts.google.com/o/oauth2/auth',
        'token_url': 'https://oauth2.googleapis.com/token',
        'userinfo_url': 'https://www.googleapis.com/oauth2/v3/userinfo',
        'scope': 'openid email profile',
        'redirect_uri': get_redirect_uri(),
    },
    
    # ------------------------------------------------------------------------
    # APPLE OAUTH
    # ------------------------------------------------------------------------
    'apple': {
        'client_id': os.environ.get('APPLE_CLIENT_ID', ''),
        'team_id': os.environ.get('APPLE_TEAM_ID', ''),
        'key_id': os.environ.get('APPLE_KEY_ID', ''),
        'private_key': os.environ.get('APPLE_PRIVATE_KEY', ''),
        'redirect_uri': get_redirect_uri(),
    },
    
    # ------------------------------------------------------------------------
    # FACEBOOK OAUTH
    # ------------------------------------------------------------------------
    'facebook': {
        'client_id': os.environ.get('FACEBOOK_CLIENT_ID', ''),
        'client_secret': os.environ.get('FACEBOOK_CLIENT_SECRET', ''),
        'authorize_url': 'https://www.facebook.com/v18.0/dialog/oauth',
        'token_url': 'https://graph.facebook.com/v18.0/oauth/access_token',
        'userinfo_url': 'https://graph.facebook.com/me?fields=id,name,email,picture',
        'scope': 'email public_profile',
        'redirect_uri': get_redirect_uri(),
    },
}

# ============================================================================
# MODALITÀ DI ESECUZIONE
# ============================================================================

# Modalità demo (True = senza credenziali reali)
# In produzione, impostare a False e configurare le credenziali
DEMO_MODE = os.environ.get('DEMO_MODE', 'True').lower() in ('true', '1', 't')

# ============================================================================
# CONFIGURAZIONE APP
# ============================================================================

# Nome e versione dell'applicazione
APP_NAME = "Palazzo Fiorini"
APP_VERSION = "2.0"

# URL pubblico dell'applicazione
# In sviluppo: http://localhost:8501
# In produzione: https://bons72-ristorapp.streamlit.app
APP_URL = os.environ.get('APP_URL', 'http://localhost:8501')

# Timeout sessione cliente (in minuti) - default 2 ore
CLIENTE_SESSION_TIMEOUT = int(os.environ.get('CLIENTE_SESSION_TIMEOUT', '120'))

# ============================================================================
# CONFIGURAZIONI AGGIUNTIVE
# ============================================================================

# Abilita/disabilita registrazione nuovi utenti
ALLOW_NEW_REGISTRATIONS = os.environ.get('ALLOW_NEW_REGISTRATIONS', 'True').lower() in ('true', '1', 't')

# Lingua predefinita
DEFAULT_LANGUAGE = os.environ.get('DEFAULT_LANGUAGE', 'it')

# ============================================================================
# FUNZIONI DI UTILITÀ
# ============================================================================

def is_demo_mode() -> bool:
    """Restituisce True se siamo in modalità demo"""
    return DEMO_MODE

def get_oauth_config(provider: str = 'google') -> Dict[str, Any]:
    """
    Restituisce la configurazione OAuth per un provider specifico.
    
    Args:
        provider: 'google', 'apple', o 'facebook'
    
    Returns:
        Dict con la configurazione del provider
    """
    return OAUTH_CONFIG.get(provider, {})

def get_app_url() -> str:
    """Restituisce l'URL pubblico dell'applicazione"""
    return APP_URL

def get_session_timeout() -> int:
    """Restituisce il timeout della sessione in minuti"""
    return CLIENTE_SESSION_TIMEOUT

# ============================================================================
# ESEMPIO DI UTILIZZO
# ============================================================================
if __name__ == "__main__":
    print("=" * 60)
    print("🔧 CONFIGURAZIONE PALAZZO FIORINI")
    print("=" * 60)
    print(f"📱 App: {APP_NAME} v{APP_VERSION}")
    print(f"🌐 URL: {APP_URL}")
    print(f"🎮 Modalità demo: {'✅ Attiva' if DEMO_MODE else '❌ Disattiva'}")
    print(f"⏱️ Timeout sessione: {CLIENTE_SESSION_TIMEOUT} minuti")
    print("=" * 60)
    print("\n📋 Provider OAuth configurati:")
    for provider in OAUTH_CONFIG.keys():
        client_id = OAUTH_CONFIG[provider]['client_id']
        status = "✅ Configurato" if client_id else "⏳ In attesa"
        print(f"  • {provider.capitalize()}: {status}")
    print("=" * 60)