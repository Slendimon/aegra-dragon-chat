"""Utilities for building user context sections for prompts."""

from typing import Dict, Any

from graphs.dragon_chat_agent.utils.datetime_utils import get_current_zulu_datetime


def build_user_context_section(metadata: Dict[str, Any]) -> str:
    """
    Build a user context section from metadata.
    
    Args:
        metadata: Dictionary containing user metadata (e.g., whatsapp_contact_name, 
                  whatsapp_contact_number, etc.)
    
    Returns:
        Formatted string with user context information, or empty string if no metadata
    """
    if not metadata:
        return ""
    
    context_parts = []
    
    # Extract WhatsApp contact information
    contact_name = metadata.get("whatsapp_contact_name")
    contact_number = metadata.get("whatsapp_contact_number")
    
    if contact_name or contact_number:
        user_info = []
        if contact_name:
            user_info.append(f"Nombre: {contact_name}")
        if contact_number:
            user_info.append(f"Número de contacto: {contact_number}")
        
        if user_info:
            context_parts.append("## Datos del usuario:")
            context_parts.extend(f"  - {info}" for info in user_info)
    
    # Add any other metadata fields
    other_metadata = {
        k: v for k, v in metadata.items()
        if k not in ("whatsapp_contact_name", "whatsapp_contact_number")
    }
    
    if other_metadata:
        context_parts.append("## Información adicional:")
        for key, value in other_metadata.items():
            context_parts.append(f"  - {key}: {value}")
    
    if context_parts:
        return "\n\n" + "\n".join(context_parts) + "\n"
    
    return ""


def build_datetime_context_section(current_datetime: str | None = None) -> str:
    """
    Build a datetime context section with current Zulu time.

    Returns:
        Formatted string with current date and time information
    """
    if not current_datetime:
        current_datetime = get_current_zulu_datetime()
    return f"\n\n## Información de contexto:\n- Fecha y hora actual: {current_datetime}\n"


def build_knowledge_base_instructions(has_knowledge_base: bool = False) -> str:
    """
    Build instructions for using the knowledge base.

    Args:
        has_knowledge_base: Whether the assistant has documents in its knowledge base

    Returns:
        Formatted string with knowledge base usage instructions, or empty if no KB
    """
    if not has_knowledge_base:
        return ""

    return """

## Instrucciones de Base de Conocimientos
IMPORTANTE: Tienes acceso a una base de conocimientos específica mediante la herramienta `search_knowledge_base`.
- SIEMPRE busca en la base de conocimientos PRIMERO cuando el usuario haga preguntas sobre productos, servicios, políticas, procedimientos, o cualquier información que pueda estar documentada.
- Usa el resultado de la búsqueda como FUENTE PRINCIPAL de tu respuesta.
- Si la búsqueda retorna resultados relevantes, DEBES basar tu respuesta en esa información.
- Solo responde con conocimiento general si la búsqueda no encuentra información relevante.
"""

