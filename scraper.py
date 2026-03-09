import requests
import json
import os
import base64
import re
import sys

# SOLUCIÓN: Forzar UTF-8 para evitar errores de codificación
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

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
            nombre = nombre.replace("Usa", "USA").replace("Hd", "HD").replace("Espn", "ESPN")
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
    """Limpieza profunda para agrupar bien."""
    if not texto: return ""
    try:
        t = str(texto).lower().strip()
        # 1. Reemplazar saltos de línea y tabulaciones por espacio
        t = t.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        # 2. Quitar tildes (para agrupar 'Almería' con 'Almeria')
        t = t.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
        # 3. Quitar múltiples espacios seguidos
        t = re.sub(r'\s+', ' ', t).strip()
        return t
    except:
        return str(texto).lower()

def obtener_liga(titulo, categoria):
    titulo_up = str(titulo).upper()
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

# --- PROCESADORES ---

def procesar_streamtp(data):
    eventos = []
    lista = data if isinstance(data, list) else []
    for item in lista:
        try:
            eventos.append({
                "time": str(item.get("time", "--:--")),
                "teams": str(item.get("title", "Evento")).replace('\n', ' '),
                "league": obtener_liga(item.get("title", ""), item.get("category")),
                "url": str(item.get("link", "")),
                "source": "StreamTP"
            })
        except: pass
    return eventos

def procesar_pltvhd(data):
    eventos = []
    lista = data.get("data", [])
    for item in lista:
        try:
            attrs = item.get("attributes", {})
            hora = str(attrs.get("diary_hour", "--:--"))
            if len(hora) > 5: hora = hora[:5]
            titulo = str(attrs.get("diary_description", "Evento")).replace('\n', ' ')
            
            embeds = attrs.get("embeds", {}).get("data", [])
            for emb in embeds:
                emb_attrs = emb.get("attributes", {})
                link_raw = str(emb_attrs.get("embed_iframe", ""))
                link_final = decodificar_base64(link_raw)
                if link_final.startswith('/'): link_final = "https://pltvhd.com" + link_final

                nombre_limpio = str(emb_attrs.get("embed_name", "Canal")).split('|')[0].strip()

                eventos.append({
                    "time": hora,
                    "teams": titulo,
                    "league": obtener_liga(titulo, attrs.get("country", {}).get("data", {}).get("attributes", {}).get("name")),
                    "url": link_final,
                    "source": "PLTVHD",
                    "clean_name": nombre_limpio
                })
        except: pass
    return eventos

def procesar_la14hd(data):
    lista = data if isinstance(data, list) else data.get("data", [])
    eventos = []
    for item in lista:
        try:
            hora = str(item.get("time") or item.get("hour") or "--:--")
            titulo = str(item.get("title") or item.get("teams") or item.get("name") or "Evento").replace('\n', ' ')
            url = str(item.get("url") or item.get("link") or "")
            eventos.append({
                "time": hora,
                "teams": titulo,
                "league": obtener_liga(titulo, item.get("league") or item.get("category")),
                "url": url,
                "source": "La14HD"
            })
        except: pass
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
            
            try:
                data = response.json()
            except:
                text = response.content.decode('utf-8', errors='ignore')
                data = json.loads(text)
            
            if source['type'] == 'streamtp':
                eventos = procesar_streamtp(data)
            elif source['type'] == 'pltvhd':
                eventos = procesar_pltvhd(data)
            elif source['type'] == 'la14hd':
                eventos = procesar_la14hd(data)
            else:
                eventos = []

            print(f"   ✅ {len(eventos)} items.")

            for ev in eventos:
                if not ev['url']: continue

                # Clave de agrupación mejorada
                clave = f"{ev['time']}_{normalizar_texto(ev['teams'])}"

                if clave not in partidos_dict:
                    partidos_dict[clave] = {
                        "time": ev['time'],
                        "teams": ev['teams'],
                        "league": ev['league'],
                        "channels": [],
                        "counters": {}
                    }
                
                origen = ev['source']
                current_count = partidos_dict[clave]['counters'].get(origen, 0) + 1
                partidos_dict[clave]['counters'][origen] = current_count

                base_name = ev.get('clean_name') or limpiar_nombre_canal(ev['url'])
                nombre_final = f"{base_name} ({origen}) OP{current_count}"

                canal = {"name": nombre_final, "url": ev['url']}
                
                if not any(c['url'] == canal['url'] for c in partidos_dict[clave]['channels']):
                    partidos_dict[clave]['channels'].append(canal)

        except Exception as e:
            print(f"   ❌ Error: {e}")

    lista_final = list(partidos_dict.values())
    lista_final.sort(key=lambda x: x['time'])
    
    for p in lista_final:
        if 'counters' in p: del p['counters']
    
    print(f"📊 Total eventos unificados: {len(lista_final)}")

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
    
    try:
        r = requests.patch(url_api, headers=headers, json=payload)
        if r.status_code == 200:
            print("🚀 ¡Actualización exitosa!")
        else:
            print(f"❌ Error subiendo: {r.text}")
    except Exception as e:
        print(f"❌ Excepción subiendo: {e}")

if __name__ == "__main__":
    actualizar_datos()
