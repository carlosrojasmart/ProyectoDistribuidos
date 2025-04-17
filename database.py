import sqlite3

DB_NAME = "aulas.db"

def crear_tablas():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS solicitudes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        facultad TEXT,
        num_salones INTEGER,
        num_laboratorios INTEGER,
        estado TEXT DEFAULT 'pendiente',
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    conn.commit()
    conn.close()

def guardar_solicitud(facultad, num_salones, num_laboratorios):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    INSERT INTO solicitudes (facultad, num_salones, num_laboratorios) 
    VALUES (?, ?, ?)
    """, (facultad, num_salones, num_laboratorios))

    conn.commit()
    conn.close()

def obtener_solicitudes():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM solicitudes")
    solicitudes = cursor.fetchall()

    conn.close()
    return solicitudes

# Si ejecutamos este archivo directamente, creamos las tablas
if __name__ == "__main__":
    crear_tablas()
    print("Base de datos inicializada.")
