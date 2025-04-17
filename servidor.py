import zmq
import threading
from config import PUERTO_SERVIDOR, NUM_SALONES, NUM_LABORATORIOS
from database import guardar_solicitud, crear_tablas


context = zmq.Context()
socket = context.socket(zmq.REP)
socket.bind("tcp://0.0.0.0:5555")  # Cambia el puerto si es necesario


class ServidorCentral:
    def __init__(self):
        self.salones_disponibles = NUM_SALONES
        self.laboratorios_disponibles = NUM_LABORATORIOS
        self.lock = threading.Lock()

        self.contexto = zmq.Context()
        self.socket = self.contexto.socket(zmq.REP)  # Cambiamos a REP
        self.socket.bind(f"tcp://*:{PUERTO_SERVIDOR}")

        crear_tablas()
        print(f"[SERVIDOR] Escuchando en el puerto {PUERTO_SERVIDOR}...")

    def manejar_solicitud(self, solicitud):
        facultad, num_salones, num_labs = solicitud
        print(f"[SERVIDOR] Recibida solicitud de {facultad}: {num_salones} salones, {num_labs} laboratorios")

        with self.lock:
            if num_labs > self.laboratorios_disponibles:
                num_labs = min(num_labs, self.laboratorios_disponibles)
            self.laboratorios_disponibles -= num_labs

            if num_salones > self.salones_disponibles:
                num_salones = min(num_salones, self.salones_disponibles)
            self.salones_disponibles -= num_salones

        guardar_solicitud(facultad, num_salones, num_labs)

        respuesta = f"Asignados {num_salones} salones y {num_labs} laboratorios a {facultad}"
        print(f"[SERVIDOR] Enviando respuesta: {respuesta}")
        return respuesta

    def atender_clientes(self):
        while True:
            print("[SERVIDOR] Esperando mensaje de facultad...")
            mensaje = self.socket.recv()  # Recibe solicitud
            solicitud = eval(mensaje.decode())  # Convertir string recibido a tupla
            print(f"[SERVIDOR] Procesando solicitud: {solicitud}")

            respuesta = self.manejar_solicitud(solicitud)
            self.socket.send(respuesta.encode())  # Enviar respuesta

if __name__ == "__main__":
    servidor = ServidorCentral()
    servidor.atender_clientes()
