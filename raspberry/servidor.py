import cherrypy
import sqlite3
from datetime import datetime

DB = "lecturas.db"

def init_db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS lecturas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT, co2 REAL, temp REAL, hum REAL)""")
    con.commit()
    con.close()

class API:
    @cherrypy.expose
    def index(self):
        return "SIMVA funcionando"

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def lectura(self):
        d = cherrypy.request.json
        con = sqlite3.connect(DB)
        con.execute("INSERT INTO lecturas (fecha, co2, temp, hum) VALUES (?,?,?,?)",
                    (datetime.now().isoformat(), d.get("co2"), d.get("temp"), d.get("hum")))
        con.commit()
        con.close()
        return {"ok": True}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def ultimas(self, n=20):
        con = sqlite3.connect(DB)
        filas = con.execute(
            "SELECT fecha, co2, temp, hum FROM lecturas ORDER BY id DESC LIMIT ?", (int(n),)
        ).fetchall()
        con.close()
        return [{"fecha": f, "co2": c, "temp": t, "hum": h} for f, c, t, h in filas]

init_db()
cherrypy.config.update({
    "server.socket_host": "0.0.0.0",
    "server.socket_port": 8080,
})
cherrypy.quickstart(API())
