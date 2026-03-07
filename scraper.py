import requests
from bs4 import BeautifulSoup
import json

def actualizar_streamtp():
    # URL que me indicaste
    url = "https://streamtp10.com/eventos.html"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://streamtp10.com/"
    }

    try:
        print(f"Buscando partidos en {url}...")
        response = requests.get(url, headers=headers, timeout=20)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        lista_final = []

        # StreamTP suele usar celdas (td) o divs con clases específicas
        # Buscamos elementos que contengan enlaces a canales
        items = soup.find_all(['a', 'div'], href=True)

        for item in items:
            href = item['href']
            texto = item.get_text().strip()

            # Filtramos: solo enlaces que lleven a "canal" o "reproductor"
            if "canal" in href.lower() or "stream" in href.lower():
                # Si el texto está vacío, intentamos buscar un título cerca
                titulo = texto if texto else "Evento Deportivo"
                
                lista_final.append({
                    "titulo": titulo,
                    "url": href if href.startswith('http') else "https://streamtp10.com/" + href,
                    "estado": "LIVE"
                })

        # Si no encontró nada con 'canal', buscamos por tablas (común en estas webs)
        if not lista_final:
            for fila in soup.find_all('tr'):
                columnas = fila.find_all('td')
                if len(columnas) >= 2:
                    nombre = columnas[0].get_text().strip()
                    link_btn = fila.find('a', href=True)
                    if link_btn:
                        lista_final.append({
                            "titulo": nombre,
                            "url": link_btn['href'],
                            "estado": "DISPONIBLE"
                        })

        # Guardar resultados
        with open('eventos.json', 'w', encoding='utf-8') as f:
            json.dump(lista_final, f, ensure_ascii=False, indent=4)
        
        print(f"✅ Proceso terminado. Encontrados: {len(lista_final)}")

    except Exception as e:
        print(f"❌ Error al conectar: {e}")

if __name__ == "__main__":
    actualizar_streamtp()
