# System Prompt Priority in Dragon Chat Agent

Este documento explica cómo funciona la prioridad del system prompt en el `dragon_chat_agent` después de las modificaciones.

## Orden de Prioridad

El middleware `inject_dynamic_prompt` ahora respeta el siguiente orden de prioridad (de mayor a menor):

### 1. **System Prompt desde la Base de Datos (Máxima Prioridad)** ✅

El prompt almacenado en `assistant.config` en la base de datos tiene la **máxima prioridad**.

**Ubicación:** `config.system_prompt`

**Cuándo se usa:**
- Cuando el microservicio actualiza el assistant mediante `PUT /assistants/{assistant_id}`
- El `system_prompt` se almacena en la columna `config` de la tabla `assistants`

**Ejemplo de actualización:**

```python
# En el microservicio
PUT /assistants/dragon_chat_agent
{
  "config": {
    "system_prompt": "Eres un asistente experto en ventas. Siempre sé proactivo y amigable."
  }
}
```

Este prompt **prevalecerá** sobre cualquier otro definido en el runtime context.

### 2. **System Prompt desde Runtime Context**

Si no existe un prompt en el `config` de la base de datos, se usa el del `context`.

**Ubicación:** `context.system_prompt`

**Cuándo se usa:**
- Cuando se pasa un prompt personalizado en el request del run
- Útil para overrides temporales en casos específicos

**Ejemplo:**

```python
# En el request del run
POST /threads/{thread_id}/runs
{
  "assistant_id": "dragon_chat_agent",
  "input": {...},
  "context": {
    "system_prompt": "Override temporal del prompt"
  }
}
```

### 3. **DEFAULT_SYSTEM_PROMPT (Fallback)**

Si no existe ningún prompt en config ni en context, se usa el prompt por defecto definido en el código.

**Ubicación:** `graphs/dragon_chat_agent/prompts.py`

## Implementación

