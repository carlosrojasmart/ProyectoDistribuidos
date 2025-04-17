import zmq
import random
from config import PUERTO_SERVIDOR

class ProgramaAcademico:
    def __init__(self, nombre, facultad):
        self.nombre = nombre
        self.facultad = facultad
        self.contexto = zmq.Context()
        self.socket = self.contexto.socket(zmq.REQ)  # Request-Reply
        self.socket.connect(f"tcp://localhost:{PUERTO_SERVIDOR}")  # Conectarse al servidor

    def solicitar_aulas(self):
        num_salones = random.randint(7, 10)
        num_laboratorios = random.randint(2, 4)
        print(f"{self.nombre} solicita {num_salones} salones y {num_laboratorios} laboratorios.")
        
        self.socket.send_json((self.facultad, num_salones, num_laboratorios))
        respuesta = self.socket.recv_string()
        print(f"{self.nombre} recibió respuesta: {respuesta}")

if __name__ == "__main__":
    programa = ProgramaAcademico("Ingeniería de Sistemas", "Ingeniería")
    programa.solicitar_aulas()
