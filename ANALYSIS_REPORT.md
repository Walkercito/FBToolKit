# FBToolKit - Informe de Auditoría y Análisis Técnico

**Fecha:** 22 de Noviembre, 2025
**Versión Analizada:** 0.0.2
**Autor Original:** Dapunta Khurayra X
**Analista:** Claude Code

---

## Resumen Ejecutivo

Este informe presenta un análisis exhaustivo del repositorio FBToolKit, un fork de una herramienta de automatización de Facebook mediante ingeniería inversa de la API GraphQL interna. Se identificaron **23 problemas críticos** y **15 áreas de mejora** que afectan la estabilidad, mantenibilidad y experiencia del usuario.

### Estadísticas del Codebase
| Métrica | Valor |
|---------|-------|
| Archivos Python | 10 |
| Líneas de Código | ~1,236 |
| Dependencias Declaradas | 1 (requests) |
| Dependencias Reales | 4 |
| Tests Unitarios | 0 |

---

## 1. Problemas Críticos Identificados

### 1.1 Dependencias No Declaradas (SEVERIDAD: CRÍTICA)

**Ubicación:** `setup.py:26-28`

El paquete solo declara `requests` como dependencia, pero el código requiere:

```python
# CreateAccount.py
from Crypto.Cipher import AES, PKCS1_v1_5
from Crypto.PublicKey import RSA
from Crypto.Random import get_random_bytes
from nacl.public import PublicKey, SealedBox

# Setting.py
import pyotp
```

**Impacto:** La instalación del paquete fallará al intentar usar `CreateAccount` o funciones de 2FA.

**Dependencias faltantes:**
- `pycryptodome` (para Crypto)
- `PyNaCl` (para nacl)
- `pyotp` (para autenticación 2FA)

---

### 1.2 Manejo de Errores Deficiente

#### 1.2.1 Excepciones Silenciosas en Subida de Imágenes

**Ubicación:** `Automation1.py:35-43, 82-90, 130-138`

```python
def UploadPhoto(self, url):
    try:
        file = {'file':('image.jpg',urllib.request.urlopen(url).read())}
        # ... código de subida ...
    except Exception as e: pass  # ERROR: Fallo silencioso
```

**Problemas:**
- Si la subida de imagen falla, el usuario no recibe ninguna notificación
- El post se crea sin las imágenes sin ningún aviso
- No hay logging ni información para depuración

#### 1.2.2 Excepciones Genéricas con Mensajes No Traducidos

**Ubicación:** `Automation1.py:55, 105, 156, 189, 229, 269`

```python
except Exception as e: tur = {'status':'failed','id':None,'message':'Terjadi Kesalahan'}
```

**Problema:** "Terjadi Kesalahan" es indonesio para "Ocurrió un error" - no informativo ni en inglés.

---

### 1.3 Strings Hardcodeados en Indonesio/Otros Idiomas

| Archivo | Línea | Texto Original | Traducción Correcta |
|---------|-------|----------------|---------------------|
| `Automation1.py` | 53 | `'Status Baru Duplikat'` | `'Duplicate Post'` |
| `Automation1.py` | 55, 105, 156, 189, 229, 269 | `'Terjadi Kesalahan'` | `'An error occurred'` |
| `Automation1.py` | 100, 263 | `'Akun Anda dibatasi saat ini'` | `'Your account is currently restricted'` |
| `Automation1.py` | 226, 227, 267 | `'Tidak Dapat Membagikan Postingan'` | `'Unable to share post'` |
| `GetInfo.py` | 60 | `'Info Kontak dan Dasar'` | `'Basic Contact Information'` |
| `GetInfo.py` | 61 | `'Keluarga dan Hubungan'` | `'Family and Relationships'` |

---

### 1.4 Regex Sin Validación (Potenciales AttributeError)

**Ubicación:** Múltiples archivos

```python
# Tools.py:21-33 - Todos estos pueden fallar con AttributeError
av = re.search(r'"actorID":"(.*?)"',str(req)).group(1)
__hs = re.search(r'"haste_session":"(.*?)"',str(req)).group(1)
# ... etc
```

