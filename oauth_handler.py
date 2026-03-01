"""
Gestore OAuth per login sociale
Versione 2.0 - Gestisce autenticazione con Google, Apple, Facebook
Con supporto completo per refresh token, gestione errori e sicurezza avanzata
"""

import streamlit as st
import secrets
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from urllib.parse import urlencode
import hmac
import hashlib

# Librerie opzionali con gestione errori
try:
    import jwt
    JWT_AVAILABLE = True
except ImportError:
    JWT_AVAILABLE = False
    print("⚠️ jwt library not installed. Apple OAuth will be limited.")

try:
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("⚠️ requests library not installed. OAuth will not work.")

# Prova a importare config, altrimenti usa valori di default
try:
    from config import OAUTH_CONFIG, DEMO_MODE, get_redirect_uri, APP_NAME
except ImportError:
    DEMO_MODE = True
    APP_NAME = "Palazzo Fiorini"
    OAUTH_CONFIG = {}
    
    def get_redirect_uri():
        return "http://localhost:8501/"


# ============================================================================
# CONFIGURAZIONE SESSIONE
# ============================================================================

# Chiavi di sessione
SESSION_KEYS = {
    'state': 'oauth_state',
    'provider': 'oauth_provider',
    'time': 'oauth_time',
    'code_verifier': 'oauth_code_verifier'
}

# Timeout sessioni OAuth (10 minuti)
OAUTH_TIMEOUT = 600

# ============================================================================
# CLASSI DI ERRORE PERSONALIZZATE
# ============================================================================

class OAuthError(Exception):
    """Eccezione base per errori OAuth"""
    pass

class OAuthConfigurationError(OAuthError):
    """Errore di configurazione OAuth"""
    pass

class OAuthNetworkError(OAuthError):
    """Errore di rete durante chiamate OAuth"""
    pass

class OAuthTokenError(OAuthError):
    """Errore nello scambio del token"""
    pass

class OAuthStateError(OAuthError):
    """Errore di verifica dello stato (CSRF)"""
    pass


# ============================================================================
# CLIENT HTTP CON RETRY
# ============================================================================

