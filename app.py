# app.py
# -----------------------------------------------------------------------------
# Este es el punto de entrada principal de la aplicación Streamlit.
# Actúa como el "director de orquesta": gestiona la autenticación, el estado
# de la sesión, la navegación y llama a la función de la página correcta
# desde el módulo ui_pages.
# -----------------------------------------------------------------------------

import streamlit as st
import google.generativeai as genai
import json
import time

# =============================================================================
#           BLOQUE DE IMPORTACIONES DE OTROS MÓDULOS
# =============================================================================

from auth import get_credentials, build_drive_service
from ui_pages import (
    landing_page, project_selection_page, phase_1_page, phase_1_results_page,
    phase_2_page, phase_3_page, phase_4_page, phase_5_page
)
from prompts import PROMPT_PLIEGOS
from utils import limpiar_respuesta_json
from drive_utils import find_or_create_folder, get_files_in_project, download_file_from_drive

# =============================================================================
#           CONFIGURACIÓN GLOBAL Y GESTIÓN DE ESTADO
# =============================================================================

st.set_page_config(layout="wide")

# --- Inicialización de Estado ---
# Es crucial para que la app recuerde en qué página está y guarde datos entre interacciones.
if 'page' not in st.session_state: st.session_state.page = 'landing'
if 'credentials' not in st.session_state: st.session_state.credentials = None
if 'drive_service' not in st.session_state: st.session_state.drive_service = None
if 'selected_project' not in st.session_state: st.session_state.selected_project = None
if 'generated_doc_buffer' not in st.session_state: st.session_state.generated_doc_buffer = None
if 'generated_doc_filename' not in st.session_state: st.session_state.generated_doc_filename = ""
if 'refined_doc_buffer' not in st.session_state: st.session_state.refined_doc_buffer = None
if 'refined_doc_filename' not in st.session_state: st.session_state.refined_doc_filename = ""
if 'generated_structure' not in st.session_state: st.session_state.generated_structure = None
if 'uploaded_pliegos' not in st.session_state: st.session_state.uploaded_pliegos = None


# --- Funciones de Navegación ---
# Estas funciones modifican el estado para cambiar de página.
def go_to_landing(): st.session_state.page = 'landing'
def go_to_project_selection(): st.session_state.page = 'project_selection'
def go_to_phase1(): st.session_state.page = 'phase_1'
def go_to_phase1_results(): st.session_state.page = 'phase_1_results'
def go_to_phase2(): st.session_state.page = 'phase_2'
def go_to_phase3(): st.session_state.page = 'phase_3'
def go_to_phase4(): st.session_state.page = 'phase_4'
def go_to_phase5(): st.session_state.page = 'phase_5'

# --- Función de Limpieza ---
def back_to_project_selection_and_cleanup():
    """Limpia el estado de la sesión relacionado con un proyecto específico."""
    keys_to_clear = [
        'generated_structure', 'word_file', 'uploaded_template', 
        'uploaded_pliegos', 'selected_project', 'generated_doc_buffer', 
        'refined_doc_buffer', 'generated_doc_filename', 'refined_doc_filename'
    ]
    for key in keys_to_clear:
        if key in st.session_state:
            del st.session_state[key]
    go_to_project_selection()

# =============================================================================
#           LÓGICA CENTRAL DE LA APLICACIÓN (NO-UI)
# =============================================================================

