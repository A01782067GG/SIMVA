import sqlite3
from datetime import datetime

DB_NAME = "simva.db"

def inicializar_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS lecturas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha_hora TEXT NOT NULL,
            temperatura REAL,
            humedad REAL,
            co2 REAL,
            pulso INTEGER,
            ventilador INTEGER DEFAULT 0,
            estado TEXT DEFAULT 'Normal'
        )
    """)
    conn.commit()
    conn.close()

def guardar_lectura(temperatura, humedad, co2, pulso, ventilador, estado):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    fecha_hora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO lecturas (fecha_hora, temperatura, humedad, co2, pulso, ventilador, estado)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (fecha_hora, temperatura, humedad, co2, pulso, ventilador, estado))
    conn.commit()
    conn.close()

def obtener_historial(limite=10):
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM lecturas ORDER BY id DESC LIMIT ?", (limite,))
    filas = cursor.fetchall()
    conn.close()
    return [dict(f) for f in filas]

def obtener_ultima_lectura():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM lecturas ORDER BY id DESC LIMIT 1")
    fila = cursor.fetchone()
    conn.close()
    return dict(fila) if fila else None
  
