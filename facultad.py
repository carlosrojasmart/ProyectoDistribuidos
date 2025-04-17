import paramiko
import threading
import time
import zmq
from config import PUERTO_SERVIDOR

# Configuración SSH
usuario = "estudiante"
ip_maquina = "10.43.96.52"
contraseña = "1Rioblanco/7"
puerto_ssh = 22
puerto_local = 5555
puerto_remoto = 5555

def establecer_tunel_ssh():
    """ Crea un túnel SSH que redirige el puerto del servidor remoto al localhost de la PC. """
    print("🔗 Estableciendo túnel SSH...")
    
    cliente = paramiko.SSHClient()
    cliente.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        cliente.connect(ip_maquina, port=puerto_ssh, username=usuario, password=contraseña)
        
        # Crear túnel SSH
        transporte = cliente.get_transport()
        if transporte:
            forward_tunel = transporte.open_channel("direct-tcpip", ("localhost", puerto_remoto), ("localhost", puerto_local))
            print("✅ Túnel SSH establecido con éxito.")
            return cliente, forward_tunel
        else:
            print("❌ Error al crear el túnel SSH.")
            return None, None
    except Exception as e:
        print(f"❌ Error en la conexión SSH: {e}")
        return None, None

# Iniciar túnel SSH antes de conectarse a ZeroMQ
cliente_ssh, tunel_ssh = establecer_tunel_ssh()

# Si el túnel es exitoso, conectamos ZeroMQ
if cliente_ssh and tunel_ssh:
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect("tcp://localhost:5555")  # Usamos localhost porque el túnel redirige

    class Facultad:
        def __init__(self, nombre):
            print(f"Iniciando Facultad: {nombre}")
            self.nombre = nombre
            self.contexto = zmq.Context()
            self.socket = self.contexto.socket(zmq.REQ)
            self.socket.connect(f"tcp://localhost:{PUERTO_SERVIDOR}")
            print(f"Facultad {nombre} conectada al servidor en el puerto {PUERTO_SERVIDOR}")

        def solicitar_aulas(self, num_salones, num_laboratorios):
            solicitud = (self.nombre, num_salones, num_laboratorios)
            print(f"Facultad {self.nombre} enviando solicitud: {solicitud}")
            self.socket.send(str(solicitud).encode())

            print(f"Facultad {self.nombre} esperando respuesta...")
            respuesta = self.socket.recv()
            print(f"Facultad {self.nombre} recibió respuesta: {respuesta.decode()}")

    if __name__ == "__main__":
        facultad = Facultad("Ingeniería")
        facultad.solicitar_aulas(8, 3)

    # Cerrar la conexión SSH después de ejecutar
    tunel_ssh.close()
    cliente_ssh.close()
else:
    print("⚠ No se pudo establecer el túnel SSH, cerrando programa.")
