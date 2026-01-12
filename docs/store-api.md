# Store API Documentation

Documentación completa de los endpoints de STORE para consumo desde el backend.

## Base URL

Todos los endpoints están bajo: `http://localhost:8000` (o la URL de tu servidor)

## Autenticación

Todos los endpoints requieren autenticación. Incluye el header de autenticación en cada request:

```
Authorization: Bearer <token>
```

## Almacenamiento de Embeddings

**¡Importante!** Cuando el store está configurado con embeddings (ver configuración abajo), el sistema **automáticamente genera y guarda embeddings** de los items cuando los almacenas con `PUT /store/items`.

### ¿Cómo funciona?

1. **Almacenamiento automático**: Cuando guardas un item con `PUT /store/items`, el sistema:
   - Guarda el valor original en la base de datos
   - Genera automáticamente embeddings usando el modelo configurado
   - Almacena los embeddings en PostgreSQL con pgvector
   - Todo esto sucede automáticamente, no necesitas hacer nada adicional

2. **Búsqueda semántica**: Los embeddings permiten búsqueda semántica en `POST /store/items/search`:
   - Puedes buscar por significado, no solo por palabras exactas
   - El sistema encuentra items similares semánticamente

### Configuración de Embeddings

Para habilitar embeddings, agrega esto a tu `aegra.json`:

```json
{
  "store": {
    "index": {
      "dims": 1536,
      "embed": "openai:text-embedding-3-small",
      "fields": ["$"]
    }
  }
}
```

**Opciones:**
- `dims`: Dimensiones del vector (1536 para text-embedding-3-small, 3072 para text-embedding-3-large)
- `embed`: Modelo en formato `provider:model-id` (ej: `openai:text-embedding-3-small`)
- `fields`: Campos del JSON a embedear (default `["$"]` para todo el documento)

**Modelos soportados:**
- OpenAI: `openai:text-embedding-3-small` (1536 dims), `openai:text-embedding-3-large` (3072 dims)
- AWS Bedrock: `bedrock:amazon.titan-embed-text-v2:0` (1024 dims)
- Cohere: `cohere:embed-english-v3.0` (1024 dims)

**Variables de entorno requeridas:**
```bash
# Para OpenAI
OPENAI_API_KEY=sk-...

# Para AWS Bedrock
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...

# Para Cohere
COHERE_API_KEY=...
```

**Nota**: Si no configuras embeddings, el store funciona en modo key-value básico (sin búsqueda semántica).

## Endpoints

### 1. PUT `/store/items` - Almacenar un item

Almacena un item en el store de LangGraph.

**Request:**
```http
PUT /store/items
Content-Type: application/json
Authorization: Bearer <token>

{
  "namespace": ["notes"],
  "key": "item-1",
  "value": {
    "title": "Mi nota",
    "content": "Contenido de la nota",
    "tags": ["importante", "personal"]
  }
}
```

**Request Body Schema:**
```json
{
  "namespace": ["string"],  // Array de strings que define el namespace
  "key": "string",          // Clave única del item
  "value": {}               // Valor del item (puede ser cualquier tipo JSON)
}
```

**Nota sobre Embeddings:**
Si el store está configurado con embeddings, el sistema **automáticamente genera y guarda embeddings** del `value` cuando almacenas el item. No necesitas hacer nada adicional - los embeddings se crean automáticamente en el backend.

**Response:**
```json
{
  "status": "stored"
}
```

**Status Codes:**
- `200 OK`: Item almacenado exitosamente
- `401 Unauthorized`: Token de autenticación inválido o faltante
- `422 Unprocessable Entity`: Datos de request inválidos

**Ejemplo con cURL:**
```bash
curl -X PUT http://localhost:8000/store/items \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "namespace": ["notes"],
    "key": "item-1",
    "value": {
      "title": "Mi nota",
      "content": "Contenido de la nota"
    }
  }'
```

---

