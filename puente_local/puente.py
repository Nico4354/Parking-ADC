import serial
import time
import requests

# ================= CONFIGURACIÓN =================
PORT = "COM8"        
BAUD_RATE = 9600     
BASE_URL = "https://parking-adc.onrender.com"
# =================================================

def iniciar_puente():
    print("=" * 50)
    print("Iniciando Puente Local Bidireccional")
    print(f"Escuchando Puerto: {PORT} a {BAUD_RATE} baudios")
    print(f"Conectado a la Nube: {BASE_URL}")
    print("=" * 50)

    while True:
        try:
            ser = serial.Serial(PORT, BAUD_RATE, timeout=1)
            time.sleep(2)  # Pausa para que el Arduino reinicie tras abrir el puerto
            print(f"\n[INFO] 🔌 Conectado exitosamente a {PORT}.")

            while True:
                if ser.in_waiting > 0:
                    linea = ser.readline().decode('utf-8', errors='ignore').strip()
                    if not linea:
                        continue
                    
                    # 1. SOLICITUD DE SINCRONIZACIÓN (NUEVO)
                    if linea == "SYNC_REQUEST":
                        print("[INFO] 🔄 Arduino solicitó sincronización inicial...")
                        try:
                            res = requests.get(f"{BASE_URL}/api/estado", timeout=5)
                            if res.status_code == 200:
                                carros_db = res.json().get("carros_adentro", 0)
                                # Enviar dato al Arduino con el formato SYNC:X
                                comando = f"SYNC:{carros_db}\n"
                                ser.write(comando.encode('utf-8'))
                                print(f"[✓ OK] Sincronización exitosa. Restaurando Arduino a {carros_db} carros.")
                        except Exception as e:
                            print(f"[✗ ERR] Falló la sincronización con la BD: {e}")

                    # 2. ACTUALIZACIÓN DE ESTADO
                    elif linea.startswith("ESTADO:"):
                        try:
                            valor = int(linea.split(":")[1])
                            payload = {"carros_adentro": valor}
                            res = requests.post(f"{BASE_URL}/api/carros", json=payload, timeout=5)
                            print(f"[✓ OK] API ESTADO -> Carros: {valor} | Código: {res.status_code}")
                        except Exception as e:
                            print(f"[✗ ERR] Error enviando ESTADO: {e}")

                    # 3. ACTUALIZACIÓN DE CLIMA
                    elif linea.startswith("CLIMA:"):
                        try:
                            datos = linea.split(":")[1].split(",")
                            temp = float(datos[0])
                            hum = float(datos[1])
                            payload = {"temperatura": temp, "humedad": hum}
                            res = requests.post(f"{BASE_URL}/api/clima", json=payload, timeout=5)
                            print(f"[✓ OK] API CLIMA -> Temp: {temp}°C, Hum: {hum}% | Código: {res.status_code}")
                        except Exception as e:
                            print(f"[✗ ERR] Error enviando CLIMA: {e}")

        except serial.SerialException:
            print(f"[✗ DESCONECTADO] No se puede abrir o se perdió la conexión en {PORT}.")
            print("Reintentando en 3 segundos...")
            time.sleep(3)
        except KeyboardInterrupt:
            print("\n[INFO] Deteniendo el puente local de forma segura...")
            break

if __name__ == '__main__':
    iniciar_puente()