"""Knowledge base tools with assistant-scoped filtering."""

import hashlib
from datetime import UTC, datetime
from typing import Annotated, Any

from langchain_core.tools import tool
from langgraph.config import get_config
from langgraph.prebuilt import InjectedStore


@tool
async def search_knowledge_base(
    query: str,
    store: Annotated[Any, InjectedStore()],
) -> str:
    """Busca en la base de conocimientos específica del asistente.

    Esta herramienta permite buscar información relevante almacenada previamente
    en la base de conocimientos del asistente usando búsqueda semántica.

    Args:
        query: Consulta de búsqueda en lenguaje natural

    Returns:
        Texto con los resultados encontrados o mensaje de error
    """
    # Obtener el config de LangGraph
    config = get_config()
    
    # Intentar obtener external_assistant_id del metadata en configurable
    configurable = config.get("configurable", {})
    metadata = configurable.get("metadata", {})
    external_assistant_id = metadata.get("external_assistant_id") if isinstance(metadata, dict) else None
    
    # Si no hay external_assistant_id, usar el assistant_id local
    assistant_id = external_assistant_id or configurable.get("assistant_id")
    
    print(f"Assistant ID (local): {configurable.get('assistant_id')}")
    print(f"External Assistant ID: {external_assistant_id}")
    print(f"Using Assistant ID for namespace: {assistant_id}")

    if not assistant_id:
        return "Error: No se identificó el asistente. Verifica que el sistema esté configurado correctamente."

    # Namespace específico para este asistente
    # Estructura: ("knowledge", assistant_id)
    namespace = ("knowledge", assistant_id)

    # Búsqueda semántica usando embeddings
    # El store.asearch usa los embeddings configurados en aegra.json
    results = await store.asearch(namespace, query=query, limit=5)

    if not results:
        return "No encontré información relevante en la base de conocimientos. Puedes proporcionarme información para almacenarla usando store_knowledge."

    # Formatear resultados
    formatted_results = []
    for i, result in enumerate(results, 1):
        # Extraer el contenido del valor almacenado
        value: dict[str, Any] = result.value if isinstance(result.value, dict) else {}
        title = value.get("title", "Sin título")
        content = value.get("content", str(result.value))
        timestamp = value.get("timestamp", "")

        # Truncar contenido si es muy largo
        content_preview = content[:500] + "..." if len(content) > 500 else content

        formatted_results.append(
            f"**{i}. {title}**\n{content_preview}\n_Almacenado: {timestamp}_"
        )

    return "\n\n".join(formatted_results)


@tool
async def store_knowledge(
    content: str,
    title: str,
    store: Annotated[Any, InjectedStore()],
) -> str:
    """Almacena información en la base de conocimientos del asistente.

    Esta herramienta permite guardar información importante para uso futuro.
    Los datos se guardan con embeddings automáticos para búsqueda semántica.

    Args:
        title: Título descriptivo del conocimiento
        content: Contenido completo a almacenar

    Returns:
        Mensaje de confirmación con el ID del conocimiento almacenado
    """
    # Obtener el config de LangGraph
    config = get_config()
    configurable = config.get("configurable", {})
    
    # Intentar obtener external_assistant_id del metadata en configurable
    metadata = configurable.get("metadata", {})
    external_assistant_id = metadata.get("external_assistant_id") if isinstance(metadata, dict) else None
    
    # Si no hay external_assistant_id, usar el assistant_id local
    assistant_id = external_assistant_id or configurable.get("assistant_id")

    if not assistant_id:
        return "Error: No se identificó el asistente. No puedo almacenar el conocimiento."

    namespace = ("knowledge", assistant_id)

    # Generar un ID único para este conocimiento basado en título y contenido
    key = hashlib.md5(f"{title}_{content[:50]}".encode()).hexdigest()

    # Almacenar (los embeddings se generan automáticamente)
    # El sistema usa el modelo configurado en aegra.json (ej: openai:text-embedding-3-small)
    await store.aput(
        namespace=namespace,
        key=key,
        value={
            "title": title,
            "content": content,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )

    return f"✓ Conocimiento almacenado exitosamente:\n- Título: {title}\n- ID: {key}\n\nPuedes recuperarlo más tarde con search_knowledge_base."