### 2. GET `/store/items` - Obtener un item

Obtiene un item del store por su namespace y key.

**Request:**
```http
GET /store/items?key=item-1&namespace=notes
Authorization: Bearer <token>
```

**Query Parameters:**
- `key` (required): Clave del item a obtener
- `namespace` (optional): Namespace como string con puntos (ej: `"notes"` o `"user.123.preferences"`) o como array en query params

**Ejemplos de namespace:**
- String con puntos: `?namespace=notes` o `?namespace=user.123.preferences`
- Array en query params: `?namespace[]=notes` o `?namespace[]=user&namespace[]=123`

**Response:**
```json
{
  "key": "item-1",
  "value": {
    "title": "Mi nota",
    "content": "Contenido de la nota",
    "tags": ["importante", "personal"]
  },
  "namespace": ["users", "user-id", "notes"]
}
```

**Response Schema:**
```json
{
  "key": "string",
  "value": {},              // Valor almacenado (cualquier tipo JSON)
  "namespace": ["string"]   // Namespace completo (incluye scoping de usuario)
}
```

**Status Codes:**
- `200 OK`: Item encontrado
- `404 Not Found`: Item no encontrado
- `401 Unauthorized`: Token de autenticación inválido o faltante

**Ejemplo con cURL:**
```bash
# Con namespace como string
curl -X GET "http://localhost:8000/store/items?key=item-1&namespace=notes" \
  -H "Authorization: Bearer <token>"

# Con namespace como array
curl -X GET "http://localhost:8000/store/items?key=item-1&namespace[]=notes" \
  -H "Authorization: Bearer <token>"
```

---

### 3. DELETE `/store/items` - Eliminar un item

Elimina un item del store.

**Request (con JSON body - recomendado):**
```http
DELETE /store/items
Content-Type: application/json
Authorization: Bearer <token>

{
  "namespace": ["notes"],
  "key": "item-1"
}
```

**Request (con query parameters - alternativa):**
```http
DELETE /store/items?key=item-1&namespace[]=notes
Authorization: Bearer <token>
```

**Request Body Schema (opcional):**
```json
{
  "namespace": ["string"],
  "key": "string"
}
```

**Query Parameters (alternativa):**
- `key` (required si no se envía en body): Clave del item a eliminar
- `namespace` (optional): Array de strings del namespace

**Response:**
```json
{
  "status": "deleted"
}
```

**Status Codes:**
- `200 OK`: Item eliminado exitosamente
- `401 Unauthorized`: Token de autenticación inválido o faltante
- `422 Unprocessable Entity`: Falta el parámetro 'key'

**Ejemplo con cURL:**
```bash
# Con JSON body
curl -X DELETE http://localhost:8000/store/items \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "namespace": ["notes"],
    "key": "item-1"
  }'

# Con query parameters
curl -X DELETE "http://localhost:8000/store/items?key=item-1&namespace[]=notes" \
  -H "Authorization: Bearer <token>"
```

---

### 4. POST `/store/items/search` - Buscar items

Busca items en el store por namespace prefix y query opcional.

**Request:**
```http
POST /store/items/search
Content-Type: application/json
Authorization: Bearer <token>

{
  "namespace_prefix": ["notes"],
  "query": "nota importante",
  "limit": 20,
  "offset": 0
}
```

**Request Body Schema:**
```json
{
  "namespace_prefix": ["string"],  // Prefix del namespace para buscar
  "query": "string",                // Query de búsqueda (opcional, para semantic search)
  "limit": 20,                      // Máximo de resultados (opcional, default: 20, max: 100)
  "offset": 0                       // Offset para paginación (opcional, default: 0)
}
```

**Response:**
```json
{
  "items": [
    {
      "key": "item-1",
      "value": {
        "title": "Mi nota",
        "content": "Contenido de la nota"
      },
      "namespace": ["users", "user-id", "notes"]
    },
    {
      "key": "item-2",
      "value": {
        "title": "Otra nota",
        "content": "Más contenido"
      },
      "namespace": ["users", "user-id", "notes"]
    }
  ],
  "total": 2,
  "limit": 20,
  "offset": 0
}
```

