import os
import cherrypy
import sqlite3
from datetime import datetime
from logica import decidir_estado

DB = "lecturas.db"

def init_db():
    con = sqlite3.connect(DB)
    # Tabla con soporte para CO2, temp, hum, pulso y operador
    con.execute("""CREATE TABLE IF NOT EXISTS lecturas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT, co2 REAL, temp REAL, hum REAL, pulso REAL, operador TEXT)""")
    con.commit()
    con.close()

operador_activo = "anonimo"

def evaluar_ultimas():
    """ Evalua las ultimas lecturas guardadas; None si no hay datos """
    con = sqlite3.connect(DB)
    filas = con.execute("SELECT co2, temp, hum, pulso FROM lecturas ORDER BY id DESC LIMIT 10").fetchall()
    con.close()
    if not filas:
        return None
    ahora = datetime.now()
    co2_actual, temp, hum, pulso = filas[0]
    evaluacion = decidir_estado(
        co2=co2_actual,
        historial_co2=[f[0] for f in reversed(filas)],
        temp=temp,
        hum=hum,
        pulso=pulso,
        hora=ahora.hour,
        dia_semana=ahora.weekday()
    )
    return filas[0], evaluacion

class API:
    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def operador(self):
        """ Define el operador que se asigna a las lecturas que no traen uno """
        global operador_activo
        d = cherrypy.request.json
        nombre = d.get("operador") if isinstance(d, dict) else None
        if not isinstance(nombre, str) or not nombre.strip():
            raise cherrypy.HTTPError(400, "Falta el campo operador")
        operador_activo = nombre.strip()
        return {"ok": True, "operador": operador_activo}

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def lectura(self):
        """ Endpoint donde el ESP32 envía los datos de los sensores """
        d = cherrypy.request.json
        if not isinstance(d, dict):
            raise cherrypy.HTTPError(400, "Se esperaba un objeto JSON")
        try:
            co2 = float(d["co2"])
            temp = float(d["temp"])
            hum = float(d["hum"])
            pulso = float(d.get("pulso", 70))
        except (KeyError, TypeError, ValueError):
            raise cherrypy.HTTPError(400, "Campos co2, temp, hum (y pulso) deben ser numericos")
        con = sqlite3.connect(DB)
        con.execute(
            "INSERT INTO lecturas (fecha, co2, temp, hum, pulso, operador) VALUES (?,?,?,?,?,?)",
            (
                datetime.now().isoformat(),
                co2,
                temp,
                hum,
                pulso,
                d.get("operador") or operador_activo
            )
        )
        con.commit()
        con.close()
        _, evaluacion = evaluar_ultimas()
        # El ESP32 usa estado y ventilador para accionar rele, LED y buzzer
        return {
            "ok": True,
            "estado": evaluacion["estado"],
            "ventilador": evaluacion["ventilador"],
            "ventilador_pct": evaluacion["ventilador_pct"],
            "vibracion_pct": evaluacion["vibracion_pct"]
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ultimas(self, n=20):
        """ Regresa las últimas N lecturas guardadas """
        try:
            n = max(1, min(int(n), 500))
        except ValueError:
            raise cherrypy.HTTPError(400, "n debe ser un entero")
        con = sqlite3.connect(DB)
        filas = con.execute(
            "SELECT fecha, co2, temp, hum, pulso FROM lecturas ORDER BY id DESC LIMIT ?", (int(n),)
        ).fetchall()
        con.close()
        return [{"fecha": f, "co2": c, "temp": t, "hum": h, "pulso": p} for f, c, t, h, p in filas]

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def estado(self):
        """ Endpoint que consume el Dashboard de la Interfaz Web """
        resultado = evaluar_ultimas()

        if resultado is None:
            return {
                "temp": 22.0, "hum": 50.0, "co2": 400.0, "pulso": 70.0,
                "estado": "Normal", "vent": "OFF", "ventilador_pct": 0, "vibracion_pct": 0,
                "ia_status": "Sin datos registrados", "pendiente": 0.0
            }

        (co2_actual, temp, hum, pulso), evaluacion = resultado

        return {
            "estado": evaluacion["estado"],
            "temp": round(temp, 1),
            "hum": round(hum, 1),
            "co2": int(co2_actual),
            "pulso": int(pulso) if pulso else 0,
            "vent": "ON" if evaluacion["ventilador"] == 1 else "OFF",
            "ventilador_pct": evaluacion["ventilador_pct"],
            "vibracion_pct": evaluacion["vibracion_pct"],
            "ia_status": evaluacion["msg_ia"],
            "pendiente": evaluacion["pendiente"]
        }

def main():
    init_db()
    cherrypy.quickstart(API(), "/", conf)

# Servir la carpeta interfaz/ como aplicación web
PATH_INTERFAZ = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "interfaz"))

conf = {
    "/": {
        "tools.staticdir.on": True,
        "tools.staticdir.dir": PATH_INTERFAZ,
        "tools.staticdir.index": "index.html"
    }
}

cherrypy.config.update({
    "server.socket_host": "0.0.0.0",
    "server.socket_port": 8080,
})

if __name__ == "__main__":
    main()
