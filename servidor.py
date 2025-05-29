import zmq
import threading
import sqlite3
import logging
from datetime import datetime
import os
import time
from tabulate import tabulate

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("ServidorCentral")

NUM_SALONES = 450
NUM_LABORATORIOS = 140
PUERTO_SOLICITUDES = 5555
PUERTO_HEALTHCHECK = 5557
PUERTO_SYNC_BACKUP = 5556
DB_NAME = "aulas.db"
INTERFACE = "0.0.0.0"
IP_DEL_BACKUP = "10.43.96.100"

class ServidorCentral:
    def __init__(self):
        self.salones_disponibles = NUM_SALONES
        self.laboratorios_disponibles = NUM_LABORATORIOS
        self.lock = threading.Lock()
        self.contexto = zmq.Context()

        self.socket_solicitudes = self.contexto.socket(zmq.REP)
        self.socket_solicitudes.bind(f"tcp://{INTERFACE}:{PUERTO_SOLICITUDES}")

        self.socket_healthcheck = self.contexto.socket(zmq.REP)
        self.socket_healthcheck.bind(f"tcp://*:{PUERTO_HEALTHCHECK}")

        self._asegurar_tabla()
        self._cargar_estado()

    def _asegurar_tabla(self):
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS solicitudes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE,
                facultad TEXT,
                salones_asignados INTEGER,
                laboratorios_asignados INTEGER,
                fecha DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """)
            conn.commit()
        logger.info("Tabla 'solicitudes' verificada/creada.")

    def _cargar_estado(self):
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(salones_asignados), SUM(laboratorios_asignados) FROM solicitudes")
            total_salones, total_labs = cursor.fetchone()
            if total_salones:
                self.salones_disponibles -= total_salones
            if total_labs:
                self.laboratorios_disponibles -= total_labs
        logger.info(f"Estado inicial: {self.salones_disponibles} salones, {self.laboratorios_disponibles} laboratorios disponibles.")

    def notificar_backup(self, reserva):
        try:
            backup_socket = self.contexto.socket(zmq.REQ)
            backup_socket.connect(f"tcp://{IP_DEL_BACKUP}:{PUERTO_SYNC_BACKUP}")
            backup_socket.setsockopt(zmq.LINGER, 0)
            backup_socket.setsockopt(zmq.RCVTIMEO, 1000)
            backup_socket.send_json(reserva)
            try:
                ack = backup_socket.recv_json()
                logger.info("Reserva notificada al backup.")
            except zmq.Again:
                logger.warning("Backup no respondió a tiempo. Continuando sin bloquear.")
            backup_socket.close()
        except Exception as e:
            logger.error(f"No se pudo notificar reserva al backup: {e}")

    def notificar_borrado_backup(self, id_registro=None):
        try:
            backup_socket = self.contexto.socket(zmq.REQ)
            backup_socket.connect(f"tcp://{IP_DEL_BACKUP}:{PUERTO_SYNC_BACKUP}")
            backup_socket.setsockopt(zmq.LINGER, 0)
            backup_socket.setsockopt(zmq.RCVTIMEO, 1000)

            mensaje = {
                "tipo": "borrado_total" if id_registro is None else "borrado_registro",
                "id": id_registro
            }
            backup_socket.send_json(mensaje)

            try:
                ack = backup_socket.recv_json()
                logger.info("Borrado notificado al backup")
            except zmq.Again:
                logger.warning("Backup no respondió a notificación de borrado")
            backup_socket.close()
        except Exception as e:
            logger.error(f"Error notificando borrado al backup: {e}")

    def manejar_solicitud(self, facultad, num_salones, num_labs, uuid):
        with self.lock:
            fecha_actual = datetime.now().isoformat()
            try:
                with sqlite3.connect(DB_NAME) as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM solicitudes WHERE uuid = ?", (uuid,))
                    if cursor.fetchone():
                        logger.info("Solicitud duplicada detectada, ignorando (UUID ya existe)")
                        return {
                            "status": "duplicate",
                            "message": "Solicitud ya procesada anteriormente.",
                            "salones_asignados": 0,
                            "laboratorios_asignados": 0
                        }
                    salones_asignados = min(num_salones, self.salones_disponibles)
                    labs_asignados = min(num_labs, self.laboratorios_disponibles)
                    self.salones_disponibles -= salones_asignados
                    self.laboratorios_disponibles -= labs_asignados

                    cursor.execute("""
                        INSERT INTO solicitudes (uuid, facultad, salones_asignados, laboratorios_asignados, fecha)
                        VALUES (?, ?, ?, ?, ?)
                    """, (uuid, facultad, salones_asignados, labs_asignados, fecha_actual))
                    conn.commit()
            except Exception as e:
                logger.error(f"Error guardando en la BD local: {e}")

            reserva = {
                "uuid": uuid,
                "facultad": facultad,
                "salones_asignados": salones_asignados,
                "laboratorios_asignados": labs_asignados,
                "fecha": fecha_actual
            }
            threading.Thread(target=self.notificar_backup, args=(reserva,), daemon=True).start()

            logger.info(f"Asignados a {facultad}: {salones_asignados} salones, {labs_asignados} labs.")

            respuesta = {
                "status": "success" if (salones_asignados == num_salones and labs_asignados == num_labs) else "partial",
                "salones_asignados": salones_asignados,
                "laboratorios_asignados": labs_asignados,
                "salones_restantes": self.salones_disponibles,
                "laboratorios_restantes": self.laboratorios_disponibles
            }
            if respuesta["status"] == "partial":
                respuesta["message"] = "No se pudo asignar la cantidad total solicitada por disponibilidad limitada."
            return respuesta

    def recibir_y_atender(self):
        logger.info("Servidor listo para aceptar solicitudes en puerto 5555.")
        while True:
            try:
                mensaje = self.socket_solicitudes.recv_json()
                facultad = mensaje.get("facultad")
                num_salones = mensaje.get("num_salones")
                num_laboratorios = mensaje.get("num_laboratorios")
                uuid = mensaje.get("uuid")
                respuesta = self.manejar_solicitud(facultad, num_salones, num_laboratorios, uuid)
                self.socket_solicitudes.send_json(respuesta)
            except Exception as e:
                logger.error(f"Error inesperado: {e}")
                try:
                    self.socket_solicitudes.send_json({"status": "error", "message": str(e)})
                except Exception as ee:
                    logger.error(f"No se pudo enviar mensaje de error: {ee}")

    def health_check_server(self):
        while True:
            try:
                msg = self.socket_healthcheck.recv_string()
                if msg == "PING":
                    self.socket_healthcheck.send_string("PONG")
            except Exception as e:
                logging.error(f"Error en health-check server: {e}")

    def mostrar_datos(self):
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM solicitudes ORDER BY fecha DESC")
            datos = cursor.fetchall()

            if not datos:
                print("\nNo hay registros en la base de datos.\n")
                return

            headers = ["ID", "UUID", "Facultad", "Salones", "Laboratorios", "Fecha"]
            print("\n" + "="*80)
            print("REGISTROS EN LA BASE DE DATOS".center(80))
            print("="*80)
            print(tabulate(datos, headers=headers, tablefmt="grid"))
            print(f"\nTotal registros: {len(datos)}")
            print(f"Salones disponibles: {self.salones_disponibles}/{NUM_SALONES}")
            print(f"Laboratorios disponibles: {self.laboratorios_disponibles}/{NUM_LABORATORIOS}\n")

    def borrar_registro(self, id_registro):
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT salones_asignados, laboratorios_asignados FROM solicitudes WHERE id = ?", (id_registro,))
            resultado = cursor.fetchone()

            if resultado:
                salones, labs = resultado
                cursor.execute("DELETE FROM solicitudes WHERE id = ?", (id_registro,))
                conn.commit()

                with self.lock:
                    self.salones_disponibles += salones
                    self.laboratorios_disponibles += labs

                threading.Thread(target=self.notificar_borrado_backup, args=(id_registro,), daemon=True).start()

                print(f"\n✅ Registro con ID {id_registro} eliminado correctamente.")
                print(f"Se liberaron {salones} salones y {labs} laboratorios.\n")
                return True
            else:
                print(f"\n❌ No se encontró ningún registro con ID {id_registro}\n")
                return False

    def borrar_todo(self):
        confirmacion = input("\n⚠️ ¿Estás seguro de que quieres borrar TODOS los registros? (s/n): ").lower()
        if confirmacion != 's':
            print("\nOperación cancelada.\n")
            return

        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(salones_asignados), SUM(laboratorios_asignados) FROM solicitudes")
            total_salones, total_labs = cursor.fetchone()

            cursor.execute("DELETE FROM solicitudes")
            conn.commit()

            with self.lock:
                self.salones_disponibles = NUM_SALONES
                self.laboratorios_disponibles = NUM_LABORATORIOS

            threading.Thread(target=self.notificar_borrado_backup, daemon=True).start()

            print("\n️ Todos los registros han sido eliminados.")
            if total_salones:
                print(f"Se liberaron {total_salones} salones y {total_labs} laboratorios.")
            print("Los contadores han sido restablecidos a los valores iniciales.\n")

def mostrar_menu():
    print("\n" + "="*50)
    print(" MENÚ DEL SERVIDOR DE GESTIÓN DE AULAS ".center(50))
    print("="*50)
    print("1. Mostrar todos los registros")
    print("2. Borrar un registro específico")
    print("3. Borrar TODOS los registros")
    print("4. Iniciar/Continuar servicio de reservas")
    print("5. Salir")
    print("="*50)

def menu_interactivo(servidor):
    threading.Thread(target=servidor.health_check_server, daemon=True).start()
    while True:
        mostrar_menu()
        opcion = input("Seleccione una opción (1-5): ")

        if opcion == "1":
            servidor.mostrar_datos()
        elif opcion == "2":
            try:
                id_registro = int(input("Ingrese el ID del registro a borrar: "))
                servidor.borrar_registro(id_registro)
            except ValueError:
                print("\n❌ Error: Debes ingresar un número válido.\n")
        elif opcion == "3":
            servidor.borrar_todo()
        elif opcion == "4":
            print("\nIniciando servicio de reservas... (Presiona Ctrl+C para volver al menú)")
            try:
                servidor.recibir_y_atender()
            except KeyboardInterrupt:
                print("\nVolviendo al menú principal...\n")
                continue
        elif opcion == "5":
            print("\nSaliendo del servidor...\n")
            os._exit(0)
        else:
            print("\n❌ Opción no válida. Por favor, seleccione 1-5.\n")

        time.sleep(1)

if __name__ == "__main__":
    servidor = ServidorCentral()
    menu_interactivo(servidor)
