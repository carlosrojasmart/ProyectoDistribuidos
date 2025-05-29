import zmq

import time

import logging

import uuid
 
logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("Facultad")
 
PUERTO_SERVIDOR = 5555
 
IP_SERVIDOR_CENTRAL = "10.43.96.52"

IP_SERVIDOR_BACKUP  = "10.43.96.100"
 
TIMEOUT = 5000  # 5 segundos en milisegundos
 
FACULTADES = {

   1: "Facultad de Ciencias Sociales",

   2: "Facultad de Ciencias Naturales",

   3: "Facultad de Ingeniería",

   4: "Facultad de Medicina",

   5: "Facultad de Derecho",

   6: "Facultad de Artes",

   7: "Facultad de Educación",

   8: "Facultad de Ciencias Económicas",

   9: "Facultad de Arquitectura",

   10: "Facultad de Tecnología"

}
 
MAX_AULAS = 500

MAX_LABORATORIOS = 200
 
class Facultad:

    def __init__(self, nombre):

        self.nombre = nombre

        self.contexto = zmq.Context()

        logger.info(f" Procesando solicitud de facultad {nombre}...")
 
    def enviar_solicitud(self, num_salones, num_laboratorios):

        """Prueba automáticamente Central y luego Backup."""

        solicitud_uuid = str(uuid.uuid4())  # <-- Generar UUID

        for ip_servidor in [IP_SERVIDOR_CENTRAL, IP_SERVIDOR_BACKUP]:

            socket = self.contexto.socket(zmq.REQ)

            socket.setsockopt(zmq.RCVTIMEO, TIMEOUT)

            try:

                logger.info(f"Intentando conexión a {ip_servidor}:{PUERTO_SERVIDOR} ...")

                socket.connect(f"tcp://{ip_servidor}:{PUERTO_SERVIDOR}")

                solicitud = {

                    "uuid": solicitud_uuid,

                    "facultad": self.nombre,

                    "num_salones": num_salones,

                    "num_laboratorios": num_laboratorios

                }

                logger.info(f" Enviando solicitud: {solicitud}")

                socket.send_json(solicitud)

                respuesta = socket.recv_json()
 
                print(f"\n=== RESULTADO DE LA RESERVA (Servidor {ip_servidor}) ===")

                print(f" Facultad: {self.nombre}")

                print(f"\n Salones:")

                print(f"- Solicitados: {num_salones}")

                print(f"- Asignados: {respuesta.get('salones_asignados', 0)}")

                faltan_salones = num_salones - respuesta.get('salones_asignados', 0)

                if faltan_salones > 0:

                    print(f"❌ Faltaron asignar {faltan_salones} salones")
 
                print(f"\n離 Laboratorios:")

                print(f"- Solicitados: {num_laboratorios}")

                print(f"- Asignados: {respuesta.get('laboratorios_asignados', 0)}")

                faltan_labs = num_laboratorios - respuesta.get('laboratorios_asignados', 0)

                if faltan_labs > 0:

                    print(f"❌ Faltaron asignar {faltan_labs} laboratorios")
 
                if respuesta.get("status") == "success":

                    print("\n✅ ¡Todas las asignaciones fueron exitosas!")

                elif respuesta.get("status") == "partial":

                    print(f"\n⚠️ Asignación parcial. Se asignaron {respuesta.get('salones_asignados', 0)} salones y {respuesta.get('laboratorios_asignados', 0)} laboratorios")

                elif respuesta.get("status") == "duplicate":

                    print(f"\n⚠️ Esta solicitud ya fue procesada anteriormente (duplicada).")

                elif respuesta.get("status") == "error":

                    print(f"\n❌ Error: {respuesta.get('message', '')}")
 
                socket.close()

                return respuesta
 
            except zmq.Again:

                logger.warning(f"El servidor {ip_servidor} no respondió en el tiempo esperado, probando siguiente...")

                socket.close()

                continue

            except zmq.ZMQError as e:

                logger.error(f"Error de conexión con {ip_servidor}: {e}")

                socket.close()

                continue

            except Exception as e:

                logger.error(f"Error inesperado: {e}")

                socket.close()

                continue
 
        print("\n⌛ Error: Ningún servidor respondió en el tiempo esperado.")

        return None
 
def mostrar_menu():

    print("\n=== FACULTADES  ===")

    for key, value in FACULTADES.items():

        print(f"{key}. {value}")

    while True:

        try:

            opcion = int(input("\nSeleccione la facultad la cual desea realizar una reserva: "))

            if opcion in FACULTADES:

                return FACULTADES[opcion]

            print("❌ Opción inválida. Intente nuevamente.")

        except ValueError:

            print("❌ Por favor ingrese un número válido.")
 
def solicitar_cantidad(tipo_recurso, maximo):

    while True:

        try:

            mensaje = f"\nIngrese el número de {tipo_recurso} a reservar (1-{maximo}): "

            cantidad = int(input(mensaje))

            if 1 <= cantidad <= maximo:

                return cantidad

            print(f"❌ La cantidad de {tipo_recurso} solicitadas supera la cantidad permitida.")

        except ValueError:

            print(f"❌ Por favor solicite un número valido, máximo puede solicitar {maximo}.")

def enviar_peticiones_a_facultad_balanceado(facultad_id, num_aulas, num_laboratorios):
    """
    Función auxiliar para pruebas automáticas. Elige aleatoriamente entre Servidor Central y Backup.
    No usa menú, ni input del usuario.
    """
    import random
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.RCVTIMEO, TIMEOUT)

    servidor = random.choice([IP_SERVIDOR_CENTRAL, IP_SERVIDOR_BACKUP])
    try:
        socket.connect(f"tcp://{servidor}:{PUERTO_SERVIDOR}")
        solicitud = {
            "uuid": str(uuid.uuid4()),
            "facultad": FACULTADES.get(facultad_id, f"Facultad {facultad_id}"),
            "num_salones": num_aulas,
            "num_laboratorios": num_laboratorios
        }
        socket.send_json(solicitud)
        respuesta = socket.recv_json()
    except Exception as e:
        respuesta = {"success": False, "error": str(e)}
    finally:
        socket.close()
        context.term()

    return respuesta
 
if __name__ == "__main__":

    print("\n=== SISTEMA DE RESERVAS DE AULAS ===")

    print(f"Límites máximos: {MAX_AULAS} aulas | {MAX_LABORATORIOS} laboratorios\n")
 
    try:

        facultad_nombre = mostrar_menu()

        facultad = Facultad(facultad_nombre)
 
        print(f"\nFacultad seleccionada: {facultad_nombre}")

        num_salones = solicitar_cantidad("aulas", MAX_AULAS)

        num_laboratorios = solicitar_cantidad("laboratorios", MAX_LABORATORIOS)
 
        print(f"\n✔ Confirmación:")

        print(f"- Facultad: {facultad_nombre}")

        print(f"- Aulas solicitadas: {num_salones}")

        print(f"- Laboratorios solicitados: {num_laboratorios}")
 
        confirmar = input("\n¿Confirmar solicitud? (S/N): ").strip().lower()

        if confirmar != 's':

            print("\nOperación cancelada por el usuario")

            exit()
 
        print("\nEnviando solicitud al servidor...")

        respuesta = facultad.enviar_solicitud(num_salones, num_laboratorios)
 
        if respuesta is None:

            print("\nNo se pudo completar la solicitud. Por favor intente más tarde.")
 
    except KeyboardInterrupt:

        print("\n\nOperación cancelada por el usuario")

    finally:

        input("\nPresione Enter para salir...")

    

 