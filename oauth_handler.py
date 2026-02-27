"""
Gestore OAuth per login sociale
Versione 1.0 - Gestisce autenticazione con Google, Apple, Facebook
"""

import streamlit as st
import secrets
import json
import time
from datetime import datetime, timedelta
import jwt
import requests
from urllib.parse import quote

# Prova a importare config, altrimenti usa valori di default
try:
    from config import OAUTH_CONFIG, DEMO_MODE
except ImportError:
    DEMO_MODE = True
    OAUTH_CONFIG = {}

class OAuthHandler:
    """Gestisce l'autenticazione con provider social"""
    
    def __init__(self):
        self.demo_mode = DEMO_MODE
        
    def get_google_auth_url(self):
        """Genera URL per autenticazione Google"""
        if self.demo_mode:
            return None
            
        config = OAUTH_CONFIG.get('google', {})
        if not config.get('client_id'):
            return None
            
        # Genera stato per sicurezza
        state = secrets.token_urlsafe(32)
        st.session_state.oauth_state = state
        st.session_state.oauth_provider = 'google'
        
        # Costruisci URL
        params = {
            'client_id': config['client_id'],
            'redirect_uri': config['redirect_uri'],
            'response_type': 'code',
            'scope': config['scope'],
            'state': state,
            'access_type': 'offline',
            'prompt': 'consent'
        }
        
        auth_url = f"{config['authorize_url']}?{self._encode_params(params)}"
        return auth_url
    
    def get_apple_auth_url(self):
        """Genera URL per autenticazione Apple"""
        if self.demo_mode:
            return None
            
        config = OAUTH_CONFIG.get('apple', {})
        if not config.get('client_id'):
            return None
            
        state = secrets.token_urlsafe(32)
        st.session_state.oauth_state = state
        st.session_state.oauth_provider = 'apple'
        
        params = {
            'client_id': config['client_id'],
            'redirect_uri': config['redirect_uri'],
            'response_type': 'code',
            'scope': 'name email',
            'state': state,
            'response_mode': 'form_post'
        }
        
        auth_url = f"https://appleid.apple.com/auth/authorize?{self._encode_params(params)}"
        return auth_url
    
    def get_facebook_auth_url(self):
        """Genera URL per autenticazione Facebook"""
        if self.demo_mode:
            return None
            
        config = OAUTH_CONFIG.get('facebook', {})
        if not config.get('client_id'):
            return None
            
        state = secrets.token_urlsafe(32)
        st.session_state.oauth_state = state
        st.session_state.oauth_provider = 'facebook'
        
        params = {
            'client_id': config['client_id'],
            'redirect_uri': config['redirect_uri'],
            'state': state,
            'scope': config['scope'],
            'auth_type': 'rerequest'
        }
        
        auth_url = f"{config['authorize_url']}?{self._encode_params(params)}"
        return auth_url
    
    def handle_callback(self, code, state, provider):
        """Gestisce il callback OAuth"""
        if self.demo_mode:
            return self._demo_login(provider)
            
        config = OAUTH_CONFIG.get(provider, {})
        if not config:
            return None
            
        # Verifica stato
        if state != st.session_state.get('oauth_state'):
            return None
        
        try:
            if provider == 'google':
                return self._handle_google_callback(code, config)
            elif provider == 'apple':
                return self._handle_apple_callback(code, config)
            elif provider == 'facebook':
                return self._handle_facebook_callback(code, config)
        except Exception as e:
            st.error(f"Errore autenticazione: {e}")
            return None
    
    def _handle_google_callback(self, code, config):
        """Gestisce callback Google"""
        # Scambia codice per token
        token_data = {
            'code': code,
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'redirect_uri': config['redirect_uri'],
            'grant_type': 'authorization_code'
        }
        
        token_response = requests.post(config['token_url'], data=token_data)
        token_json = token_response.json()
        
        # Ottieni info utente
        headers = {'Authorization': f"Bearer {token_json['access_token']}"}
        user_response = requests.get(config['userinfo_url'], headers=headers)
        user_info = user_response.json()
        
        return {
            'provider': 'google',
            'id': user_info.get('sub'),
            'email': user_info.get('email'),
            'name': user_info.get('name'),
            'picture': user_info.get('picture'),
            'token': token_json
        }
    
    def _handle_facebook_callback(self, code, config):
        """Gestisce callback Facebook"""
        # Scambia codice per token
        token_data = {
            'code': code,
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'redirect_uri': config['redirect_uri']
        }
        
        token_response = requests.get(config['token_url'], params=token_data)
        token_json = token_response.json()
        
        # Ottieni info utente
        user_response = requests.get(
            config['userinfo_url'],
            params={'access_token': token_json['access_token']}
        )
        user_info = user_response.json()
        
        return {
            'provider': 'facebook',
            'id': user_info.get('id'),
            'name': user_info.get('name'),
            'email': user_info.get('email'),
            'picture': f"https://graph.facebook.com/{user_info['id']}/picture?type=large",
            'token': token_json
        }
    
    def _handle_apple_callback(self, code, config):
        """Gestisce callback Apple"""
        # Apple richiede gestione più complessa
        # Versione semplificata per ora
        return {
            'provider': 'apple',
            'id': 'apple_' + secrets.token_hex(8),
            'name': 'Utente Apple',
            'email': '',
            'picture': None,
            'token': {'access_token': code}
        }
    
    def _demo_login(self, provider='demo'):
        """Login demo per testing"""
        # Genera nome casuale
        nomi = ['Mario', 'Luigi', 'Giovanna', 'Anna', 'Paolo', 'Sofia']
        cognomi = ['Rossi', 'Bianchi', 'Verdi', 'Russo', 'Ferrari']
        
        import random
        nome = random.choice(nomi)
        cognome = random.choice(cognomi)
        
        return {
            'provider': provider,
            'id': f"{provider}_{secrets.token_hex(4)}",
            'name': f"{nome} {cognome}",
            'email': f"{nome.lower()}.{cognome.lower()}@example.com",
            'picture': None
        }
    
    def _encode_params(self, params):
        """Codifica parametri URL"""
        return '&'.join([f"{k}={quote(str(v))}" for k, v in params.items()])
    
    def save_user_session(self, user_info, tavolo_id):
        """Salva utente in sessione"""
        st.session_state.cliente_logged_in = True
        st.session_state.cliente_info = user_info
        st.session_state.cliente_login_time = datetime.now()
        st.session_state.cliente_tavolo = tavolo_id
        
        # Salva anche nel database (opzionale)
        self._save_user_to_db(user_info, tavolo_id)
    
    def _save_user_to_db(self, user_info, tavolo_id):
        """Salva utente nel database per statistiche"""
        try:
            import sqlite3
            conn = sqlite3.connect('ristorante.db')
            cursor = conn.cursor()
            
            # Crea tabella se non esiste
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
            print(f"Errore salvataggio cliente: {e}")
    
    def is_session_valid(self):
        """Verifica se la sessione cliente è ancora valida"""
        if not st.session_state.get('cliente_logged_in'):
            return False
        
        login_time = st.session_state.get('cliente_login_time')
        if not login_time:
            return False
        
        # Timeout dopo 2 ore
        timeout = timedelta(hours=2)
        if datetime.now() - login_time > timeout:
            return False
        
        return True
    
    def logout(self):
        """Esegue logout del cliente"""
        for key in ['cliente_logged_in', 'cliente_info', 'cliente_login_time', 
                   'cliente_tavolo', 'cliente_carrello', 'cliente_nota']:
            if key in st.session_state:
                del st.session_state[key]