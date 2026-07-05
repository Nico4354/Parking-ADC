import serial
import time
import requests

# === VARIABLES GLOBALES DE CONFIGURACIÓN ===
PORT = "COM3"          # Cambiar por el puerto correcto asignado a tu Arduino (ej. COM5, /dev/ttyUSB0)
BAUD_RATE = 9600       # Debe coincidir con el Serial.begin() de tu Arduino
API_URL = "http://127.0.0.1:8000" # URL base de la API FastAPI

def parsear_y_enviar(linea: str):
    """Parsea la línea recibida del Arduino y hace el POST correspondiente a la API."""
    linea = linea.strip()
    
    # --- Caso 1: Ocupación de Vehículos ---
    if linea.startswith("ESTADO:"):
        try:
            # Se espera formato: "ESTADO:X" (ej. "ESTADO:3")
            _, valor = linea.split(":", 1)
            carros = int(valor.strip())
            
            respuesta = requests.post(
                f"{API_URL}/api/carros",
                json={"carros_adentro": carros},
                timeout=5
            )
            print(f"[✓ OK] API ESTADO -> Carros: {carros} | Código: {respuesta.status_code}")
            
        except ValueError:
            print(f"[! WARN] Formato numérico incorrecto en ESTADO: '{linea}'")
        except requests.RequestException as e:
            print(f"[✗ ERROR RED] Falló envío de ESTADO a la API: {e}")

    # --- Caso 2: Registro de Clima ---
    elif linea.startswith("CLIMA:"):
        try:
            # Se espera formato: "CLIMA:T,H" (ej. "CLIMA:24.5,60.2")
            _, valores = linea.split(":", 1)
            temp_str, hum_str = valores.split(",", 1)
            
            temperatura = float(temp_str.strip())
            humedad = float(hum_str.strip())
            
            respuesta = requests.post(
                f"{API_URL}/api/clima",
                json={"temperatura": temperatura, "humedad": humedad},
                timeout=5
            )
            print(f"[✓ OK] API CLIMA -> Temp: {temperatura}°C, Hum: {humedad}% | Código: {respuesta.status_code}")
            
        except ValueError:
            print(f"[! WARN] Formato numérico incorrecto en CLIMA: '{linea}'")
        except requests.RequestException as e:
            print(f"[✗ ERROR RED] Falló envío de CLIMA a la API: {e}")
            
    else:
        # Logs de depuración o líneas malformadas
        if len(linea) > 0:
            print(f"[ARDUINO] {linea}")

def main():
    print("="*50)
    print("Iniciando Puente Local: Arduino <-> Nube")
    print(f"Escuchando Puerto: {PORT} a {BAUD_RATE} baudios")
    print(f"Enviando datos a : {API_URL}")
    print("="*50)
    
    # Bucle principal de reconexión
    while True:
        try:
            # Intenta abrir el puerto serial
            with serial.Serial(PORT, BAUD_RATE, timeout=2) as ser:
                print(f"\n[INFO] 🔌 Conectado exitosamente a {PORT}.")
                
                # Bucle de lectura continua
                while True:
                    if ser.in_waiting > 0:
                        try:
                            # Leer línea completa
                            linea_raw = ser.readline()
                            # Decodificar omitiendo errores de caracteres raros (ruido eléctrico)
                            linea_decodificada = linea_raw.decode('utf-8', errors='ignore')
                            
                            if linea_decodificada:
                                parsear_y_enviar(linea_decodificada)
                                
                        except Exception as e:
                            print(f"[! WARN] Error leyendo o decodificando serial: {e}")
                    
                    # Pequeña pausa para evitar usar 100% de CPU
                    time.sleep(0.05)
                    
        except serial.SerialException as e:
            print(f"[✗ DESCONECTADO] No se puede abrir o se perdió la conexión en {PORT}.")
            print("Reintentando en 3 segundos...")
            time.sleep(3)
        except KeyboardInterrupt:
            print("\n[INFO] Programa detenido por el usuario.")
            break
        except Exception as e:
            print(f"[✗ CRÍTICO] Error inesperado: {e}")
            print("Reintentando en 3 segundos...")
            time.sleep(3)

if __name__ == "__main__":
    main()