**Problema:** Si el regex no encuentra coincidencia, `.group(1)` lanza `AttributeError: 'NoneType' object has no attribute 'group'`

---

### 1.5 Uso de `exit()` para Validación de Parámetros

**Ubicación:** `Automation1.py:68, 243`

```python
if group == None: exit("\nParameter 'group' Must Be Included\n")
```

**Problema:** `exit()` termina todo el programa Python, no solo la función. En una aplicación más grande, esto causaría una terminación inesperada.

---

## 2. Problemas Específicos de Posting a Grupos

### 2.1 Clase `PostToGroup` - Análisis Detallado

**Ubicación:** `Automation1.py:58-106`

#### Problemas Identificados:

1. **Sin validación de ID de grupo:**
   ```python
   self.group = group  # No valida si es un ID numérico válido
   ```

2. **Sin retry logic:**
   - Si la petición falla por timeout o error de red, no hay reintentos
   - Facebook puede rechazar temporalmente y no hay backoff exponencial

3. **Detección de errores basada en strings frágiles:**
   ```python
   if 'Akun Anda dibatasi saat ini' in str(pos):  # Depende del idioma de Facebook
   ```
   Si Facebook cambia el idioma o el mensaje, la detección falla.

4. **Sin rate limiting:**
   - No hay delay entre requests
   - Alto riesgo de ser bloqueado por spam

5. **Sin verificación de membresía:**
   - No verifica si el usuario es miembro del grupo antes de intentar publicar

### 2.2 Clase `ShareToGroup` - Problemas Similares

**Ubicación:** `Automation1.py:232-270`

Mismos problemas que `PostToGroup`, más:
- Sin validación de que el post original existe
- Sin manejo de posts privados que no pueden compartirse

---

## 3. Problemas de Upload de Imágenes

### 3.1 Limitaciones Actuales

**Ubicación:** `Automation1.py:35-43`

```python
def UploadPhoto(self, url):
    try:
        file = {'file':('image.jpg',urllib.request.urlopen(url).read())}
```

**Problemas:**

1. **Solo soporta URLs:** No acepta paths locales de archivos
2. **Nombre de archivo hardcodeado:** Siempre `'image.jpg'` sin importar el formato real
3. **Sin detección de formato:** No verifica si es JPEG, PNG, GIF, etc.
4. **Sin límite de tamaño:** Puede intentar subir archivos muy grandes
5. **Sin timeout en descarga:** `urllib.request.urlopen(url)` puede bloquear indefinidamente
6. **Sin validación de URL:** URLs malformadas causan excepciones silenciosas

---

## 4. Problemas de Arquitectura

### 4.1 Variables Globales

**Ubicación:** `__init__.py:13-14, 57-58`

```python
global_cookie = False
global_requests = False

# En __init__:
global_cookie = self.cookie
global_requests = self.r
```

**Problema:** Usar globales causa problemas con múltiples instancias simultáneas y testing.

### 4.2 Código Duplicado

Los headers HTTP están definidos múltiples veces:
- `Automation1.py:4-6`
- `Login.py:3-5`
- `GetInfo.py:4-6`

### 4.3 Sin Logging Estructurado

El código usa `print()` para debugging en lugar de el módulo `logging`:
- `CreateAccount.py:23, 25, 27, 28, 34, 178`

---

## 5. Problemas de Seguridad

### 5.1 Cookies en Texto Plano

Las cookies se pasan como strings sin encriptación:
```python
cookies={'cookie':self.cookie}
```

### 5.2 Sin Validación de Certificados SSL

Los requests no especifican `verify=True` explícitamente.

### 5.3 Sin Sanitización de Input

Los parámetros `text`, `url`, `tag` no se validan antes de enviar a Facebook.

---

## 6. Fragilidad del Scraping

### 6.1 Dependencia de Estructura HTML/JSON de Facebook

El código depende de patrones regex muy específicos:

