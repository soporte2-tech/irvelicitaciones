import streamlit as st
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request

# =============================================================================
#           BLOQUE COMPLETO DE CONFIGURACIÓN Y FUNCIONES DE DRIVE
# =============================================================================
st.set_page_config(layout="wide")

SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid',
    'https://www.googleapis.com/auth/documents.readonly' # <-- NUEVO PERMISO
]
CLIENT_CONFIG = {
    "web": {
        "client_id": st.secrets["GOOGLE_CLIENT_ID"],
        "client_secret": st.secrets["GOOGLE_CLIENT_SECRET"],
        "redirect_uris": [st.secrets["GOOGLE_REDIRECT_URI"]],
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
    }
}
def get_google_flow():
    """Crea y devuelve el objeto Flow de Google OAuth."""
    return Flow.from_client_config(
        client_config=CLIENT_CONFIG,
        scopes=SCOPES,
        redirect_uri=st.secrets["GOOGLE_REDIRECT_URI"]
    )

def get_credentials():
    """Obtiene las credenciales, forzando un nuevo login si los scopes han cambiado."""
    
    # --- !! ESTA ES LA NUEVA LÓGICA DE COMPROBACIÓN !! ---
    if 'credentials' in st.session_state and st.session_state.credentials:
        creds = st.session_state.credentials
        # Comprobamos si todos los scopes que necesitamos están en las credenciales guardadas.
        if not all(scope in creds.scopes for scope in SCOPES):
            # Si faltan scopes, las credenciales no son válidas. Las borramos.
            del st.session_state.credentials
            # Forzamos al usuario a la página de inicio para que se loguee de nuevo.
            go_to_landing()
            st.rerun() # Detenemos la ejecución actual y recargamos
    # --- !! FIN DE LA NUEVA LÓGICA !! ---

    if 'credentials' in st.session_state and st.session_state.credentials:
        creds = st.session_state.credentials
        if creds.expired and creds.refresh_token:
            try:
                # Necesitamos importar Request de google.auth.transport.requests
                from google.auth.transport.requests import Request
                creds.refresh(Request())
                st.session_state.credentials = creds
            except Exception as e:
                # Si el refresh token falla (p.ej. ha sido revocado), borramos credenciales
                del st.session_state.credentials
                go_to_landing()
                st.rerun()
        return creds

    if 'code' in st.query_params:
        try:
            flow = get_google_flow()
            flow.fetch_token(code=st.query_params['code'])
            st.session_state.credentials = flow.credentials
            # Limpiamos los parámetros de la URL para evitar bucles
            st.query_params.clear()
            st.rerun()
        except Exception as e:
            # Si hay un error (como 'scope has changed'), lo mostramos y limpiamos el estado.
            st.error(f"Error al obtener el token: {e}")
            if 'credentials' in st.session_state:
                del st.session_state.credentials
            # Damos la opción de reintentar
            st.button("Reintentar inicio de sesión")
            st.stop() # Detenemos la ejecución para que no continúe con error
            
    return None
    
def build_drive_service(credentials):
    """Construye y devuelve el objeto de servicio de la API de Drive."""
    try:
        return build('drive', 'v3', credentials=credentials)
    except HttpError as error:
        st.error(f"No se pudo crear el servicio de Drive: {error}")
        return None