def handle_full_regeneration(model):
    """
    Función que genera un índice desde cero analizando los archivos de 'Pliegos'.
    Se mantiene aquí porque es una lógica de app, no una página de UI.
    """
    if not st.session_state.get('drive_service') or not st.session_state.get('selected_project'):
        st.error("Error de sesión. No se puede iniciar la regeneración."); return False

    with st.spinner("Descargando archivos de 'Pliegos' y re-analizando desde cero..."):
        try:
            service = st.session_state.drive_service
            project_folder_id = st.session_state.selected_project['id']
            pliegos_folder_id = find_or_create_folder(service, "Pliegos", parent_id=project_folder_id)
            document_files = get_files_in_project(service, pliegos_folder_id)

            if not document_files:
                st.warning("No se encontraron archivos en la carpeta 'Pliegos' para analizar."); return False

            contenido_ia = [PROMPT_PLIEGOS]
            for file in document_files:
                file_content_bytes = download_file_from_drive(service, file['id'])
                contenido_ia.append({"mime_type": file['mimeType'], "data": file_content_bytes.getvalue()})

            response = model.generate_content(contenido_ia, generation_config={"response_mime_type": "application/json"})
            
            json_limpio_str = limpiar_respuesta_json(response.text)
            if json_limpio_str:
                st.session_state.generated_structure = json.loads(json_limpio_str)
                st.session_state.uploaded_pliegos = document_files
                st.toast("✅ ¡Índice regenerado desde cero con éxito!")
                return True
            else:
                st.error("La IA devolvió una respuesta vacía o no válida."); return False
        except Exception as e:
            st.error(f"Ocurrió un error durante la regeneración completa: {e}"); return False

# app.py (Sección final corregida)

# =============================================================================
#                        LÓGICA PRINCIPAL (ROUTER)
# =============================================================================

# 1. Intenta obtener las credenciales del usuario.
credentials = get_credentials()

# 2. Si no hay credenciales, muestra la página de inicio de sesión.
if not credentials:
    landing_page()
else:
    # 3. Si hay credenciales, configura los servicios (una sola vez).
    # Este bloque 'try-except' es para evitar que se reconfigure en cada rerun.
    try:
        if 'drive_service' not in st.session_state or st.session_state.drive_service is None:
            st.session_state.drive_service = build_drive_service(credentials)
        
        # Es buena práctica configurar esto también solo si no está ya hecho
        if 'gemini_model' not in st.session_state:
            genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
            st.session_state.gemini_model = genai.GenerativeModel('models/gemini-1.5-pro-latest')

        model = st.session_state.gemini_model

    except Exception as e:
        st.error(f"Error en la configuración de servicios. Detalle: {e}")
        # Limpiamos credenciales por si el error es de token inválido
        del st.session_state['credentials']
        st.button("Reintentar conexión", on_click=go_to_landing)
        st.stop()
        
    # --- ¡CORRECCIÓN CLAVE! ---
    # Si estamos autenticados pero la página de sesión sigue siendo 'landing',
    # significa que acabamos de iniciar sesión. Forzamos el paso a la siguiente página.
    if st.session_state.page == 'landing':
        go_to_project_selection()
        # Forzamos un rerun para que el router de abajo ya entre con la página correcta.
        st.rerun()

    # 4. Router: Llama a la función de la página actual según el estado.
    page = st.session_state.page
    
    # Ya no necesitamos el 'if page == 'landing'' aquí porque la corrección de arriba lo maneja.
    if page == 'project_selection':
        project_selection_page(go_to_landing, go_to_phase1)
    elif page == 'phase_1':
        phase_1_page(model, go_to_project_selection, go_to_phase1_results, handle_full_regeneration, back_to_project_selection_and_cleanup)
    elif page == 'phase_1_results':
        phase_1_results_page(model, go_to_phase1, go_to_phase2, handle_full_regeneration)
    elif page == 'phase_2':
        phase_2_page(model, go_to_phase1, go_to_phase1_results, go_to_phase3)
    elif page == 'phase_3':
        phase_3_page(model, go_to_phase1, go_to_phase2, go_to_phase4)
    elif page == 'phase_4':
        phase_4_page(model, go_to_phase3, go_to_phase5)
    elif page == 'phase_5':
        phase_5_page(model, go_to_phase4, go_to_phase1, back_to_project_selection_and_cleanup)
    else:
        st.error(f"Página '{page}' no reconocida. Volviendo a la selección de proyecto.")
        go_to_project_selection()

