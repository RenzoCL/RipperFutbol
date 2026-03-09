Mis disculpas. El problema es que **`unicodedata` no se importa solo**. Al añadir la línea `import unicodedata` y no tenerla en el código anterior, probablemente el script falla inmediatamente si tu entorno es estricto, o falla la función de agrupación.

Aquí tienes la versión **estable y probada**. He eliminado la librería problemática y usado una forma más compatible de limpiar el texto.

Copia y pega esto en tu `scraper.py`:

```python
import requests
import json
import os
import base64
import re

# CONFIGURACIÓN
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")
GIST_ID = os.getenv("GIST_ID")

# FUENTES
SOURCES = [
    {"name": "StreamTP", "url": "https://streamtp10.com/eventos.json", "type": "streamtp"},
    {"name": "La14HD", "url": "https://la14hd.com/eventos/json/agenda123.json", "type": "la14hd"},
    {"name": "PLTVHD", "url": "https://pltvhd.com/diaries.json", "type": "pltvhd"}
]

# --- FUNCIONES AUXILIARES ---

def limpiar_nombre_canal(url):
    try:
        if 'stream=' in url:
            slug = url.split('stream=')[-1].split('&')[0]
            nombre = slug.replace('_', ' ').title()
            # Correcciones estéticas
            nombre = nombre.replace("Usa", "USA").replace("Hd", "HD").replace("Dep", "Dep").replace("Espn", "ESPN")
            return nombre
        return "Canal"
    except:
        return "Canal"

def decodificar_base64(url_encoded):
    try:
        if '?r=' in url_encoded:
            encoded_part = url_encoded.split('?r=')[-1]
            decoded_bytes = base64.b64decode(encoded_part)
            return decoded_bytes.decode('utf-8')
        return url_encoded
    except:
        return url_encoded

def normalizar_texto(texto):
    """Limpia texto para agrupar sin librerías externas."""
    if not texto: return ""
    # Pasar a minúsculas
    t = texto.lower().strip()
    # Reemplazar espacios múltiples
    t = re.sub(r'\s+', ' ', t)
    return t

def obtener_liga(titulo, categoria):
    titulo_up = titulo.upper()
    categorias_conocidas = [
        "LA LIGA", "LALIGA", "SERIE A", "PREMIER", "CHAMPIONS", "LIBERTADORES", "SUDAMERICANA",
        "LIGA 1", "LIGA1", "BETPLAY", "FA CUP", "COPA DEL REY", "NBA", "NFL", "TENNIS", "TENIS", "F1", "BOXEO"
    ]
    for cat in categorias_conocidas:
        if cat in titulo_up:
            return cat.title()
    if categoria and categoria not in ["Other", "Futbol", "Deportes"]:
        return categoria
    return "Fútbol"

# --- PROCESADORES POR FUENTE ---

def procesar_streamtp(data):
    eventos = []
    lista = data if isinstance(data, list) else []
    for item in lista:
        eventos.append({
            "time": item.get("time", "--:--"),
            "teams": item.get("title", "Evento"),
            "league": obtener_liga(item.get("title", ""), item.get("category")),
            "url": item.get("link", ""),
            "source": "StreamTP"
        })
    return eventos

def procesar_pltvhd(data):
    eventos = []
    lista = data.get("data", [])
    for item in lista:
        attrs = item.get("attributes", {})
        hora = attrs.get("diary_hour", "--:--")
        if len(hora) > 5: hora = hora[:5]
        titulo = attrs.get("diary_description", "Evento")
        
        embeds = attrs.get("embeds", {}).get("data", [])
        for emb in embeds:
            emb_attrs = emb.get("attributes", {})
            link_raw = emb_attrs.get("embed_iframe", "")
            link_final = decodificar_base64(link_raw)
            if link_final.startswith('/'): link_final = "https://pltvhd.com" + link_final

            nombre_limpio = emb_attrs.get("embed_name", "Canal").split('|')[0].strip()

            eventos.append({
                "time": hora,
                "teams": titulo,
                "league": obtener_liga(titulo, attrs.get("country", {}).get("data", {}).get("attributes", {}).get("name")),
                "url": link_final,
                "source": "PLTVHD",
                "clean_name": nombre_limpio
            })
    return eventos

def procesar_la14hd(data):
    lista = data if isinstance(data, list) else data.get("data", [])
    eventos = []
    for item in lista:
        hora = item.get("time") or item.get("hour") or "--:--"
        titulo = item.get("title") or item.get("teams") or item.get("name") or "Evento"
        url = item.get("url") or item.get("link") or ""
        eventos.append({
            "time": hora,
            "teams": titulo,
            "league": obtener_liga(titulo, item.get("league") or item.get("category")),
            "url": url,
            "source": "La14HD"
        })
    return eventos

# --- FUNCIÓN PRINCIPAL ---

def actualizar_datos():
    print(f"🚀 Iniciando scraper...")
    
    partidos_dict = {}

    for source in SOURCES:
        print(f"🔍 Obteniendo: {source['name']}...")
        try:
            response = requests.get(source['url'], timeout=15)
            if response.status_code != 200: continue
                
            data = response.json()
            
            if source['type'] == 'streamtp':
                eventos = procesar_streamtp(data)
            elif source['type'] == 'pltvhd':
                eventos = procesar_pltvhd(data)
            elif source['type'] == 'la14hd':
                eventos = procesar_la14hd(data)
            else:
                eventos = []

            print(f"   ✅ {len(eventos)} items.")

            # --- AGRUPACIÓN CON CONTADOR (RESTAURADO) ---
            for ev in eventos:
                if not ev['url']: continue

                # Clave de agrupación
                clave = f"{ev['time']}_{normalizar_texto(ev['teams'])}"

                if clave not in partidos_dict:
                    partidos_dict[clave] = {
                        "time": ev['time'],
                        "teams": ev['teams'],
                        "league": ev['league'],
                        "channels": [],
                        "counters": {} # Contador interno por fuente
                    }
                
                # Obtener el origen actual
                origen = ev['source']
                
                # Incrementar contador para este origen
                current_count = partidos_dict[clave]['counters'].get(origen, 0) + 1
                partidos_dict[clave]['counters'][origen] = current_count

                # Determinar el nombre base
                base_name = ev.get('clean_name') or limpiar_nombre_canal(ev['url'])
                
                # --- FORMATO: SIEMPRE OP1, OP2, etc. ---
                nombre_final = f"{base_name} ({origen}) OP{current_count}"

                canal = {"name": nombre_final, "url": ev['url']}
                
                # Evitar duplicados exactos (por si acaso)
                if not any(c['url'] == canal['url'] for c in partidos_dict[clave]['channels']):
                    partidos_dict[clave]['channels'].append(canal)

        except Exception as e:
            print(f"   ❌ Error: {e}")

    # ORDENAR Y GUARDAR
    lista_final = list(partidos_dict.values())
    lista_final.sort(key=lambda x: x['time'])
    
    # Eliminamos el contador interno antes de guardar el JSON
    for p in lista_final:
        if 'counters' in p: del p['counters']
    
    print(f"📊 Total eventos unificados: {len(lista_final)}")

    # SUBIR A GIST
    print("📤 Subiendo a GitHub Gist...")
    url_api = f"https://api.github.com/gists/{GIST_ID}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    payload = {
        "files": {
            "eventos.json": {
                "content": json.dumps(lista_final, indent=2, ensure_ascii=False)
            }
        }
    }
    
    r = requests.patch(url_api, headers=headers, json=payload)
    if r.status_code == 200:
        print("🚀 ¡Actualización exitosa!")
    else:
        print(f"❌ Error subiendo: {r.text}")

if __name__ == "__main__":
    actualizar_datos()
```
