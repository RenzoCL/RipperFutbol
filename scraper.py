import requests
import json
import os
import base64
import re
import sys
import time

# Forzar UTF-8 en la salida
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# CONFIGURACION
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")
GIST_ID = os.getenv("GIST_ID")

# FUENTES  (el "type" debe coincidir con un procesador: streamtp / pltvhd / la14hd)
SOURCES = [
    {"name": "futbol libre", "url": "https://futbollibretv.lol/api/agenda", "type": "pltvhd",
     "referer": "https://futbollibretv.lol/"},
    {"name": "StreamTP", "url": "https://streamtp-golden1.click/events.json", "type": "streamtp",
     "referer": "https://streamtp-golden1.click/"},
]

BASE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

# --- DICCIONARIOS DE MAPEO ---

# 1. Reglas de sinonimos para titulos (regex)
TITLE_REGEX_RULES = [
    (r"LaLiga\s*2", "LaLiga SmartBank"),
    (r"LaLiga\s*SmartBank", "LaLiga SmartBank"),
    (r"LaLiga\s*Hypermotion", "LaLiga HyperMotion"),
]

# 2. Sinonimos de nombres de canales
CHANNEL_NAMES = {
    "laligahypermotion": "LaLiga TV", "hypermotion1": "LaLiga TV",
    "winsportsplus": "Win Sports +", "winsports2": "Win Sports 2",
    "winplus": "Win Sports +", "winplus2": "Win Sports 2",
    "espnplus1": "ESPN +", "espnplus2": "ESPN +",
    "espn1_nl": "ESPN NL",
    "dsports": "DSports", "dsports2": "DSports 2",
    "disney1": "Disney+", "disney2": "Disney+", "disney3": "Disney+",
    "disney4": "Disney+", "disney5": "Disney+",
    "espn3": "ESPN 3", "espn3mx": "ESPN 3 MX", "espn2": "ESPN 2",
    "fox_deportes_usa": "Fox Deportes", "foxdeportes": "Fox Deportes",
    "tntsportschile": "TNT Sports Chile",
    "liga1max": "Liga 1 MAX",
    "tycsports": "TyC Sports",
    "fanatiz1": "Fanatiz", "fanatiz2": "Fanatiz", "fanatiz3": "Fanatiz", "fanatiz4": "Fanatiz",
    "max1": "Max",
    "espndeportes": "ESPN Deportes",
    "sky_sports_laliga": "Sky LaLiga",
    "even1": "Futbol Canal", "even2": "NBA League Pass", "even4": "Tigo Sports", "even10": "FUTV",
    "ecdf_ligapro": "ECDF LigaPro",
}

# --- FUNCIONES AUXILIARES ---

def limpiar_nombre_canal_simple(url):
    """Extrae y limpia el nombre del canal desde la URL"""
    try:
        if "stream=" in url:
            slug = url.split("stream=")[-1].split("&")[0]
            return slug.replace("_", " ").title()
        # URLs tipo .../return/dsports-fullHD-recomendado.html
        m = re.search(r"/([^/?#]+?)\.html?(?:$|[?#])", url)
        if m:
            slug = re.sub(r"[-_](recomendado|fullhd|hd|sd)", "", m.group(1), flags=re.IGNORECASE)
            return slug.replace("-", " ").replace("_", " ").title()
        return "Canal"
    except Exception:
        return "Canal"


def obtener_nombre_canal_limpio(url, default_name):
    """Obtiene el nombre limpio del canal usando el diccionario de mapeo"""
    try:
        if "stream=" in url:
            slug = url.split("stream=")[-1].split("&")[0].lower()
            if slug in CHANNEL_NAMES:
                return CHANNEL_NAMES[slug]
    except Exception:
        pass
    return default_name


def decodificar_base64(url_encoded):
    """Decodifica URLs codificadas en base64"""
    try:
        if "?r=" in url_encoded:
            encoded_part = url_encoded.split("?r=")[-1]
            # Rellenar padding si falta
            encoded_part += "=" * (-len(encoded_part) % 4)
            decoded_bytes = base64.b64decode(encoded_part)
            return decoded_bytes.decode("utf-8")
        return url_encoded
    except Exception:
        return url_encoded


def limpiar_texto(texto):
    """Limpia y normaliza texto"""
    if not texto:
        return ""
    t = str(texto).strip()
    t = t.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    return re.sub(r"\s+", " ", t).strip()


