import zmq
import time
import logging

# Configuración básica
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Facultad")

# Configuración de conexión
PUERTO_SERVIDOR = 5555
IP_SERVIDOR = "10.43.96.52"  # Asegúrate que esta IP es correcta
TIMEOUT = 5000  # 5 segundos en milisegundos

# Lista de facultades disponibles
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

# Límites máximos
MAX_AULAS = 500
MAX_LABORATORIOS = 200

class Facultad:
    def __init__(self, nombre):
        self.nombre = nombre
        self.contexto = zmq.Context()
        logger.info(f" Procesando solicitud de facultad {nombre}...")

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
            
            # Mostrar resultados al usuario
            print("\n=== RESULTADO DE LA RESERVA ===")
            print(f" Facultad: {self.nombre}")
            
            # Manejo de salones
            print(f"\n Salones:")
            print(f"- Solicitados: {num_salones}")
            print(f"- Asignados: {respuesta.get('salones_asignados', 0)}")
            faltan_salones = num_salones - respuesta.get('salones_asignados', 0)
            if faltan_salones > 0:
                print(f"❌ Faltaron asignar {faltan_salones} salones")
            
            # Manejo de laboratorios
            print(f"\n Laboratorios:")
            print(f"- Solicitados: {num_laboratorios}")
            print(f"- Asignados: {respuesta.get('laboratorios_asignados', 0)}")
            faltan_labs = num_laboratorios - respuesta.get('laboratorios_asignados', 0)
            if faltan_labs > 0:
                print(f"❌ Faltaron asignar {faltan_labs} laboratorios")
            
            # Resumen final
            if respuesta.get("status") == "success":
                print("\n✅ ¡Todas las asignaciones fueron exitosas!")
            elif respuesta.get("status") == "partial":
                print(f"\n⚠️ Asignación parcial. Se asignaron {respuesta.get('salones_asignados', 0)} salones y {respuesta.get('laboratorios_asignados', 0)} laboratorios")
            
            return respuesta
            
        except zmq.Again:
            print("\n⌛ Error: El servidor no respondió en el tiempo esperado")
            return None
        except zmq.ZMQError as e:
            print(f"\n❌ Error de conexión: {e}")
            return None
        except Exception as e:
            print(f"\n❌ Error inesperado: {e}")
            return None
        finally:
            socket.close()
            time.sleep(0.1)

def mostrar_menu():
    """Muestra el menú de facultades disponibles"""
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
    """Solicita al usuario la cantidad de recursos a reservar"""
    while True:
        try:
            mensaje = f"\nIngrese el número de {tipo_recurso} a reservar (1-{maximo}): "
            cantidad = int(input(mensaje))
            if 1 <= cantidad <= maximo:
                return cantidad
            print(f"❌ La cantidad de aulas solicitadas supera la cantidad permitida.")
        except ValueError:
            print("❌ Por favor solicite un número valido maximo puede solicitar {maximo}.")

if __name__ == "__main__":
    print("\n=== SISTEMA DE RESERVAS DE AULAS ===")
    print(f"Límites máximos: {MAX_AULAS} aulas | {MAX_LABORATORIOS} laboratorios\n")
    
    try:
        # Selección de facultad
        facultad_nombre = mostrar_menu()
        facultad = Facultad(facultad_nombre)
        
        # Solicitud de cantidades
        print(f"\nFacultad seleccionada: {facultad_nombre}")
        num_salones = solicitar_cantidad("aulas", MAX_AULAS)
        num_laboratorios = solicitar_cantidad("laboratorios", MAX_LABORATORIOS)
        
        # Confirmación
        print(f"\n✔ Confirmación:")
        print(f"- Facultad: {facultad_nombre}")
        print(f"- Aulas solicitadas: {num_salones}")
        print(f"- Laboratorios solicitados: {num_laboratorios}")
        
        confirmar = input("\n¿Confirmar solicitud? (S/N): ").strip().lower()
        if confirmar != 's':
            print("\nOperación cancelada por el usuario")
            exit()
        
        # Envío de solicitud
        print("\nEnviando solicitud al servidor...")
        respuesta = facultad.enviar_solicitud(num_salones, num_laboratorios)
        
        if respuesta is None:
            print("\nNo se pudo completar la solicitud. Por favor intente más tarde.")
        
    except KeyboardInterrupt:
        print("\n\nOperación cancelada por el usuario")
    finally:
        input("\nPresione Enter para salir...")