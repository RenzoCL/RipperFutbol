import requests
import json
import os
import base64
import re
import sys

# SOLUCIÓN: Forzar UTF-8
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

# DICCIONARIO DE NOMBRES LIMPIOS (Para arreglar nombres feos)
CHANNEL_NAMES = {
    "laligahypermotion": "LaLiga TV",
    "hypermotion1": "LaLiga TV",
    "winsportsplus": "Win Sports +",
    "winsports2": "Win Sports 2",
    "winplus": "Win Sports +",
    "winplus2": "Win Sports 2",
    "espnplus1": "ESPN +",
    "espnplus2": "ESPN +",
    "espn1_nl": "ESPN NL",
    "dsports": "DSports",
    "dsports2": "DSports 2",
    "disney1": "Disney+",
    "disney2": "Disney+",
    "disney3": "Disney+",
    "disney4": "Disney+",
    "disney5": "Disney+",
    "espn3": "ESPN 3",
    "espn3mx": "ESPN 3 MX",
    "espn2": "ESPN 2",
    "fox_deportes_usa": "Fox Deportes",
    "foxdeportes": "Fox Deportes",
    "tntsportschile": "TNT Sports Chile",
    "liga1max": "Liga 1 MAX",
    "tycsports": "TyC Sports",
    "fanatiz1": "Fanatiz",
    "fanatiz2": "Fanatiz",
    "fanatiz3": "Fanatiz",
    "fanatiz4": "Fanatiz",
    "max1": "Max",
    "espndeportes": "ESPN Deportes",
    "sky_sports_laliga": "Sky LaLiga",
    "even1": "Futbol Canal",
    "even2": "NBA League Pass",
    "even4": "Tigo Sports",
    "even10": "FUTV",
    "ecdf_ligapro": "ECDF LigaPro"
}

# --- FUNCIONES AUXILIARES ---

def obtener_nombre_limpio(url, default_name):
    """Busca el nombre en el diccionario o usa el default."""
    try:
        if 'stream=' in url:
            slug = url.split('stream=')[-1].split('&')[0].lower()
            if slug in CHANNEL_NAMES:
                return CHANNEL_NAMES[slug]
    except:
        pass
    return default_name

def decodificar_base64(url_encoded):
    try:
        if '?r=' in url_encoded:
            encoded_part = url_encoded.split('?r=')[-1]
            decoded_bytes = base64.b64decode(encoded_part)
            return decoded_bytes.decode('utf-8')
        return url_encoded
    except:
        return url_encoded

def limpiar_titulo(texto):
    """Limpieza estricta: quita saltos de línea y múltiples espacios."""
    if not texto: return ""
    try:
        t = str(texto).strip()
        # Reemplazar saltos de línea por espacio
        t = t.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        # Reemplazar múltiples espacios por uno solo
        t = re.sub(r'\s+', ' ', t).strip()
        return t
    except:
        return str(texto)

def normalizar_para_agrupar(texto):
    """Convierte a minúsculas y quita tildes para agrupar duplicados."""
    if not texto: return ""
    t = limpiar_titulo(texto).lower()
    t = t.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    return t

def obtener_liga(titulo, categoria):
    titulo_up = limpiar_titulo(titulo).upper()
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
            url = str(item.get("link", ""))
            raw_name = limpiar_nombre_canal_simple(url) # Función simple para default
            clean_name = obtener_nombre_limpio(url, raw_name) # Intentar arreglar
            
            eventos.append({
                "time": str(item.get("time", "--:--")),
                "teams": limpiar_titulo(item.get("title", "Evento")),
                "league": obtener_liga(item.get("title", ""), item.get("category")),
                "url": url,
                "source": "StreamTP",
                "clean_name": clean_name
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
            titulo = limpiar_titulo(attrs.get("diary_description", "Evento"))
            
            embeds = attrs.get("embeds", {}).get("data", [])
            for emb in embeds:
                emb_attrs = emb.get("attributes", {})
                link_raw = str(emb_attrs.get("embed_iframe", ""))
                link_final = decodificar_base64(link_raw)
                if link_final.startswith('/'): link_final = "https://pltvhd.com" + link_final

                raw_name = str(emb_attrs.get("embed_name", "Canal")).split('|')[0].strip()
                clean_name = obtener_nombre_limpio(link_final, raw_name)

                eventos.append({
                    "time": hora,
                    "teams": titulo,
                    "league": obtener_liga(titulo, attrs.get("country", {}).get("data", {}).get("attributes", {}).get("name")),
                    "url": link_final,
                    "source": "PLTVHD",
                    "clean_name": clean_name
                })
        except: pass
    return eventos

def procesar_la14hd(data):
    lista = data if isinstance(data, list) else data.get("data", [])
    eventos = []
    for item in lista:
        try:
            hora = str(item.get("time") or item.get("hour") or "--:--")
            titulo = limpiar_titulo(item.get("title") or item.get("teams") or item.get("name") or "Evento")
            url = str(item.get("url") or item.get("link") or "")
            
            raw_name = limpiar_nombre_canal_simple(url)
            clean_name = obtener_nombre_limpio(url, raw_name)

            eventos.append({
                "time": hora,
                "teams": titulo,
                "league": obtener_liga(titulo, item.get("league") or item.get("category")),
                "url": url,
                "source": "La14HD",
                "clean_name": clean_name
            })
        except: pass
    return eventos

def limpiar_nombre_canal_simple(url):
    try:
        if 'stream=' in url:
            slug = url.split('stream=')[-1].split('&')[0]
            nombre = slug.replace('_', ' ').title()
            return nombre
        return "Canal"
    except:
        return "Canal"

# --- FUNCIÓN PRINCIPAL ---

def actualizar_datos():
    print(f"🚀 Iniciando scraper mejorado...")
    
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

                # Clave de agrupación ESTRICTA (hora + titulo limpio)
                clave = f"{ev['time']}_{normalizar_para_agrupar(ev['teams'])}"

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

                # NOMBRE FINAL
                base_name = ev.get('clean_name')
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
