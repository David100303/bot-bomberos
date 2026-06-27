import requests
from bs4 import BeautifulSoup
import os
import json
import time
import re

# --- TUS DATOS DE TELEGRAM ---
TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
CHAT_ID = os.environ.get('CHAT_ID')

URL_EMERGENCIAS = "https://sgonorte.bomberosperu.gob.pe/24horas"
URL_UNIDADES = "https://www.bomberosperu.gob.pe/sgo/ceem/SGO_CEEM_CDVehiculos.asp"

# --- TUS UNIDADES (Filtro único y estricto) ---
UNIDADES_10 = ["B-10", "AMB-10", "RES-10", "ESC-10", "AUX-10", "M10-1"]
patron_unidades = re.compile(r'\b(?:' + '|'.join(UNIDADES_10) + r')\b')

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, data={'chat_id': CHAT_ID, 'text': mensaje})
    except Exception as e:
        print(f"Error enviando mensaje: {e}")

# --- CARGAR MEMORIA DE ESTADO ---
memoria = {'emergencias': [], 'unidades': {u: "DESCONOCIDO" for u in UNIDADES_10}}
if os.path.exists('memoria.json'):
    with open('memoria.json', 'r', encoding='utf-8') as f:
        try:
            memoria = json.load(f)
        except json.JSONDecodeError:
            pass

headers = {'User-Agent': 'Mozilla/5.0'}

# ==========================================
# BUCLE INTERNO (Revisa 4 veces, cada 60s)
# ==========================================
for intento in range(4):
    print(f"Iniciando escaneo {intento + 1}/4...")
    
    # 1. REVISAR EMERGENCIAS (Página Principal)
    try:
        resp = requests.get(URL_EMERGENCIAS, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        for fila in soup.find_all('tr'):
            texto_fila = fila.text.strip().upper()
            
            # IGNORAR INCIDENTES CERRADOS
            if "CERRADO" in texto_fila:
                continue
            
            # Buscar EXACTAMENTE tus unidades (ignorará emergencias de otras compañías)
            es_nuestra_unidad = bool(patron_unidades.search(texto_fila))
            
            if es_nuestra_unidad:
                id_emergencia = texto_fila[:20].replace(" ", "")
                if id_emergencia not in memoria['emergencias']:
                    enviar_telegram(f"🚒 ¡SALVADORA 10 DESPACHADA!\n\nDetalle:\n{texto_fila}")
                    memoria['emergencias'].append(id_emergencia)
    except Exception as e:
        print(f"Error consultando emergencias: {e}")

    # 2. REVISAR ESTADO DE VEHÍCULOS (Cambios de servicio)
    try:
        resp_u = requests.get(URL_UNIDADES, headers=headers, timeout=10)
        soup_u = BeautifulSoup(resp_u.text, 'html.parser')
        
        for fila in soup_u.find_all('tr'):
            cols = fila.find_all('td')
            if len(cols) > 2:
                nombre = cols[0].text.strip().upper()
                if nombre in UNIDADES_10:
                    estado_actual = cols[2].text.strip().upper()
                    estado_anterior = memoria['unidades'].get(nombre, "DESCONOCIDO")
                    
                    if estado_actual != estado_anterior and estado_anterior != "DESCONOCIDO":
                        icono = "🟢" if "SERVICIO" in estado_actual else ("🔴" if "EMERGENCIA" in estado_actual else "🟡")
                        enviar_telegram(f"🔄 CAMBIO DE ESTADO: {nombre}\n{icono} Nuevo: {estado_actual}")
                    
                    memoria['unidades'][nombre] = estado_actual
    except Exception as e:
        print(f"Error consultando unidades: {e}")

    # Pausa de 60 segundos entre escaneos
    if intento < 3:
        time.sleep(60)

# Limpiamos el historial viejo para mantener el JSON ligero
memoria['emergencias'] = memoria['emergencias'][-50:]

# --- GUARDAR MEMORIA DE ESTADO AL FINALIZAR ---
with open('memoria.json', 'w', encoding='utf-8') as f:
    json.dump(memoria, f, indent=4)
