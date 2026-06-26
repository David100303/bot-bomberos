import requests
from bs4 import BeautifulSoup
import time
import os

# --- VARIABLES DE ENTORNO ---
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')

# --- RUTAS OFICIALES CGBVP ---
URL_EMERGENCIAS = "https://sgonorte.bomberosperu.gob.pe/24horas"
URL_UNIDADES = "https://www.bomberosperu.gob.pe/sgo/ceem/SGO_CEEM_CDVehiculos.asp"

# --- CONFIGURACIÓN ---
UNIDADES_10 = ["B-10", "AMB-10", "RES-10", "ESC-10", "AUX-10", "M10-1"]
UBICACIONES_CLAVE = ["CERCADO DE LIMA", "AV. TACNA", "JR. DE LA UNION", "PLAZA SAN MARTIN"]

# --- MEMORIA DEL BOT ---
emergencias_conocidas = set()
estado_unidades = {unidad: "DESCONOCIDO" for unidad in UNIDADES_10}

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': CHAT_ID, 'text': mensaje})
    except Exception as e:
        print(f"Error al enviar mensaje: {e}")

# Añadimos cabeceras para simular que somos un navegador y evitar bloqueos
headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

print("Iniciando vigilancia de la Salvadora 10 (Telegram 24/7)...")

while True:
    try:
        # =========================================================
        # 1. REVISIÓN DE EMERGENCIAS (Y alertas cercanas)
        # =========================================================
        resp_emergencias = requests.get(URL_EMERGENCIAS, headers=headers, timeout=10)
        soup_emergencias = BeautifulSoup(resp_emergencias.text, 'html.parser')
        
        for fila in soup_emergencias.find_all('tr'):
            texto_fila = fila.text.strip().upper()
            es_cerca = any(lugar in texto_fila for lugar in UBICACIONES_CLAVE)
            es_nuestra_unidad = any(unidad in texto_fila for unidad in UNIDADES_10)
            
            if es_cerca or es_nuestra_unidad:
                # Generamos un ID simple con los primeros caracteres para no repetir
                id_emergencia = texto_fila[:20].replace(" ", "")
                
                if id_emergencia not in emergencias_conocidas:
                    motivo = "🚨 EMERGENCIA EN TU ZONA" if es_cerca else "🚒 SALVADORA 10 DESPACHADA"
                    mensaje = f"{motivo}\n\nDetalle:\n{texto_fila}"
                    
                    enviar_telegram(mensaje)
                    emergencias_conocidas.add(id_emergencia)
                    print(f"Alerta de emergencia enviada: {id_emergencia}")

        # =========================================================
        # 2. REVISIÓN DEL ESTADO DE LAS UNIDADES
        # =========================================================
        resp_unidades = requests.get(URL_UNIDADES, headers=headers, timeout=10)
        soup_unidades = BeautifulSoup(resp_unidades.text, 'html.parser')
        
        # Buscamos en todo el texto de la tabla de vehículos
        for fila in soup_unidades.find_all('tr'):
            columnas = fila.find_all('td')
            if len(columnas) > 2:
                nombre_unidad = columnas[0].text.strip().upper()
                
                # Si la unidad en la tabla es una de las nuestras
                if nombre_unidad in UNIDADES_10:
                    estado_actual = columnas[2].text.strip().upper() # Asumiendo que el estado está en la 3ra columna
                    
                    # Si el estado cambió respecto a lo que recordaba el bot
                    if estado_actual != estado_unidades[nombre_unidad] and estado_unidades[nombre_unidad] != "DESCONOCIDO":
                        
                        icono = "🟢" if "SERVICIO" in estado_actual else ("🔴" if "EMERGENCIA" in estado_actual else "🟡")
                        mensaje = f"🔄 CAMBIO DE ESTADO: {nombre_unidad}\n{icono} Nuevo estado: {estado_actual}"
                        
                        enviar_telegram(mensaje)
                        print(f"Cambio de estado: {nombre_unidad} -> {estado_actual}")
                    
                    # Actualizamos la memoria del bot
                    estado_unidades[nombre_unidad] = estado_actual

        # Esperar 2 minutos para no saturar los servidores de los bomberos
        time.sleep(120)
        
    except Exception as e:
        print(f"Error en la consulta web: {e}")
        time.sleep(120)