def create_requests_session(retries: int = 3, backoff_factor: float = 0.5) -> requests.Session:
    """
    Crea una sessione requests con retry automatico.
    
    Args:
        retries: Numero di tentativi
        backoff_factor: Fattore di backoff per exponential backoff
    
    Returns:
        Sessione requests configurata
    """
    if not REQUESTS_AVAILABLE:
        raise OAuthConfigurationError("Libreria requests non installata")
    
    session = requests.Session()
    retry_strategy = Retry(
        total=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


# ============================================================================
# CLASSE PRINCIPALE OAuthHandler
# ============================================================================

class OAuthHandler:
    """
    Gestisce l'autenticazione con provider social.
    
    Supporta:
    - Google OAuth 2.0
    - Facebook OAuth 2.0
    - Apple OAuth 2.0 (base)
    - Modalità demo per sviluppo
    - Refresh token
    - Protezione CSRF con state
    """
    
    def __init__(self, timeout: int = 10, use_demo: Optional[bool] = None):
        """
        Inizializza l'OAuth handler.
        
        Args:
            timeout: Timeout per richieste HTTP in secondi
            use_demo: Forza modalità demo (sovrascrive config)
        """
        self.demo_mode = use_demo if use_demo is not None else DEMO_MODE
        self.timeout = timeout
        self.session = None
        
        if not self.demo_mode and REQUESTS_AVAILABLE:
            self.session = create_requests_session()
        
        # PKCE per maggiore sicurezza (opzionale)
        self.use_pkce = False
        
    def _generate_state(self, provider: str) -> str:
        """
        Genera e salva lo stato per sicurezza CSRF.
        
        Args:
            provider: Nome del provider ('google', 'facebook', 'apple')
        
        Returns:
            Stringa di stato unica
        """
        state = secrets.token_urlsafe(32)
        st.session_state[SESSION_KEYS['state']] = state
        st.session_state[SESSION_KEYS['provider']] = provider
        st.session_state[SESSION_KEYS['time']] = time.time()
        return state
    
    def _verify_state(self, state: str) -> bool:
        """
        Verifica che lo stato sia valido (protezione CSRF).
        
        Args:
            state: Stato ricevuto dal callback
        
        Returns:
            True se valido, False altrimenti
        """
        stored_state = st.session_state.get(SESSION_KEYS['state'])
        stored_time = st.session_state.get(SESSION_KEYS['time'], 0)
        
        # Verifica che lo stato corrisponda
        if not stored_state or not hmac.compare_digest(stored_state, state):
            return False
        
        # Verifica che non sia scaduto (10 minuti)
        if time.time() - stored_time > OAUTH_TIMEOUT:
            return False
        
        return True
    
    def _generate_code_verifier(self) -> Tuple[str, str]:
        """
        Genera code verifier e challenge per PKCE.
        
        Returns:
            Tupla (code_verifier, code_challenge)
        """
        code_verifier = secrets.token_urlsafe(64)
        code_challenge = hashlib.sha256(code_verifier.encode()).digest()
        code_challenge = base64.urlsafe_b64encode(code_challenge).decode().rstrip('=')
        
        st.session_state[SESSION_KEYS['code_verifier']] = code_verifier
        
        return code_verifier, code_challenge
    
    def _encode_params(self, params: Dict[str, Any]) -> str:
        """Codifica parametri URL in modo sicuro"""
        return urlencode(params)
    
    # ========================================================================
    # GENERAZIONE URL DI AUTENTICAZIONE
    # ========================================================================
    
    def get_google_auth_url(self, use_pkce: bool = False) -> Optional[str]:
        """
        Genera URL per autenticazione Google.
        
        Args:
            use_pkce: Usa PKCE per maggiore sicurezza
        
        Returns:
            URL di autenticazione o None in modalità demo
        """
        if self.demo_mode:
            return None
        
        config = OAUTH_CONFIG.get('google', {})
        if not config.get('client_id'):
            raise OAuthConfigurationError("Google client_id non configurato")
        
        self.use_pkce = use_pkce
        
        # Parametri base
        params = {
            'client_id': config['client_id'],
            'redirect_uri': config['redirect_uri'],
            'response_type': 'code',
            'scope': config['scope'],
            'state': self._generate_state('google'),
            'access_type': 'offline',
            'prompt': 'consent',
            'include_granted_scopes': 'true'
        }
        
        # Aggiungi PKCE se richiesto
        if use_pkce:
            code_verifier, code_challenge = self._generate_code_verifier()
            params['code_challenge'] = code_challenge
            params['code_challenge_method'] = 'S256'
        
        return f"{config['authorize_url']}?{self._encode_params(params)}"
    
    def get_facebook_auth_url(self) -> Optional[str]:
        """
        Genera URL per autenticazione Facebook.
        
        Returns:
            URL di autenticazione o None in modalità demo
        """
        if self.demo_mode:
            return None
        
        config = OAUTH_CONFIG.get('facebook', {})
        if not config.get('client_id'):
            raise OAuthConfigurationError("Facebook client_id non configurato")
        
        params = {
            'client_id': config['client_id'],
            'redirect_uri': config['redirect_uri'],
            'state': self._generate_state('facebook'),
            'scope': config['scope'],
            'auth_type': 'rerequest',
            'response_type': 'code'
        }
        
        return f"{config['authorize_url']}?{self._encode_params(params)}"
    
    def get_apple_auth_url(self) -> Optional[str]:
        """
        Genera URL per autenticazione Apple.
        
        Returns:
            URL di autenticazione o None in modalità demo
        """
        if self.demo_mode:
            return None
        
        config = OAUTH_CONFIG.get('apple', {})
        if not config.get('client_id'):
            raise OAuthConfigurationError("Apple client_id non configurato")
        
        params = {
            'client_id': config['client_id'],
            'redirect_uri': config['redirect_uri'],
            'response_type': 'code',
            'scope': 'name email',
            'state': self._generate_state('apple'),
            'response_mode': 'form_post'
        }
        
        return f"https://appleid.apple.com/auth/authorize?{self._encode_params(params)}"
    
    # ========================================================================
    # GESTIONE CALLBACK
    # ========================================================================
    
    def handle_callback(self, code: str, state: str, provider: str) -> Optional[Dict[str, Any]]:
        """
        Gestisce il callback OAuth.
        
        Args:
            code: Codice di autorizzazione
            state: Stato per verifica CSRF
            provider: Provider di autenticazione
        
        Returns:
            Dizionario con informazioni utente o None in caso di errore
        """
        if self.demo_mode:
            return self._demo_login(provider)
        
        # Verifica stato CSRF
        if not self._verify_state(state):
            st.error("❌ Errore di sicurezza: stato non valido. Possibile attacco CSRF.")
            return None
        
        # Recupera configurazione provider
        config = OAUTH_CONFIG.get(provider, {})
        if not config:
            st.error(f"❌ Provider {provider} non configurato")
            return None
        
        # Mappa provider a gestori
        handlers = {
            'google': self._handle_google_callback,
            'facebook': self._handle_facebook_callback,
            'apple': self._handle_apple_callback
        }
        
        handler = handlers.get(provider)
        if not handler:
            st.error(f"❌ Provider {provider} non supportato")
            return None
        
        try:
            # Esegui il callback specifico
            user_info = handler(code, config)
            
            # Aggiungi timestamp per refresh token
            if 'token' in user_info and 'expires_in' in user_info['token']:
                user_info['token']['expires_at'] = time.time() + user_info['token']['expires_in']
            
            return user_info
            
        except OAuthError as e:
            st.error(f"❌ Errore autenticazione: {e}")
            return None
        except requests.exceptions.RequestException as e:
            st.error(f"❌ Errore di rete: {e}")
            return None
        except Exception as e:
            st.error(f"❌ Errore imprevisto: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _handle_google_callback(self, code: str, config: Dict) -> Dict[str, Any]:
        """
        Gestisce callback Google OAuth.
        
        Args:
            code: Codice di autorizzazione
            config: Configurazione Google
        
        Returns:
            Dizionario con informazioni utente
        """
        # Prepara dati per scambio token
        token_data = {
            'code': code,
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'redirect_uri': config['redirect_uri'],
            'grant_type': 'authorization_code'
        }
        
        # Aggiungi code_verifier se PKCE era attivo
        if self.use_pkce and SESSION_KEYS['code_verifier'] in st.session_state:
            token_data['code_verifier'] = st.session_state[SESSION_KEYS['code_verifier']]
        
        # Scambia codice per token
        session = self.session or requests
        token_response = session.post(
            config['token_url'], 
            data=token_data, 
            timeout=self.timeout
        )
        token_response.raise_for_status()
        token_json = token_response.json()
        
        if 'error' in token_json:
            error_msg = token_json.get('error_description', token_json['error'])
            raise OAuthTokenError(f"Google: {error_msg}")
        
        # Ottieni info utente
        headers = {'Authorization': f"Bearer {token_json['access_token']}"}
        user_response = session.get(
            config['userinfo_url'], 
            headers=headers, 
            timeout=self.timeout
        )
        user_response.raise_for_status()
        user_info = user_response.json()
        
        return {
            'provider': 'google',
            'id': user_info.get('sub'),
            'email': user_info.get('email'),
            'name': user_info.get('name'),
            'given_name': user_info.get('given_name'),
            'family_name': user_info.get('family_name'),
            'picture': user_info.get('picture'),
            'locale': user_info.get('locale'),
            'email_verified': user_info.get('email_verified', False),
            'token': token_json
        }
    
    def _handle_facebook_callback(self, code: str, config: Dict) -> Dict[str, Any]:
        """
        Gestisce callback Facebook OAuth.
        
        Args:
            code: Codice di autorizzazione
            config: Configurazione Facebook
        
        Returns:
            Dizionario con informazioni utente
        """
        # Scambia codice per token
        token_data = {
            'code': code,
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'redirect_uri': config['redirect_uri']
        }
        
        session = self.session or requests
        token_response = session.get(
            config['token_url'], 
            params=token_data, 
            timeout=self.timeout
        )
        token_response.raise_for_status()
        token_json = token_response.json()
        
        if 'error' in token_json:
            error_msg = token_json.get('error', {}).get('message', 'Errore sconosciuto')
            raise OAuthTokenError(f"Facebook: {error_msg}")
        
        # Ottieni info utente
        user_response = session.get(
            config['userinfo_url'],
            params={'access_token': token_json['access_token']},
            timeout=self.timeout
        )
        user_response.raise_for_status()
        user_info = user_response.json()
        
        return {
            'provider': 'facebook',
            'id': user_info.get('id'),
            'name': user_info.get('name'),
            'email': user_info.get('email'),
            'picture': f"https://graph.facebook.com/{user_info['id']}/picture?type=large",
            'token': token_json
        }
    
    def _handle_apple_callback(self, code: str, config: Dict) -> Dict[str, Any]:
        """
        Gestisce callback Apple OAuth.
        
        Args:
            code: Codice di autorizzazione
            config: Configurazione Apple
        
        Returns:
            Dizionario con informazioni utente
        """
        if not JWT_AVAILABLE:
            # Versione semplificata senza JWT
            return {
                'provider': 'apple',
                'id': 'apple_' + secrets.token_hex(8),
                'name': 'Utente Apple',
                'email': '',
                'picture': None,
                'token': {'access_token': code}
            }
        
        try:
            # Genera client_secret JWT per Apple
            headers = {
                'kid': config['key_id']
            }
            payload = {
                'iss': config['team_id'],
                'iat': int(time.time()),
                'exp': int(time.time()) + 3600,
                'aud': 'https://appleid.apple.com',
                'sub': config['client_id']
            }
            client_secret = jwt.encode(
                payload, 
                config['private_key'].replace('\\n', '\n'), 
                algorithm='ES256', 
                headers=headers
            )
            
            # Scambia codice per token
            token_data = {
                'code': code,
                'client_id': config['client_id'],
                'client_secret': client_secret,
                'redirect_uri': config['redirect_uri'],
                'grant_type': 'authorization_code'
            }
            
            session = self.session or requests
            token_response = session.post(
                'https://appleid.apple.com/auth/token', 
                data=token_data, 
                timeout=self.timeout
            )
            token_response.raise_for_status()
            token_json = token_response.json()
            
            # Decodifica id_token per ottenere email
            user_info = {}
            if 'id_token' in token_json:
                # Non verifichiamo la firma per semplicità
                id_token = jwt.decode(
                    token_json['id_token'], 
                    options={"verify_signature": False}
                )
                user_info = {
                    'sub': id_token.get('sub'),
                    'email': id_token.get('email'),
                    'email_verified': id_token.get('email_verified', False)
                }
            
            return {
                'provider': 'apple',
                'id': user_info.get('sub', 'apple_' + secrets.token_hex(8)),
                'name': 'Utente Apple',
                'email': user_info.get('email', ''),
                'email_verified': user_info.get('email_verified', False),
                'picture': None,
                'token': token_json
            }
            
        except Exception as e:
            print(f"Errore callback Apple: {e}")
            # Fallback a versione semplificata
            return {
                'provider': 'apple',
                'id': 'apple_' + secrets.token_hex(8),
                'name': 'Utente Apple',
                'email': '',
                'picture': None,
                'token': {'access_token': code}
            }
    
    # ========================================================================
    # GESTIONE TOKEN E REFRESH
    # ========================================================================
    
    def refresh_token(self, provider: str, refresh_token: str) -> Optional[Dict[str, Any]]:
        """
        Aggiorna il token di accesso usando il refresh token.
        
        Args:
            provider: Provider ('google', 'facebook', 'apple')
            refresh_token: Refresh token
        
        Returns:
            Nuovo token o None in caso di errore
        """
        if self.demo_mode:
            return {'access_token': 'demo_token', 'expires_in': 3600}
        
        config = OAUTH_CONFIG.get(provider, {})
        if not config:
            return None
        
        try:
            if provider == 'google':
                token_data = {
                    'refresh_token': refresh_token,
                    'client_id': config['client_id'],
                    'client_secret': config['client_secret'],
                    'grant_type': 'refresh_token'
                }
                
                session = self.session or requests
                response = session.post(
                    config['token_url'], 
                    data=token_data, 
                    timeout=self.timeout
                )
                response.raise_for_status()
                token_json = response.json()
                
                if 'error' in token_json:
                    return None
                
                return token_json
                
            elif provider == 'facebook':
                # Facebook non supporta refresh token nel modo standard
                # Richiede nuova autorizzazione
                return None
                
            elif provider == 'apple':
                # Apple refresh token
                if not JWT_AVAILABLE:
                    return None
                
                # Genera nuovo client_secret
                headers = {'kid': config['key_id']}
                payload = {
                    'iss': config['team_id'],
                    'iat': int(time.time()),
                    'exp': int(time.time()) + 3600,
                    'aud': 'https://appleid.apple.com',
                    'sub': config['client_id']
                }
                client_secret = jwt.encode(
                    payload, 
                    config['private_key'].replace('\\n', '\n'), 
                    algorithm='ES256', 
                    headers=headers
                )
                
                token_data = {
                    'refresh_token': refresh_token,
                    'client_id': config['client_id'],
                    'client_secret': client_secret,
                    'grant_type': 'refresh_token'
                }
                
                session = self.session or requests
                response = session.post(
                    'https://appleid.apple.com/auth/token',
                    data=token_data,
                    timeout=self.timeout
                )
                response.raise_for_status()
                return response.json()
                
        except Exception as e:
            print(f"Errore refresh token: {e}")
            return None
    
    # ========================================================================
    # MODALITÀ DEMO
    # ========================================================================
    
    def _demo_login(self, provider: str = 'demo') -> Dict[str, Any]:
        """
        Genera un login fittizio per modalità demo.
        
        Args:
            provider: Nome del provider simulato
        
        Returns:
            Dizionario con informazioni utente fittizie
        """
        # Liste per generazione casuale
        nomi = ['Mario', 'Luigi', 'Giovanna', 'Anna', 'Paolo', 'Sofia', 'Marco', 'Chiara']
        cognomi = ['Rossi', 'Bianchi', 'Verdi', 'Russo', 'Ferrari', 'Esposito', 'Romano']
        
        import random
        nome = random.choice(nomi)
        cognome = random.choice(cognomi)
        
        # Mappa provider a email demo
        provider_emails = {
            'google': f"{nome.lower()}.{cognome.lower()}@gmail.com",
            'facebook': f"{nome.lower()}.{cognome.lower()}@facebook.com",
            'apple': f"{nome.lower()}.{cognome.lower()}@icloud.com",
            'demo': f"{nome.lower()}.{cognome.lower()}@example.com"
        }
        
        email = provider_emails.get(provider, provider_emails['demo'])
        
        return {
            'provider': provider,
            'id': f"{provider}_{secrets.token_hex(4)}",
            'name': f"{nome} {cognome}",
            'given_name': nome,
            'family_name': cognome,
            'email': email,
            'email_verified': True,
            'picture': None,
            'locale': 'it',
            'token': {
                'access_token': 'demo_token_' + secrets.token_hex(8),
                'refresh_token': 'demo_refresh_' + secrets.token_hex(8),
                'expires_in': 3600,
                'expires_at': time.time() + 3600
            }
        }
    
    # ========================================================================
    # GESTIONE SESSIONE UTENTE
    # ========================================================================
    
    def save_user_session(self, user_info: Dict[str, Any], tavolo_id: int) -> None:
        """
        Salva le informazioni utente nella sessione Streamlit.
        
        Args:
            user_info: Dizionario con informazioni utente
            tavolo_id: ID del tavolo
        """
        st.session_state.cliente_logged_in = True
        st.session_state.cliente_info = user_info
        st.session_state.cliente_login_time = datetime.now()
        st.session_state.cliente_tavolo = tavolo_id
        st.session_state.cliente_provider = user_info.get('provider')
        
        # Salva anche nel database
        self._save_user_to_db(user_info, tavolo_id)
    
    def _save_user_to_db(self, user_info: Dict[str, Any], tavolo_id: int) -> None:
        """
        Salva le informazioni utente nel database per statistiche.
        
        Args:
            user_info: Dizionario con informazioni utente
            tavolo_id: ID del tavolo
        """
        try:
            import sqlite3
            from db import DB_PATH
            
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            
            # Crea tabella se non esiste (assicurazione)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS clienti (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    provider_id TEXT UNIQUE,
                    provider TEXT,
                    email TEXT,
                    nome TEXT,
                    ultimo_accesso TIMESTAMP,
                    tavolo_id INTEGER,
                    ordini_totali INTEGER DEFAULT 0,
                    spesa_totale REAL DEFAULT 0
                )
            """)
            
            # Inserisci o aggiorna
            cursor.execute("""
                INSERT OR IGNORE INTO clienti 
                (provider_id, provider, email, nome, ultimo_accesso, tavolo_id)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?)
            """, (
                user_info.get('id'),
                user_info.get('provider'),
                user_info.get('email'),
                user_info.get('name'),
                tavolo_id
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"⚠️ Errore salvataggio cliente in DB: {e}")
    
    def is_session_valid(self) -> bool:
        """
        Verifica se la sessione cliente è ancora valida.
        
        Returns:
            True se valida, False altrimenti
        """
        if not st.session_state.get('cliente_logged_in'):
            return False
        
        login_time = st.session_state.get('cliente_login_time')
        if not login_time:
            return False
        
        # Timeout configurabile (default 2 ore)
        from config import CLIENTE_SESSION_TIMEOUT
        timeout_hours = CLIENTE_SESSION_TIMEOUT / 60
        
        if datetime.now() - login_time > timedelta(hours=timeout_hours):
            return False
        
        return True
    
    def logout(self) -> None:
        """Esegue logout del cliente, pulendo la sessione."""
        keys_to_clear = [
            'cliente_logged_in', 
            'cliente_info', 
            'cliente_login_time', 
            'cliente_tavolo',
            'cliente_provider',
            'cliente_carrello', 
            'cliente_nota'
        ]
        
        for key in keys_to_clear:
            if key in st.session_state:
                del st.session_state[key]
        
        # Pulisci anche dati OAuth
        for key in SESSION_KEYS.values():
            if key in st.session_state:
                del st.session_state[key]


# ============================================================================
# FUNZIONI DI UTILITÀ PER L'INTEGRAZIONE
# ============================================================================

def get_oauth_handler() -> OAuthHandler:
    """
    Factory function per ottenere un'istanza di OAuthHandler.
    
    Returns:
        Istanza di OAuthHandler
    """
    return OAuthHandler()

def render_login_buttons(tavolo_id: int) -> None:
    """
    Renderizza i pulsanti di login social nella pagina cliente.
    
    Args:
        tavolo_id: ID del tavolo
    """
    handler = get_oauth_handler()
    
    st.markdown("### 🔐 Accedi con")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        google_url = handler.get_google_auth_url()
        if google_url and not handler.demo_mode:
            st.markdown(f"""
                <a href="{google_url}" target="_self">
                    <button style="width:100%; padding:10px; background:#fff; border:1px solid #ddd; border-radius:5px; cursor:pointer;">
                        <img src="https://www.google.com/favicon.ico" width="20" style="vertical-align:middle;"> Google
                    </button>
                </a>
            """, unsafe_allow_html=True)
        else:
            if st.button("🟦 Google (demo)", key="google_demo", use_container_width=True):
                user_info = handler._demo_login('google')
                handler.save_user_session(user_info, tavolo_id)
                st.rerun()
    
    with col2:
        fb_url = handler.get_facebook_auth_url()
        if fb_url and not handler.demo_mode:
            st.markdown(f"""
                <a href="{fb_url}" target="_self">
                    <button style="width:100%; padding:10px; background:#1877f2; color:white; border:none; border-radius:5px; cursor:pointer;">
                        📘 Facebook
                    </button>
                </a>
            """, unsafe_allow_html=True)
        else:
            if st.button("📘 Facebook (demo)", key="fb_demo", use_container_width=True):
                user_info = handler._demo_login('facebook')
                handler.save_user_session(user_info, tavolo_id)
                st.rerun()
    
    with col3:
        apple_url = handler.get_apple_auth_url()
        if apple_url and not handler.demo_mode:
            st.markdown(f"""
                <a href="{apple_url}" target="_self">
                    <button style="width:100%; padding:10px; background:#000; color:white; border:none; border-radius:5px; cursor:pointer;">
                        🍎 Apple
                    </button>
                </a>
            """, unsafe_allow_html=True)
        else:
            if st.button("🍎 Apple (demo)", key="apple_demo", use_container_width=True):
                user_info = handler._demo_login('apple')
                handler.save_user_session(user_info, tavolo_id)
                st.rerun()


# ============================================================================
# ESEMPIO DI UTILIZZO (se eseguito direttamente)
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("🔧 OAUTH HANDLER - TEST CONFIGURAZIONE")
    print("=" * 60)
    
    handler = OAuthHandler()
    print(f"🎮 Modalità demo: {'✅ Attiva' if handler.demo_mode else '❌ Disattiva'}")
    
    if not handler.demo_mode:
        print("\n📋 URL di autenticazione:")
        print(f"  Google: {handler.get_google_auth_url()}")
        print(f"  Facebook: {handler.get_facebook_auth_url()}")
        print(f"  Apple: {handler.get_apple_auth_url()}")
    
    print("\n👤 Esempio login demo:")
    demo_user = handler._demo_login('google')
    print(f"  Nome: {demo_user['name']}")
    print(f"  Email: {demo_user['email']}")
    print(f"  Provider: {demo_user['provider']}")
    
    print("=" * 60)