import sqlite3
 
DB_NAME = "aulas.db"
 
def crear_tablas():
    """Crea la tabla de solicitudes si no existe."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS solicitudes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                uuid TEXT UNIQUE,
                facultad TEXT NOT NULL,
                salones_asignados INTEGER NOT NULL,
                laboratorios_asignados INTEGER NOT NULL,
                fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        print("✅ [DATABASE] Tabla 'solicitudes' creada o ya existente.")
 
def guardar_solicitud(uuid, facultad, salones, laboratorios):
    """Guarda una solicitud en la base de datos si el uuid no existe."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM solicitudes WHERE uuid = ?", (uuid,))
        if cursor.fetchone():
            print(" [DATABASE] Solicitud duplicada ignorada (UUID ya existe).")
            return
        cursor.execute('''
            INSERT INTO solicitudes (uuid, facultad, salones_asignados, laboratorios_asignados)
            VALUES (?, ?, ?, ?)
        ''', (uuid, facultad, salones, laboratorios))
        conn.commit()
        print(f" [DATABASE] Solicitud guardada: {facultad} - {salones} salones, {laboratorios} laboratorios")
 
if __name__ == "__main__":
    crear_tablas()