La lógica de prioridad está implementada en [graphs/dragon_chat_agent/middleware/dynamic_prompt.py:11-51](../graphs/dragon_chat_agent/middleware/dynamic_prompt.py#L11-L51):

```python
@dynamic_prompt
def inject_dynamic_prompt(request: ModelRequest) -> str:
    """Build the final system prompt from the dynamic context.

    Priority order for system prompt:
    1. system_prompt from assistant config (database) - highest priority
    2. system_prompt from runtime context
    3. DEFAULT_SYSTEM_PROMPT - fallback
    """
    ctx = getattr(request.runtime, "context", None)
    config = getattr(request.runtime, "config", {})

    # Priority 1: Check if system_prompt exists in assistant config (from DB)
    base_prompt = config.get("system_prompt") if config else None

    # Priority 2: If no config prompt, check runtime context
    if not base_prompt:
        if isinstance(ctx, DragonAgentContext):
            base_prompt = ctx.system_prompt
        elif isinstance(ctx, dict):
            base_prompt = ctx.get("system_prompt")

    # Priority 3: Fallback to default
    if not base_prompt:
        base_prompt = DEFAULT_SYSTEM_PROMPT

    # ... resto del código
```

## Flujo de Datos

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Microservicio actualiza assistant.config.system_prompt  │
│    PUT /assistants/dragon_chat_agent                        │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ 2. Base de datos (PostgreSQL)                               │
│    assistants.config = {"system_prompt": "..."}             │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ 3. Run execution: execute_run_async()                       │
│    - Lee assistant.config de la DB                          │
│    - Crea run_config con create_run_config()                │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ 4. LangGraph runtime                                         │
│    - request.runtime.config contiene assistant.config       │
│    - request.runtime.context contiene context del request   │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ 5. inject_dynamic_prompt middleware                          │
│    - Lee config.system_prompt (Prioridad 1) ✅               │
│    - Si no existe, lee context.system_prompt (Prioridad 2)  │
│    - Si no existe, usa DEFAULT_SYSTEM_PROMPT (Prioridad 3)  │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│ 6. El modelo recibe el prompt final                         │
└─────────────────────────────────────────────────────────────┘
```

## Casos de Uso

### ✅ Caso 1: Prompt Persistente desde el Microservicio

**Escenario:** El microservicio guarda un prompt personalizado en la base de datos.

**Resultado:** Ese prompt se usará en todas las conversaciones hasta que se actualice nuevamente.

```python
# 1. Actualizar prompt
PUT /assistants/dragon_chat_agent
{
  "config": {
    "system_prompt": "Eres un asistente de ventas experto. Tu objetivo es ayudar a cerrar deals."
  }
}

# 2. Crear conversación
POST /threads/thread-123/runs
{
  "assistant_id": "dragon_chat_agent",
  "input": {"messages": [{"role": "user", "content": "Hola"}]}
}

# ✅ El agente usará el prompt: "Eres un asistente de ventas experto..."
```

### ⚠️ Caso 2: Override Temporal (NO recomendado si existe config.system_prompt)

**Escenario:** Intentas pasar un prompt en el context, pero ya existe uno en la DB.

**Resultado:** El prompt de la DB prevalece. El del context es ignorado.

```python
# 1. Ya existe un prompt en la DB
# assistant.config.system_prompt = "Eres un asistente de ventas"

# 2. Intentas hacer override en el request
POST /threads/thread-123/runs
{
  "assistant_id": "dragon_chat_agent",
  "input": {...},
  "context": {
    "system_prompt": "Eres un asistente técnico"  # ❌ SERÁ IGNORADO
  }
}

# ✅ El agente usará: "Eres un asistente de ventas" (desde la DB)
```

**Solución:** Si necesitas cambiar el prompt, actualiza el assistant en la DB primero:

```python
# 1. Actualizar en la DB
PUT /assistants/dragon_chat_agent
{
  "config": {
    "system_prompt": "Eres un asistente técnico"
  }
}

# 2. Ahora todos los runs usarán el nuevo prompt
```

### ✅ Caso 3: Sin Prompt en la DB

**Escenario:** El assistant no tiene `system_prompt` en su config de la DB.

**Resultado:** Se usa el prompt del context o el default.

```python
# 1. Assistant sin system_prompt en config
# assistant.config = {}  (o no tiene system_prompt)

# 2. Crear run con context
POST /threads/thread-123/runs
{
  "assistant_id": "dragon_chat_agent",
  "input": {...},
  "context": {
    "system_prompt": "Eres un asistente técnico"  # ✅ SE USARÁ
  }
}

# ✅ El agente usará: "Eres un asistente técnico" (desde el context)
```

## Ventajas de este Approach

1. **Persistencia:** El prompt se guarda en la DB y persiste entre reinicializaciones
2. **Gestión Centralizada:** El microservicio puede actualizar el prompt sin modificar código
3. **Consistencia:** Todas las conversaciones usan el mismo prompt hasta que se actualice
4. **Trazabilidad:** Los cambios al prompt quedan registrados en la base de datos
5. **Versionamiento:** Puedes usar las versiones del assistant para trackear cambios de prompts

## Migración

Si actualmente pasas el `system_prompt` via `context` en cada request:

**Antes:**
```python
POST /threads/thread-123/runs
{
  "context": {
    "system_prompt": "Tu prompt aquí"
  }
}
```

**Después:**
```python
# 1. Guarda el prompt una sola vez en la DB
PUT /assistants/dragon_chat_agent
{
  "config": {
    "system_prompt": "Tu prompt aquí"
  }
}

# 2. Ya no necesitas pasarlo en cada request
POST /threads/thread-123/runs
{
  "input": {...}
  # ✅ No necesitas context.system_prompt
}
```

## Testing

Para verificar que el prompt correcto está siendo usado:

```python
# Test 1: Config prevalece sobre context
assistant.config = {"system_prompt": "DB Prompt"}
run = create_run(context={"system_prompt": "Context Prompt"})
assert "DB Prompt" in final_prompt  # ✅

# Test 2: Context se usa si no hay config
assistant.config = {}
run = create_run(context={"system_prompt": "Context Prompt"})
assert "Context Prompt" in final_prompt  # ✅

# Test 3: Default se usa si no hay ninguno
assistant.config = {}
run = create_run()
assert DEFAULT_SYSTEM_PROMPT in final_prompt  # ✅
```

## Resumen

- **🥇 Prioridad 1:** `assistant.config.system_prompt` (Base de datos)
- **🥈 Prioridad 2:** `context.system_prompt` (Runtime context)
- **🥉 Prioridad 3:** `DEFAULT_SYSTEM_PROMPT` (Código)

**Recomendación:** Usa siempre `assistant.config.system_prompt` para prompts persistentes y gestionados desde el microservicio.