**Response Schema:**
```json
{
  "items": [
    {
      "key": "string",
      "value": {},
      "namespace": ["string"]
    }
  ],
  "total": 0,      // Número total de items encontrados
  "limit": 20,     // Límite aplicado
  "offset": 0      // Offset aplicado
}
```

**Status Codes:**
- `200 OK`: Búsqueda exitosa
- `401 Unauthorized`: Token de autenticación inválido o faltante
- `422 Unprocessable Entity`: Datos de request inválidos

**Ejemplo con cURL:**
```bash
curl -X POST http://localhost:8000/store/items/search \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "namespace_prefix": ["notes"],
    "query": "nota importante",
    "limit": 10,
    "offset": 0
  }'
```

---

## Namespace Scoping

El sistema aplica automáticamente un namespace de usuario para aislar datos:

- **Si no especificas namespace**: Se usa automáticamente `["users", "<user-id>"]`
- **Si especificas namespace**: Se puede usar cualquier namespace, pero el sistema puede aplicar scoping según la configuración

**Ejemplo:**
- Request: `namespace: ["notes"]`
- Namespace real almacenado: `["users", "user-123", "notes"]` (donde `user-123` es el ID del usuario autenticado)

---

## Ejemplos de Uso Completos

### JavaScript/TypeScript (fetch)

```javascript
const BASE_URL = 'http://localhost:8000';
const TOKEN = 'your-auth-token';

// Almacenar un item
async function storeItem(namespace, key, value) {
  const response = await fetch(`${BASE_URL}/store/items`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${TOKEN}`
    },
    body: JSON.stringify({
      namespace,
      key,
      value
    })
  });
  return await response.json();
}

// Obtener un item
async function getItem(key, namespace) {
  const namespaceStr = Array.isArray(namespace) ? namespace.join('.') : namespace;
  const response = await fetch(
    `${BASE_URL}/store/items?key=${key}&namespace=${namespaceStr}`,
    {
      headers: {
        'Authorization': `Bearer ${TOKEN}`
      }
    }
  );
  if (response.status === 404) {
    throw new Error('Item not found');
  }
  return await response.json();
}

// Buscar items
async function searchItems(namespacePrefix, query, limit = 20, offset = 0) {
  const response = await fetch(`${BASE_URL}/store/items/search`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${TOKEN}`
    },
    body: JSON.stringify({
      namespace_prefix: namespacePrefix,
      query,
      limit,
      offset
    })
  });
  return await response.json();
}

// Eliminar un item
async function deleteItem(namespace, key) {
  const response = await fetch(`${BASE_URL}/store/items`, {
    method: 'DELETE',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${TOKEN}`
    },
    body: JSON.stringify({
      namespace,
      key
    })
  });
  return await response.json();
}

// Uso
(async () => {
  // Almacenar
  await storeItem(['notes'], 'note-1', {
    title: 'Mi primera nota',
    content: 'Contenido de la nota'
  });

  // Obtener
  const item = await getItem('note-1', 'notes');
  console.log(item);

  // Buscar
  const results = await searchItems(['notes'], 'primera', 10);
  console.log(results);

  // Eliminar
  await deleteItem(['notes'], 'note-1');
})();
```

### Python (requests)

```python
import requests

BASE_URL = 'http://localhost:8000'
TOKEN = 'your-auth-token'

headers = {
    'Authorization': f'Bearer {TOKEN}',
    'Content-Type': 'application/json'
}

# Almacenar un item
def store_item(namespace, key, value):
    response = requests.put(
        f'{BASE_URL}/store/items',
        headers=headers,
        json={
            'namespace': namespace,
            'key': key,
            'value': value
        }
    )
    return response.json()

