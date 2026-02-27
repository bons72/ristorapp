"""
Configurazione OAuth per login sociale
Versione 1.0 - Configurazione di base
"""

# Configurazione OAuth (da ottenere dai provider)
OAUTH_CONFIG = {
    # Google OAuth - https://console.cloud.google.com/
    'google': {
        'client_id': '',  # Inserisci qui il tuo Client ID Google
        'client_secret': '',  # Inserisci qui il tuo Client Secret Google
        'authorize_url': 'https://accounts.google.com/o/oauth2/auth',
        'token_url': 'https://oauth2.googleapis.com/token',
        'userinfo_url': 'https://www.googleapis.com/oauth2/v3/userinfo',
        'scope': 'openid email profile',
        'redirect_uri': 'http://localhost:8501/'
    },
    
    # Apple OAuth - https://developer.apple.com/
    'apple': {
        'client_id': '',
        'team_id': '',
        'key_id': '',
        'private_key': '',
        'redirect_uri': 'http://localhost:8501/'
    },
    
    # Facebook OAuth - https://developers.facebook.com/
    'facebook': {
        'client_id': '',
        'client_secret': '',
        'authorize_url': 'https://www.facebook.com/v18.0/dialog/oauth',
        'token_url': 'https://graph.facebook.com/v18.0/oauth/access_token',
        'userinfo_url': 'https://graph.facebook.com/me?fields=id,name,email,picture',
        'scope': 'email public_profile',
        'redirect_uri': 'http://localhost:8501/'
    }
}

# Modalità demo (True = senza credenziali reali)
DEMO_MODE = True

# Configurazione app
APP_NAME = "Palazzo Fiorini"
APP_VERSION = "2.0"
APP_URL = "http://localhost:8501"

# Timeout sessione cliente (in minuti)
CLIENTE_SESSION_TIMEOUT = 120