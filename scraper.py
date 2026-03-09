import requests
import json
import os

# CONFIGURACIÓN (Lee los secrets que acabamos de crear)
GITHUB_TOKEN = os.getenv("TOKEN_GITHUB")
GIST_ID = os.getenv("GIST_ID")
SOURCE_URL = "https://pltvhd.com/diaries.json"

def limpiar_nombre_canal(url):
    try:
        slug = url.split('stream=')[-1]
        nombre = slug.replace('_', ' ').title()
        nombre = nombre.replace("Usa", "USA").replace("Hd", "HD")
        return nombre
    except:
        return "Canal"

def actualizar_datos():
    print(f"📥 Descargando eventos...")
    
    try:
        response = requests.get(SOURCE_URL, timeout=20)
        data = response.json()
        
        partidos_dict = {}

        for item in data:
            titulo = item.get("title", "Evento Desconocido")
            hora = item.get("time", "--:--")
            clave = f"{hora}_{titulo}"
            link = item.get("link", "")
            
            canal = {
                "name": limpiar_nombre_canal(link),
                "url": link
            }

            if clave not in partidos_dict:
                partidos_dict[clave] = {
                    "time": hora,
                    "teams": titulo,
                    "league": item.get("category", "Deportes"),
                    "channels": [canal]
                }
            else:
                exists = any(c['url'] == link for c in partidos_dict[clave]['channels'])
                if not exists:
                    partidos_dict[clave]['channels'].append(canal)

        lista_final = list(partidos_dict.values())
        lista_final.sort(key=lambda x: x['time'])
        print(f"✅ Procesados: {len(lista_final)} partidos.")

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
            print(f"❌ Error: {r.text}")

    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    actualizar_datos()