# Obtener un item
def get_item(key, namespace):
    namespace_str = '.'.join(namespace) if isinstance(namespace, list) else namespace
    response = requests.get(
        f'{BASE_URL}/store/items',
        headers={'Authorization': f'Bearer {TOKEN}'},
        params={'key': key, 'namespace': namespace_str}
    )
    if response.status_code == 404:
        raise Exception('Item not found')
    return response.json()

# Buscar items
def search_items(namespace_prefix, query=None, limit=20, offset=0):
    response = requests.post(
        f'{BASE_URL}/store/items/search',
        headers=headers,
        json={
            'namespace_prefix': namespace_prefix,
            'query': query,
            'limit': limit,
            'offset': offset
        }
    )
    return response.json()

# Eliminar un item
def delete_item(namespace, key):
    response = requests.delete(
        f'{BASE_URL}/store/items',
        headers=headers,
        json={
            'namespace': namespace,
            'key': key
        }
    )
    return response.json()

# Uso
if __name__ == '__main__':
    # Almacenar
    store_item(['notes'], 'note-1', {
        'title': 'Mi primera nota',
        'content': 'Contenido de la nota'
    })
    
    # Obtener
    item = get_item('note-1', ['notes'])
    print(item)
    
    # Buscar
    results = search_items(['notes'], query='primera', limit=10)
    print(results)
    
    # Eliminar
    delete_item(['notes'], 'note-1')
```

---

## Semantic Search (Búsqueda Semántica)

Si el store está configurado con embeddings, puedes usar búsqueda semántica en el endpoint `POST /store/items/search`:

```json
{
  "namespace_prefix": ["notes"],
  "query": "How does this user like to write code?",
  "limit": 5
}
```

**¿Cómo funciona la búsqueda semántica?**

1. **Embeddings automáticos**: Cuando guardas items con `PUT /store/items`, el sistema automáticamente genera embeddings y los almacena
2. **Búsqueda por significado**: Cuando haces `POST /store/items/search` con un `query`, el sistema:
   - Genera un embedding del query
   - Busca items cuyos embeddings sean similares (usando distancia coseno en pgvector)
   - Retorna los items más relevantes semánticamente

**Ejemplo práctico:**

```javascript
// 1. Guardar un item (los embeddings se generan automáticamente)
await storeItem(['preferences'], 'coding-style', {
  text: "I prefer clean code with descriptive variable names"
});

// 2. Buscar semánticamente (encuentra items por significado, no palabras exactas)
const results = await searchItems(['preferences'], 
  "How does this user like to write code?",  // Query en lenguaje natural
  5
);
// Retorna el item 'coding-style' aunque no contenga las palabras exactas del query
```

**Ventajas:**
- Encuentra items relevantes aunque no contengan las palabras exactas del query
- Funciona con sinónimos y conceptos relacionados
- Ideal para RAG, memoria conversacional, y personalización

**Requisitos:**
- Store configurado con embeddings en `aegra.json`
- PostgreSQL con extensión pgvector
- API key del proveedor de embeddings configurada

---

## Errores Comunes

### 404 Not Found en GET
- Verifica que el `key` y `namespace` sean correctos
- El item puede haber sido eliminado

### 422 Unprocessable Entity
- Verifica que todos los campos requeridos estén presentes
- Verifica que los tipos de datos sean correctos (namespace debe ser array)

### 401 Unauthorized
- Verifica que el token de autenticación sea válido
- Verifica que el header `Authorization` esté presente

---

## Notas Importantes

1. **Autenticación requerida**: Todos los endpoints requieren autenticación
2. **Namespace scoping**: Los namespaces se scopean automáticamente al usuario
3. **Valores flexibles**: El campo `value` puede ser cualquier tipo JSON válido
4. **Búsqueda semántica**: Requiere configuración adicional (ver `docs/semantic-store.md`)
5. **Límites**: El límite máximo para búsquedas es 100 items por request