def normalizar_para_agrupar(texto):
    """Normaliza texto para agrupar eventos duplicados"""
    if not texto:
        return ""
    t = limpiar_texto(texto).lower()
    for a, b in (("á", "a"), ("é", "e"), ("í", "i"), ("ó", "o"), ("ú", "u"),
                 ("à", "a"), ("è", "e"), ("ì", "i"), ("ò", "o"), ("ù", "u")):
        t = t.replace(a, b)
    return t


def obtener_titulo_estandar(titulo_original):
    """Aplica reglas regex para estandarizar titulos"""
    titulo_limpio = limpiar_texto(titulo_original)
    for patron, reemplazo in TITLE_REGEX_RULES:
        titulo_limpio = re.sub(patron, reemplazo, titulo_limpio, flags=re.IGNORECASE)
    return titulo_limpio


def obtener_liga(titulo, categoria):
    """Identifica la liga/categoria del evento"""
    titulo_up = limpiar_texto(titulo).upper()
    categorias_conocidas = [
        "LA LIGA", "LALIGA", "SERIE A", "PREMIER", "CHAMPIONSHIP", "CHAMPIONS",
        "LIBERTADORES", "SUDAMERICANA", "LIGA 1", "LIGA1", "BETPLAY", "FA CUP",
        "COPA DEL REY", "NBA", "NFL", "TENNIS", "TENIS", "F1", "BOXEO",
    ]
    for cat in categorias_conocidas:
        if cat in titulo_up:
            return cat.title()
    if categoria and categoria not in ["Other", "Futbol", "Deportes"]:
        return categoria
    return "Futbol"


def extraer_lista(data):
    """Devuelve una lista de items sin importar si el JSON es lista o dict"""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "events", "eventos", "items", "agenda"):
            val = data.get(key)
            if isinstance(val, list):
                return val
    return []


# --- PROCESADORES ---

def procesar_streamtp(data):
    """Procesa eventos en formato StreamTP"""
    eventos = []
    for item in extraer_lista(data):
        try:
            url = str(item.get("link") or item.get("url") or "")
            raw_name = limpiar_nombre_canal_simple(url)
            clean_name = obtener_nombre_canal_limpio(url, raw_name)

            titulo_raw = str(item.get("title") or item.get("name") or "Evento")
            titulo_final = obtener_titulo_estandar(titulo_raw)

            eventos.append({
                "time": str(item.get("time", "--:--")),
                "teams": titulo_final,
                "league": obtener_liga(titulo_final, item.get("category")),
                "url": url,
                "source": "StreamTP",
                "clean_name": clean_name,
            })
        except Exception as e:
            print(f"   [streamtp] item descartado: {e}")
    return eventos


def procesar_pltvhd(data):
    """Procesa eventos en formato PLTVHD / Futbol Libre"""
    eventos = []
    for item in extraer_lista(data):
        try:
            attrs = item.get("attributes", {})
            hora = str(attrs.get("diary_hour", "--:--"))
            if len(hora) > 5:
                hora = hora[:5]

            titulo_raw = str(attrs.get("diary_description", "Evento"))
            titulo_final = obtener_titulo_estandar(titulo_raw)

            pais = (attrs.get("country") or {}).get("data") or {}
            categoria = (pais.get("attributes") or {}).get("name")

            embeds = (attrs.get("embeds") or {}).get("data", [])
            for emb in embeds:
                emb_attrs = emb.get("attributes", {})
                link_raw = str(emb_attrs.get("embed_iframe", ""))
                link_final = decodificar_base64(link_raw)

                # Asegurar que la URL sea completa
                if link_final.startswith("/"):
                    link_final = "https://futbollibretv.lol" + link_final
                elif not link_final.startswith("http"):
                    link_final = "https://futbollibretv.lol/" + link_final

                raw_name = str(emb_attrs.get("embed_name", "Canal")).split("|")[0].strip()
                clean_name = obtener_nombre_canal_limpio(link_final, raw_name)

                eventos.append({
                    "time": hora,
                    "teams": titulo_final,
                    "league": obtener_liga(titulo_final, categoria),
                    "url": link_final,
                    "source": "PLTVHD",
                    "clean_name": clean_name,
                })
        except Exception as e:
            print(f"   [pltvhd] item descartado: {e}")
    return eventos


def procesar_la14hd(data):
    """Procesa eventos en formato La14HD"""
    eventos = []
    for item in extraer_lista(data):
        try:
            hora = str(item.get("time") or item.get("hour") or "--:--")
            titulo_raw = str(item.get("title") or item.get("teams") or item.get("name") or "Evento")
            titulo_final = obtener_titulo_estandar(titulo_raw)

            url = str(item.get("url") or item.get("link") or "")
            raw_name = limpiar_nombre_canal_simple(url)
            clean_name = obtener_nombre_canal_limpio(url, raw_name)

            eventos.append({
                "time": hora,
                "teams": titulo_final,
                "league": obtener_liga(titulo_final, item.get("league") or item.get("category")),
                "url": url,
                "source": "La14HD",
                "clean_name": clean_name,
            })
        except Exception as e:
            print(f"   [la14hd] item descartado: {e}")
    return eventos


