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
    {
        "name": "StreamTP",
        "url": "https://streamtp10.com/eventos.json",
        "type": "streamtp"
    },
    {
        "name": "La14HD",
        "url": "https://la14hd.com/eventos/json/agenda123.json",
        "type": "la14hd" # Asumimos estructura similar a streamtp o simple
    },
    {
        "name": "PLTVHD",
        "url": "https://pltvhd.com/diaries.json",
        "type": "pltvhd" # Estructura compleja con Base64
    }
]

# --- FUNCIONES AUXILIARES ---

def limpiar_nombre_canal(url):
    try:
        # Intenta extraer el nombre del parámetro 'stream'
        if 'stream=' in url:
            slug = url.split('stream=')[-1].split('&')[0]
            nombre = slug.replace('_', ' ').title()
            nombre = nombre.replace("Usa", "USA").replace("Hd", "HD")
            return nombre
        return "Canal"
    except:
        return "Canal"

def decodificar_base64(url_encoded):
    """Decodifica links tipo: /embed/eventos.html?r=aHR0cHM..."""
    try:
        if '?r=' in url_encoded:
            # Extraer la parte codificada
            encoded_part = url_encoded.split('?r=')[-1]
            # Decodificar
            decoded_bytes = base64.b64decode(encoded_part)
            return decoded_bytes.decode('utf-8')
        return url_encoded
    except Exception as e:
        # Si falla, devolver el original
        return url_encoded

def normalizar_texto(texto):
    if not texto: return ""
    return re.sub(r'[^\w\s]', '', texto.lower().strip())

# --- PROCESADORES POR FUENTE ---

def procesar_streamtp(data):
    eventos = []
    # Estructura: Lista directa [{}]
    lista = data if isinstance(data, list) else []
    
    for item in lista:
        eventos.append({
            "time": item.get("time", "--:--"),
            "teams": item.get("title", "Evento"),
            "league": item.get("category", "Deportes"),
            "url": item.get("link", "")
        })
    return eventos

def procesar_pltvhd(data):
    eventos = []
    # Estructura: { "data": [ { "attributes": { ... } } ] }
    lista = data.get("data", [])
    
    for item in lista:
        attrs = item.get("attributes", {})
        hora = attrs.get("diary_hour", "--:--")
        # Limpiar hora si tiene segundos (18:00:00 -> 18:00)
        if len(hora) > 5: hora = hora[:5]
        
        titulo = attrs.get("diary_description", "Evento")
        
        # Procesar embeds (canales)
        embeds = attrs.get("embeds", {}).get("data", [])
        for emb in embeds:
            emb_attrs = emb.get("attributes", {})
            link_raw = emb_attrs.get("embed_iframe", "")
            
            # DECODIFICAR BASE64
            link_final = decodificar_base64(link_raw)
            
            # Si el link es relativo (/embed/...), convertirlo en absoluto
            if link_final.startswith('/'):
                link_final = "https://pltvhd.com" + link_final

            eventos.append({
                "time": hora,
                "teams": titulo,
                "league": attrs.get("country", {}).get("data", {}).get("attributes", {}).get("name", "Deportes"),
                "url": link_final
            })
            
    return eventos

def procesar_la14hd(data):
    # Asumimos que puede ser lista directa o con 'data'
    lista = data if isinstance(data, list) else data.get("data", [])
    eventos = []
    
    for item in lista:
        # Intenta varios nombres de campo posibles
        hora = item.get("time") or item.get("hour") or "--:--"
        titulo = item.get("title") or item.get("teams") or item.get("name") or "Evento"
        url = item.get("url") or item.get("link") or ""
        
        eventos.append({
            "time": hora,
            "teams": titulo,
            "league": item.get("league") or item.get("category") or "Deportes",
            "url": url
        })
    return eventos

# --- FUNCIÓN PRINCIPAL ---

def actualizar_datos():
    print(f"🚀 Iniciando scraper multi-fuente universal...")
    
    # Diccionario para agrupar
    partidos_dict = {}

    for source in SOURCES:
        print(f"🔍 Obteniendo: {source['name']}...")
        try:
            response = requests.get(source['url'], timeout=15)
            if response.status_code != 200:
                print(f"   ❌ Error HTTP: {response.status_code}")
                continue
                
            data = response.json()
            
            # SELECCIONAR PROCESADOR
            if source['type'] == 'streamtp':
                eventos = procesar_streamtp(data)
            elif source['type'] == 'pltvhd':
                eventos = procesar_pltvhd(data)
            elif source['type'] == 'la14hd':
                eventos = procesar_la14hd(data)
            else:
                eventos = []

            print(f"   ✅ {len(eventos)} items procesados.")

            # --- AGRUPACIÓN ---
            for ev in eventos:
                if not ev['url']: continue

                clave = f"{ev['time']}_{normalizar_texto(ev['teams'])}"

                if clave not in partidos_dict:
                    partidos_dict[clave] = {
                        "time": ev['time'],
                        "teams": ev['teams'],
                        "league": ev['league'],
                        "channels": []
                    }
                
                # Etiquetar canal con su origen
                canal = {
                    "name": f"{limpiar_nombre_canal(ev['url'])} ({source['name'][:3].upper()})",
                    "url": ev['url']
                }
                
                # Evitar duplicados exactos de URL
                if not any(c['url'] == canal['url'] for c in partidos_dict[clave]['channels']):
                    partidos_dict[clave]['channels'].append(canal)

        except Exception as e:
            print(f"   ❌ Error procesando {source['name']}: {e}")

    # ORDENAR Y GUARDAR
    lista_final = list(partidos_dict.values())
    lista_final.sort(key=lambda x: x['time'])
    
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
