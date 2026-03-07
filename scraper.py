import requests
from bs4 import BeautifulSoup
import json

def actualizar_json():
    url = "https://streamtp10.com/eventos.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko)"
    }

    try:
        print("Cargando web de origen...")
        response = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ajusta el selector según la estructura real de la web
        eventos_html = soup.find_all('div', class_='event') 
        
        lista_final = []

        for item in eventos_html:
            try:
                nombre = item.find('p', class_='event-name').text.strip()
                # Extraemos el link del input hidden o del atributo value
                link = item.find('input', class_='iframe-link')['value']
                estado = item.find('button', class_='status-button').text.strip()

                lista_final.append({
                    "titulo": nombre,
                    "url": link,
                    "estado": estado
                })
            except Exception:
                continue # Si un evento falla, pasamos al siguiente

        with open('eventos.json', 'w', encoding='utf-8') as f:
            json.dump(lista_final, f, ensure_ascii=False, indent=4)
        
        print(f"✅ Se encontraron {len(lista_final)} eventos.")

    except Exception as e:
        print(f"❌ Error crítico: {e}")

if __name__ == "__main__":
    actualizar_json()