PROCESADORES = {
    "streamtp": procesar_streamtp,
    "pltvhd": procesar_pltvhd,
    "la14hd": procesar_la14hd,
}

# --- FUNCION PRINCIPAL ---

def actualizar_datos():
    """Obtiene datos de todas las fuentes, los procesa y sube a GitHub"""
    print("Iniciando scraper...")

    partidos_dict = {}

    for source in SOURCES:
        print(f"Obteniendo: {source['name']}...")
        try:
            headers = dict(BASE_HEADERS)
            if source.get("referer"):
                headers["Referer"] = source["referer"]

            response = requests.get(
                source["url"], headers=headers, params={"_": int(time.time() * 1000)}, timeout=20
            )
            if response.status_code != 200:
                print(f"   Error HTTP: {response.status_code}")
                print(f"   Respuesta: {response.text[:200]}")
                continue

            try:
                data = response.json()
            except Exception:
                text = response.content.decode("utf-8", errors="ignore")
                try:
                    data = json.loads(text)
                except Exception:
                    print(f"   La respuesta no es JSON valido: {text[:200]}")
                    continue

            procesador = PROCESADORES.get(source["type"])
            if procesador is None:
                print(f"   Tipo de fuente desconocido: '{source['type']}' (usa: {', '.join(PROCESADORES)})")
                continue

            eventos = procesador(data)
            print(f"   Items procesados: {len(eventos)}")
            if not eventos:
                print(f"   DEBUG tipo: {type(data).__name__}")
                print(f"   DEBUG respuesta: {json.dumps(data, ensure_ascii=False)[:800]}")

            # Agrupar eventos por hora y equipos
            for ev in eventos:
                if not ev["url"]:
                    continue

                clave = f"{ev['time']}_{normalizar_para_agrupar(ev['teams'])}"

                if clave not in partidos_dict:
                    partidos_dict[clave] = {
                        "time": ev["time"],
                        "teams": ev["teams"],
                        "league": ev["league"],
                        "channels": [],
                        "counters": {},
                    }

                origen = ev["source"]
                current_count = partidos_dict[clave]["counters"].get(origen, 0) + 1
                partidos_dict[clave]["counters"][origen] = current_count

                base_name = ev.get("clean_name", "Canal")
                nombre_final = f"{base_name} ({origen}) OP{current_count}"
                canal = {"name": nombre_final, "url": ev["url"]}

                # Evitar URLs duplicadas
                if not any(c["url"] == canal["url"] for c in partidos_dict[clave]["channels"]):
                    partidos_dict[clave]["channels"].append(canal)

        except Exception as e:
            print(f"   Error: {e}")

    # Preparar lista final
    lista_final = list(partidos_dict.values())
    lista_final.sort(key=lambda x: x["time"])

    for p in lista_final:
        p.pop("counters", None)

    print(f"Total eventos: {len(lista_final)}")

    print("\n--- RESULTADO ---")
    for evento in lista_final[:5]:
        print(f"{evento['time']} | {evento['teams']} ({evento['league']}) | {len(evento['channels'])} canales")

    # No sobrescribir el Gist con una lista vacia
    if not lista_final:
        print("\n⚠ Lista vacia: no se sube para no borrar los datos anteriores del Gist")
        return

    # Subir a GitHub Gist
    if GITHUB_TOKEN and GIST_ID:
        print("\nSubiendo a GitHub Gist...")
        url_api = f"https://api.github.com/gists/{GIST_ID}"
        headers = {
            "Authorization": f"Bearer {GITHUB_TOKEN.strip()}",
            "Accept": "application/vnd.github+json",
        }
        payload = {
            "files": {
                "eventos.json": {
                    "content": json.dumps(lista_final, indent=2, ensure_ascii=False)
                }
            }
        }

        try:
            r = requests.patch(url_api, headers=headers, json=payload, timeout=20)
            if r.status_code == 200:
                print("✓ Actualizacion exitosa!")
            else:
                print(f"✗ Error subiendo ({r.status_code}): {r.text}")
        except Exception as e:
            print(f"✗ Excepcion subiendo: {e}")
    else:
        print("\n⚠ No se configuraron TOKEN_GITHUB o GIST_ID - resultado no se subio")


if __name__ == "__main__":
    actualizar_datos()
