# Importación de módulos necesarios
import zmq              # Para comunicación entre procesos usando ZeroMQ
import threading        # Para sincronización con locks
import sqlite3          # Para interactuar con la base de datos SQLite
from datetime import datetime
import logging          # Para registrar eventos e información del servidor
import time

# Configuración del sistema de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("ServidorCentral")

# Constantes del sistema
NUM_SALONES = 450                    # Total de salones disponibles al inicio
NUM_LABORATORIOS = 140               # Total de laboratorios disponibles
PUERTO_SERVIDOR = 5555               # Puerto TCP en el que escucha el servidor
DB_NAME = "aulas.db"                 # Nombre de la base de datos
INTERFACE = "0.0.0.0"                # Escucha conexiones en todas las interfaces

# Clase principal que representa el Servidor Central
class ServidorCentral:
    def __init__(self):
        # Estado inicial del servidor
        self.salones_disponibles = NUM_SALONES
        self.laboratorios_disponibles = NUM_LABORATORIOS
        self.lock = threading.Lock()     # Lock para evitar accesos simultáneos
        self.corriendo = True            # Control de ejecución del bucle principal

        # Inicialización de ZeroMQ con socket REP (respuesta)
        self.contexto = zmq.Context()
        self.socket = self.contexto.socket(zmq.REP)
        try:
            bind_address = f"tcp://{INTERFACE}:{PUERTO_SERVIDOR}"
            logger.info(f"Intentando bind en {bind_address}")
            self.socket.bind(bind_address)
            logger.info(f"✅ Servidor iniciado en {bind_address}")
        except zmq.ZMQError as e:
            logger.error(f"❌ Error al iniciar servidor: {e}")
            raise

        # Verifica que la tabla de la BD tenga las columnas esperadas
        self.verificar_estructura_bd()
        # Carga reservas ya existentes para actualizar disponibilidad
        self.cargar_asignaciones_previas()

    def verificar_estructura_bd(self):
        """
        Verifica que la tabla 'solicitudes' tenga la estructura correcta.
        Si no tiene las columnas necesarias, lanza un error.
        """
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(solicitudes)")
                columnas = [col[1] for col in cursor.fetchall()]

                columnas_requeridas = {'id', 'facultad', 'salones_asignados', 'laboratorios_asignados', 'fecha'}
                if not columnas_requeridas.issubset(set(columnas)):
                    logger.error("❌ La estructura de la BD no coincide con lo esperado")
                    raise ValueError("Estructura de BD incompatible")
                logger.info("✅ Estructura de BD verificada correctamente")
        except sqlite3.Error as e:
            logger.error(f"❌ Error al verificar estructura de BD: {e}")
            raise

    def cargar_asignaciones_previas(self):
        """
        Al iniciar el servidor, consulta la base de datos para recuperar cuántos
        recursos ya han sido asignados y actualiza el estado del servidor.
        """
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute('SELECT SUM(salones_asignados), SUM(laboratorios_asignados) FROM solicitudes')
                total_salones, total_labs = cursor.fetchone()

                if total_salones is not None:
                    with self.lock:
                        self.salones_disponibles = NUM_SALONES - total_salones
                        self.laboratorios_disponibles = NUM_LABORATORIOS - (total_labs if total_labs else 0)
                    logger.info(f" Estado inicial cargado: Salones disponibles: {self.salones_disponibles}, Laboratorios disponibles: {self.laboratorios_disponibles}")
                else:
                    logger.info(" No hay asignaciones previas en la BD")
        except sqlite3.Error as e:
            logger.error(f"❌ Error al cargar asignaciones previas: {e}")

    def manejar_solicitud(self, facultad, num_salones, num_labs):
        """
        Procesa una solicitud entrante de una facultad.
        Asigna la cantidad máxima posible de recursos y guarda la reserva.
        Devuelve una respuesta con el estado de la asignación.
        """
        with self.lock:  # Sección crítica protegida
            try:
                # Log si la solicitud supera lo disponible
                if num_salones > self.salones_disponibles or num_labs > self.laboratorios_disponibles:
                    logger.warning(f"⚠️ Solicitud excede disponibilidad: {facultad} pidió {num_salones} salones y {num_labs} labs")

                # Asignación según disponibilidad
                labs_asignados = min(num_labs, self.laboratorios_disponibles)
                salones_asignados = min(num_salones, self.salones_disponibles)

                self.laboratorios_disponibles -= labs_asignados
                self.salones_disponibles -= salones_asignados

                # Registro en la base de datos
                with sqlite3.connect(DB_NAME) as conn:
                    cursor = conn.cursor()
                    cursor.execute('''
                        INSERT INTO solicitudes (facultad, salones_asignados, laboratorios_asignados)
                        VALUES (?, ?, ?)
                    ''', (facultad, salones_asignados, labs_asignados))
                    conn.commit()

                # Preparación de la respuesta
                respuesta = {
                    "status": "success",
                    "salones_asignados": salones_asignados,
                    "laboratorios_asignados": labs_asignados,
                    "salones_restantes": self.salones_disponibles,
                    "laboratorios_restantes": self.laboratorios_disponibles
                }

                # Si no se pudo asignar todo, se informa
                if num_labs > labs_asignados or num_salones > salones_asignados:
                    respuesta["status"] = "partial"
                    respuesta["message"] = "Recursos insuficientes para asignación completa"

                logger.info(f" Asignados {salones_asignados} salones y {labs_asignados} labs a {facultad}")
                return respuesta

            except Exception as e:
                logger.error(f"❌ Error procesando solicitud: {e}", exc_info=True)
                return {
                    "status": "error",
                    "message": str(e)
                }

    def limpiar_base_datos(self):
        """
        Elimina todos los registros de reservas en la base de datos.
        También reinicia la disponibilidad total de salones y laboratorios.
        """
        try:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute('DELETE FROM solicitudes')
                conn.commit()
            with self.lock:
                self.salones_disponibles = NUM_SALONES
                self.laboratorios_disponibles = NUM_LABORATORIOS
            logger.warning("♻️ Base de datos limpiada y contadores reiniciados")
            return True
        except Exception as e:
            logger.error(f"❌ Error al limpiar base de datos: {e}")
            return False

    def mostrar_reservas(self):
        """
        Muestra por pantalla todas las reservas registradas,
        incluyendo un resumen total de recursos asignados.
        """
        try:
            with sqlite3.connect(DB_NAME) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('''
                    SELECT facultad, salones_asignados, laboratorios_asignados, fecha 
                    FROM solicitudes ORDER BY fecha DESC
                ''')
                resultados = cursor.fetchall()

                if not resultados:
                    print("\nNo hay reservas registradas en la base de datos.")
                    return

                print("\n📋 RESERVAS ACTUALES:")
                print("-" * 60)
                for idx, reserva in enumerate(resultados, 1):
                    print(f"\nReserva #{idx}:")
                    print(f"  Facultad: {reserva['facultad']}")
                    print(f"  Fecha: {reserva['fecha']}")
                    print(f"  Salones asignados: {reserva['salones_asignados']}")
                    print(f"  Laboratorios asignados: {reserva['laboratorios_asignados']}")

                print("\n📊 RESUMEN TOTAL:")
                total_salones = sum(r['salones_asignados'] for r in resultados)
                total_labs = sum(r['laboratorios_asignados'] for r in resultados)
                print(f"  Total salones reservados: {total_salones}/{NUM_SALONES}")
                print(f"  Total laboratorios reservados: {total_labs}/{NUM_LABORATORIOS}")
        except Exception as e:
            logger.error(f"❌ Error al mostrar reservas: {e}")

    def aceptar_solicitudes(self):
        """
        Inicia un bucle que recibe solicitudes de reserva desde clientes ZeroMQ
        y responde con el resultado de la asignación.
        """
        logger.info("⏳ Modo: Aceptar solicitudes (Presione Ctrl+C para volver al menú)")
        self.corriendo = True
        while self.corriendo:
            try:
                self.socket.RCVTIMEO = 1000  # Timeout de 1 segundo
                mensaje = self.socket.recv_json()
                logger.info(f"📩 Solicitud recibida de {mensaje.get('facultad', 'desconocido')}")
                respuesta = self.manejar_solicitud(
                    mensaje["facultad"],
                    mensaje["num_salones"],
                    mensaje["num_laboratorios"]
                )
                self.socket.send_json(respuesta)
            except zmq.Again:
                continue  # Timeout, seguimos esperando
            except KeyError as e:
                self.socket.send_json({
                    "status": "error",
                    "message": f"Solicitud mal formada: falta {str(e)}"
                })
            except zmq.ZMQError as e:
                logger.error(f"❌ Error de ZMQ: {e}")
            except KeyboardInterrupt:
                logger.info("🛑 Volviendo al menú principal...")
                self.corriendo = False
            except Exception as e:
                logger.error(f"❌ Error inesperado: {e}", exc_info=True)
                self.socket.send_json({
                    "status": "error",
                    "message": "Error interno del servidor"
                })

    def mostrar_menu(self):
        """
        Muestra el menú de opciones por consola para el administrador.
        Permite ver reservas, aceptar solicitudes, limpiar BD o salir.
        """
        while True:
            print("\n" + "=" * 50)
            print(" MENÚ PRINCIPAL - SERVIDOR DE AULAS")
            print("=" * 50)
            print("1. Aceptar solicitudes de reserva")
            print("2. Mostrar salones/laboratorios reservados")
            print("3. Limpiar base de datos (reiniciar todo)")
            print("4. Salir")
            try:
                opcion = input("\nSeleccione una opción (1-4): ").strip()
                if opcion == "1":
                    self.aceptar_solicitudes()
                elif opcion == "2":
                    self.mostrar_reservas()
                elif opcion == "3":
                    confirmacion = input("¿Está seguro que desea limpiar TODA la base de datos? (s/n): ").lower()
                    if confirmacion == "s":
                        if self.limpiar_base_datos():
                            print("✅ Base de datos limpiada exitosamente")
                        else:
                            print("❌ Error al limpiar la base de datos")
                elif opcion == "4":
                    print("\n👋 Saliendo del sistema...")
                    self.contexto.destroy()
                    break
                else:
                    print("❌ Opción no válida. Por favor seleccione 1-4.")
            except KeyboardInterrupt:
                print("\n👋 Saliendo del sistema...")
                self.contexto.destroy()
                break
            except Exception as e:
                print(f"❌ Error inesperado: {e}")

# Punto de entrada del programa
if __name__ == "__main__":
    try:
        servidor = ServidorCentral()
        servidor.mostrar_menu()
    except Exception as e:
        logging.error(f"❌ Error fatal: {e}", exc_info=True)
