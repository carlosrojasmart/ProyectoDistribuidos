import zmq
import time
import random
import logging

# Configuración básica
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Facultad")

# Configuración de conexión
PUERTO_SERVIDOR = 5555
IP_SERVIDOR = "10.43.96.52"  
TIMEOUT = 5000  # 5 segundos en milisegundos

# Lista de facultades (una por solicitud)
FACULTADES = [
    "Ingeniería",
    "Artes",
    "Comunicacion",
    "Derecho",
    "Administracion",
    "Arquitectura"
]

class Facultad:
    def __init__(self, nombre):
        self.nombre = nombre
        self.contexto = zmq.Context()
        logger.info(f" Configurando facultad {nombre}...")

    def enviar_solicitud(self, num_salones, num_laboratorios):
        """Envía una solicitud y maneja la respuesta"""
        socket = self.contexto.socket(zmq.REQ)
        socket.setsockopt(zmq.RCVTIMEO, TIMEOUT)
        
        try:
            # Conectar y enviar
            socket.connect(f"tcp://{IP_SERVIDOR}:{PUERTO_SERVIDOR}")
            
            solicitud = {
                "facultad": self.nombre,
                "num_salones": num_salones,
                "num_laboratorios": num_laboratorios
            }
            
            logger.info(f" Enviando solicitud: {solicitud}")
            socket.send_json(solicitud)
            
            # Esperar respuesta
            respuesta = socket.recv_json()
            logger.info(" Respuesta recibida:")
            logger.info(f"  - Estado: {respuesta.get('status')}")
            logger.info(f"  - Salones asignados: {respuesta.get('salones_asignados', 0)}")
            logger.info(f"  - Laboratorios asignados: {respuesta.get('laboratorios_asignados', 0)}")
            
            if respuesta.get("status") == "partial":
                logger.warning("⚠️ Asignación parcial: " + respuesta.get("message", ""))
            
            return respuesta
            
        except zmq.Again:
            logger.error("⌛ Tiempo de espera agotado. El servidor no respondió.")
            return None
        except zmq.ZMQError as e:
            logger.error(f"❌ Error de ZMQ: {e}")
            return None
        except Exception as e:
            logger.error(f"❌ Error inesperado: {e}")
            return None
        finally:
            socket.close()
            time.sleep(0.1)  # Pequeña pausa entre solicitudes

if __name__ == "__main__":
    # Enviar 5 solicitudes, cada una con una facultad aleatoria
    for i in range(1, 6):
        # Seleccionar una facultad aleatoria para cada solicitud
        facultad_nombre = random.choice(FACULTADES)
        facultad = Facultad(facultad_nombre)
        
        # Generar números aleatorios para salones y laboratorios
        salones = random.randint(1, 10)
        laboratorios = random.randint(1, 4)
        
        logger.info(f"\n=== Solicitud #{i} ({facultad_nombre}) ===")
        respuesta = facultad.enviar_solicitud(salones, laboratorios)
        
        if respuesta is None:
            logger.warning("La solicitud no pudo ser procesada")
        
        time.sleep(1)  # Espera entre solicitudes