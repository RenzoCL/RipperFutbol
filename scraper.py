import requests
import json
import os
import re

# CONFIGURACIÓN
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB") # Se lee de los secrets
GIST_ID = os.getenv("GIST_ID")           # Se lee de los secrets
SOURCE_URL = "https://streamtp10.com/eventos.json"

def limpiar_nombre_canal(url):
    """Extrae un nombre bonito del link (ej: disney10 -> Disney 10)"""
    try:
        # Extraer lo que viene después de 'stream='
        slug = url.split('stream=')[-1]
        # Reemplazar guiones bajos y poner mayúsculas
        nombre = slug.replace('_', ' ').title()
        # Correcciones comunes
        nombre = nombre.replace("Usa", "USA").replace("Hd", "HD")
        return nombre
    except:
        return "Canal"

def actualizar_datos():
    print(f"📥 Descargando eventos desde {SOURCE_URL}...")
    
    try:
        response = requests.get(SOURCE_URL, timeout=20)
        data = response.json()
        
        # DICCIONARIO PARA AGRUPAR PARTIDOS
        # Clave: (titulo + hora) -> Valor: Info del partido + lista de canales
        partidos_dict = {}

        for item in data:
            # Crear clave única para agrupar
            # Usamos titulo y hora para distinguir si hay cambios
            titulo = item.get("title", "Evento Desconocido")
            hora = item.get("time", "--:--")
            clave = f"{hora}_{titulo}"

            link = item.get("link", "")
            
            # Formato del canal para tu App
            canal = {
                "name": limpiar_nombre_canal(link),
                "url": link
            }

            if clave not in partidos_dict:
                # Crear entrada nueva
                partidos_dict[clave] = {
                    "time": hora,
                    "teams": titulo,
                    "league": item.get("category", "Deportes"),
                    "channels": [canal] # Iniciamos lista de canales
                }
            else:
                # El partido ya existe, solo agregamos el canal nuevo
                # Validamos que no repita el mismo link
                exists = any(c['url'] == link for c in partidos_dict[clave]['channels'])
                if not exists:
                    partidos_dict[clave]['channels'].append(canal)

        # Convertir diccionario a lista ordenada por hora
        lista_final = list(partidos_dict.values())
        lista_final.sort(key=lambda x: x['time'])

        print(f"✅ Procesados: {len(lista_final)} partidos únicos.")

        # SUBIR A GITHUB GIST
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
            print("🚀 ¡Actualización exitosa en la nube!")
        else:
            print(f"❌ Error subiendo: {r.text}")

    except Exception as e:
        print(f"❌ Error crítico: {e}")

if __name__ == "__main__":
    actualizar_datos()
