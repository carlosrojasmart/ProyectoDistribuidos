import zmq
import threading
import sqlite3
import logging
import time
from tabulate import tabulate
import os
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('replica.log')
    ]
)
logger = logging.getLogger("ServidorReplica")

NUM_SALONES = 450
NUM_LABORATORIOS = 140
PUERTO_SOLICITUDES = 5555
PUERTO_HEALTHCHECK = 5557
PUERTO_SYNC = 5556
DB_NAME = "aulas_replica.db"
HEARTBEAT_INTERVAL = 3
HEARTBEAT_TIMEOUT = 5
MAX_FAILED_HEARTBEATS = 3
IP_SERVIDOR_CENTRAL = "10.43.96.52"

class ServidorReplica:
    def __init__(self):
        self.salones_disponibles = NUM_SALONES
        self.laboratorios_disponibles = NUM_LABORATORIOS
        self.lock = threading.Lock()
        self.activo = False
        self.failed_heartbeats = 0
        self.contexto = zmq.Context()

        self.solicitudes_socket = self.contexto.socket(zmq.REP)
        self.solicitudes_socket.bind(f"tcp://*:{PUERTO_SOLICITUDES}")

        self.sync_socket = self.contexto.socket(zmq.REP)
        self.sync_socket.bind(f"tcp://*:{PUERTO_SYNC}")

        self.healthcheck_socket = self.contexto.socket(zmq.REP)
        self.healthcheck_socket.bind(f"tcp://*:{PUERTO_HEALTHCHECK}")

        self._inicializar_db()
        logger.info("Servidor Réplica iniciado en modo STANDBY")

    def _inicializar_db(self):
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
            cursor.execute("SELECT SUM(salones_asignados), SUM(laboratorios_asignados) FROM solicitudes")
            total = cursor.fetchone()
            if total and total[0]:
                self.salones_disponibles -= total[0]
                self.laboratorios_disponibles -= total[1]

    def health_check(self):
        while True:
            try:
                if self.activo:
                    if self._verificar_central_activo():
                        logger.info("Central recuperado, volviendo a modo STANDBY")
                        self.activo = False
                        self.failed_heartbeats = 0
                    time.sleep(HEARTBEAT_INTERVAL)
                    continue
                if not self._verificar_central_activo():
                    self.failed_heartbeats += 1
                    logger.warning(f"Heartbeat fallido ({self.failed_heartbeats}/{MAX_FAILED_HEARTBEATS})")
                    if self.failed_heartbeats >= MAX_FAILED_HEARTBEATS:
                        self.activar_replica()
                else:
                    self.failed_heartbeats = 0
                time.sleep(HEARTBEAT_INTERVAL)
            except Exception as e:
                logger.error(f"Error en health_check: {str(e)}")
                time.sleep(HEARTBEAT_INTERVAL)

    def _verificar_central_activo(self):
        socket = self.contexto.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 0)
        socket.setsockopt(zmq.RCVTIMEO, HEARTBEAT_TIMEOUT * 1000)
        try:
            socket.connect(f"tcp://{IP_SERVIDOR_CENTRAL}:{PUERTO_HEALTHCHECK}")
            socket.send_string("PING")
            reply = socket.recv_string()
            return reply == "PONG"
        except:
            return False
        finally:
            socket.close()

    def activar_replica(self):
        if not self.activo:
            self.activo = True
            self.failed_heartbeats = 0
            logger.warning("¡FALLOVER ACTIVADO! Este servidor ahora es primario")
            print("\n¡ATENCIÓN! Este servidor ha tomado el control como primario")

    def manejar_solicitudes(self):
        while True:
            try:
                if not self.activo:
                    time.sleep(1)
                    continue

                mensaje = self.solicitudes_socket.recv_json()
                uuid = mensaje["uuid"]

                with self.lock:
                    with sqlite3.connect(DB_NAME) as conn:
                        cursor = conn.cursor()
                        cursor.execute("SELECT id FROM solicitudes WHERE uuid = ?", (uuid,))
                        if cursor.fetchone():
                            respuesta = {
                                "status": "duplicate",
                                "message": "Solicitud ya procesada anteriormente.",
                                "salones_asignados": 0,
                                "laboratorios_asignados": 0
                            }
                            self.solicitudes_socket.send_json(respuesta)
                            continue
                        salones = min(mensaje["num_salones"], self.salones_disponibles)
                        labs = min(mensaje["num_laboratorios"], self.laboratorios_disponibles)
                        self.salones_disponibles -= salones
                        self.laboratorios_disponibles -= labs
                        cursor.execute("""
                            INSERT INTO solicitudes (uuid, facultad, salones_asignados, laboratorios_asignados)
                            VALUES (?, ?, ?, ?)
                        """, (uuid, mensaje["facultad"], salones, labs))
                        conn.commit()

                respuesta = {
                    "status": "success" if (salones == mensaje["num_salones"] and labs == mensaje["num_laboratorios"]) else "partial",
                    "salones_asignados": salones,
                    "laboratorios_asignados": labs,
                    "salones_restantes": self.salones_disponibles,
                    "laboratorios_restantes": self.laboratorios_disponibles
                }

                self.solicitudes_socket.send_json(respuesta)
                logger.info(f"Respuesta enviada: {respuesta}")

            except Exception as e:
                logger.error(f"Error manejando solicitud: {str(e)}")
                try:
                    self.solicitudes_socket.send_json({"status": "error", "message": str(e)})
                except:
                    pass

    def recibir_sincronizaciones(self):
        while True:
            try:
                mensaje = self.sync_socket.recv_json()

                if mensaje.get("tipo") == "borrado_total":
                    logger.info("Recibida notificación de borrado total")
                    self._procesar_borrado_total()
                    self.sync_socket.send_json({"status": "ok"})
                elif mensaje.get("tipo") == "borrado_registro":
                    logger.info(f"Recibida notificación de borrado de registro {mensaje.get('id')}")
                    self._procesar_borrado_registro(mensaje.get("id"))
                    self.sync_socket.send_json({"status": "ok"})
                else:
                    logger.info(f"Recibiendo sincronización: {mensaje}")
                    self._procesar_reserva(mensaje)
                    self.sync_socket.send_json({"status": "ok"})

            except Exception as e:
                logger.error(f"Error en sincronización: {str(e)}")
                try:
                    self.sync_socket.send_json({"status": "error", "message": str(e)})
                except:
                    pass

    def _procesar_reserva(self, reserva):
        with self.lock:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM solicitudes WHERE uuid = ?", (reserva["uuid"],))
                if cursor.fetchone():
                    logger.info("Solicitud duplicada recibida en sincronización, ignorando (UUID ya existe)")
                    return
                cursor.execute("""
                    INSERT INTO solicitudes (uuid, facultad, salones_asignados, laboratorios_asignados, fecha)
                    VALUES (?, ?, ?, ?, ?)
                """, (reserva["uuid"], reserva["facultad"], reserva["salones_asignados"], reserva["laboratorios_asignados"], reserva["fecha"]))
                conn.commit()
            self.salones_disponibles -= reserva["salones_asignados"]
            self.laboratorios_disponibles -= reserva["laboratorios_asignados"]

    def _procesar_borrado_total(self):
        with self.lock:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(salones_asignados), SUM(laboratorios_asignados) FROM solicitudes")
                total = cursor.fetchone()
                cursor.execute("DELETE FROM solicitudes")
                conn.commit()
                if total and total[0]:
                    self.salones_disponibles += total[0]
                    self.laboratorios_disponibles += total[1]
                else:
                    self.salones_disponibles = NUM_SALONES
                    self.laboratorios_disponibles = NUM_LABORATORIOS
            logger.info("Borrado total completado por notificación del central")

    def _procesar_borrado_registro(self, id_registro):
        with self.lock:
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT salones_asignados, laboratorios_asignados FROM solicitudes WHERE id = ?", (id_registro,))
                resultado = cursor.fetchone()
                if resultado:
                    cursor.execute("DELETE FROM solicitudes WHERE id = ?", (id_registro,))
                    conn.commit()
                    self.salones_disponibles += resultado[0]
                    self.laboratorios_disponibles += resultado[1]
                    logger.info(f"Registro {id_registro} borrado por notificación del central")

    def health_check_server(self):
        """Responde a health checks cuando está activo como primario."""
        while True:
            try:
                msg = self.healthcheck_socket.recv_string()
                if msg == "PING":
                    self.healthcheck_socket.send_string("PONG")
            except Exception as e:
                logger.error(f"Error en health check server: {str(e)}")

    def mostrar_menu(self):
        while True:
            print("\n" + "="*50)
            print(" MENÚ DEL SERVIDOR RÉPLICA ".center(50))
            print("="*50)
            estado = "ACTIVO (Primario)" if self.activo else f"STANDBY (Fallos: {self.failed_heartbeats}/{MAX_FAILED_HEARTBEATS})"
            print(f"Estado: {estado}")
            print("1. Mostrar registros")
            if self.activo:
                print("2. Borrar registro")
                print("3. Borrar todo")
            print("4. Ver estado")
            print("5. Salir")
            print("="*50)

            try:
                opcion = input("Seleccione opción: ").strip()

                if opcion == "1":
                    self.mostrar_registros()
                elif opcion == "2" and self.activo:
                    self.borrar_registro()
                elif opcion == "3" and self.activo:
                    self.borrar_todo()
                elif opcion == "4":
                    self.mostrar_estado()
                elif opcion == "5":
                    logger.info("Apagando servidor réplica...")
                    os._exit(0)
                else:
                    print("Opción no válida")
            except KeyboardInterrupt:
                continue
            except Exception as e:
                print(f"Error: {str(e)}")

    def mostrar_registros(self):
        with sqlite3.connect(DB_NAME) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM solicitudes ORDER BY fecha DESC")
            registros = cursor.fetchall()
            if registros:
                print("\n" + "="*80)
                print("REGISTROS DE RESERVAS".center(80))
                print("="*80)
                print(tabulate(
                    registros,
                    headers=["ID", "UUID", "Facultad", "Labs", "Laboratorios", "Fecha"],
                    tablefmt="grid"
                ))
                print(f"\nTotal: {len(registros)} registros")
            else:
                print("\nNo hay registros en la base de datos")
            self.mostrar_estado()

    def mostrar_estado(self):
        print(f"\nSalones disponibles: {self.salones_disponibles}/{NUM_SALONES}")
        print(f"Laboratorios disponibles: {self.laboratorios_disponibles}/{NUM_LABORATORIOS}")
        print(f"Estado: {'ACTIVO (Primario)' if self.activo else 'STANDBY'}")

    def borrar_registro(self):
        try:
            id_reg = int(input("Ingrese ID del registro a borrar: "))
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT salones_asignados, laboratorios_asignados FROM solicitudes WHERE id = ?", (id_reg,))
                resultado = cursor.fetchone()
                if resultado:
                    cursor.execute("DELETE FROM solicitudes WHERE id = ?", (id_reg,))
                    conn.commit()
                    with self.lock:
                        self.salones_disponibles += resultado[0]
                        self.laboratorios_disponibles += resultado[1]
                    print(f"\nRegistro {id_reg} borrado. Liberados {resultado[0]} salones y {resultado[1]} laboratorios")
                else:
                    print("\nRegistro no encontrado")
        except ValueError:
            print("\nID debe ser un número")
        except Exception as e:
            print(f"\nError: {str(e)}")

    def borrar_todo(self):
        confirmacion = input("\n¿Está seguro de borrar TODOS los registros? (s/n): ").lower()
        if confirmacion == 's':
            with sqlite3.connect(DB_NAME) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT SUM(salones_asignados), SUM(laboratorios_asignados) FROM solicitudes")
                total = cursor.fetchone()
                cursor.execute("DELETE FROM solicitudes")
                conn.commit()
                with self.lock:
                    if total and total[0]:
                        self.salones_disponibles += total[0]
                        self.laboratorios_disponibles += total[1]
                    else:
                        self.salones_disponibles = NUM_SALONES
                        self.laboratorios_disponibles = NUM_LABORATORIOS
                print("\nTodos los registros han sido borrados")
                self.mostrar_estado()

    def iniciar(self):
        threading.Thread(target=self.health_check, daemon=True).start()
        threading.Thread(target=self.recibir_sincronizaciones, daemon=True).start()
        threading.Thread(target=self.health_check_server, daemon=True).start()
        threading.Thread(target=self.manejar_solicitudes, daemon=True).start()
        self.mostrar_menu()

if __name__ == "__main__":
    try:
        logger.info("Iniciando servidor réplica...")
        servidor = ServidorReplica()
        servidor.iniciar()
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario")
    except Exception as e:
        logger.error(f"Error fatal: {str(e)}")
    finally:
        logger.info("Servidor réplica detenido")