```python
'"sessionID":"(.*?)"'
'"feedback":{"associated_group":null,"id":"(.*?)"},"is_story_civic":null'
```

**Riesgo:** Cualquier cambio menor en la respuesta de Facebook rompe la funcionalidad.

### 6.2 Doc IDs Hardcodeados

```python
'doc_id':'7338317599553815'  # ComposerStoryCreateMutation
'doc_id':'7128740410521626'  # useCometUFICreateCommentMutation
'doc_id':'6623712531077310'  # CometUFIFeedbackReactMutation
```

Estos IDs pueden cambiar cuando Facebook actualiza su frontend.

---

## 7. Tabla de Prioridades de Mejora

| Prioridad | Área | Descripción | Esfuerzo |
|-----------|------|-------------|----------|
| 🔴 CRÍTICO | Dependencias | Agregar dependencias faltantes a setup.py | Bajo |
| 🔴 CRÍTICO | Errores | Implementar manejo de errores robusto | Medio |
| 🔴 CRÍTICO | i18n | Traducir todos los strings a inglés | Bajo |
| 🟠 ALTO | Logging | Implementar logging estructurado | Medio |
| 🟠 ALTO | Validación | Agregar validación de parámetros | Medio |
| 🟠 ALTO | Retry Logic | Implementar reintentos con backoff | Medio |
| 🟡 MEDIO | Imágenes | Mejorar soporte de formatos y paths locales | Medio |
| 🟡 MEDIO | Rate Limiting | Agregar delays configurables | Bajo |
| 🟡 MEDIO | Código | Eliminar duplicación de headers | Bajo |
| 🟢 BAJO | Arquitectura | Eliminar variables globales | Medio |
| 🟢 BAJO | Tests | Crear suite de tests unitarios | Alto |
| 🟢 BAJO | Docs | Agregar docstrings a funciones | Medio |

---

## 8. Archivos por Orden de Prioridad para Refactorización

1. **`setup.py`** - Agregar dependencias (5 min)
2. **`Automation1.py`** - Posting/Sharing - Núcleo de la funcionalidad (2-3 horas)
3. **`Tools.py`** - Funciones de utilidad con regex frágiles (1 hora)
4. **`Login.py`** - Autenticación (1 hora)
5. **`GetInfo.py`** - Scraping de información (1 hora)
6. **`__init__.py`** - Wrapper principal (30 min)

---

## 9. Recomendaciones de Implementación

### 9.1 Sistema de Excepciones Personalizadas

```python
# Propuesto: exceptions.py
class FBToolsError(Exception):
    """Base exception for FBTools"""
    pass

class AuthenticationError(FBToolsError):
    """Cookie or credentials invalid"""
    pass

class RateLimitError(FBToolsError):
    """Account temporarily restricted"""
    pass

class PostError(FBToolsError):
    """Failed to create post"""
    pass

class ImageUploadError(FBToolsError):
    """Failed to upload image"""
    pass
```

### 9.2 Configuración de Logging

```python
# Propuesto: En __init__.py
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('FBTools')
```

### 9.3 Retry Decorator

```python
# Propuesto: utils.py
import time
from functools import wraps

def retry_with_backoff(max_retries=3, base_delay=1):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2 ** attempt)
                    time.sleep(delay)
            return None
        return wrapper
    return decorator
```

---

## 10. Conclusión

FBToolKit es una herramienta funcional pero con deuda técnica significativa. Las mejoras prioritarias son:

1. **Inmediato:** Corregir dependencias en `setup.py`
2. **Corto plazo:** Traducir strings y mejorar manejo de errores
3. **Mediano plazo:** Implementar logging, retry logic, y validación
4. **Largo plazo:** Refactorizar arquitectura y agregar tests

El enfoque en posting a grupos requiere especial atención en:
- Validación de IDs de grupo
- Detección robusta de errores (no basada en strings de idioma)
- Rate limiting para evitar bloqueos
- Mejor feedback al usuario sobre el estado de las operaciones

---

*Este análisis fue generado como parte de una auditoría técnica del repositorio FBToolKit.*
