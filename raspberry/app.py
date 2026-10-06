import cherrypy
from database import inicializar_db, guardar_lectura, obtener_historial, obtener_ultima_lectura
from logica import decidir_estado

PULSO_BASE = 75  # línea base de pulso en reposo, ajustable

class SimvaAPI:

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def datos_actuales(self):
        ultima = obtener_ultima_lectura()
        return ultima if ultima else {"mensaje": "Aún no hay lecturas"}

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def historial(self):
        return obtener_historial(10)

    @cherrypy.expose
    @cherrypy.tools.json_in()
    @cherrypy.tools.json_out()
    def enviar_lectura(self):
        """Aquí es donde el ESP32 va a mandar sus datos reales (POST)."""
        datos = cherrypy.request.json
        temperatura = datos.get("temperatura")
        humedad = datos.get("humedad")
        co2 = datos.get("co2", 0)
        pulso = datos.get("pulso")

        estado, ventilador = decidir_estado(co2, pulso, PULSO_BASE)
        guardar_lectura(temperatura, humedad, co2, pulso, ventilador, estado)

        return {"estado": estado, "ventilador": ventilador, "mensaje": "Lectura guardada"}


if __name__ == "__main__":
    inicializar_db()
    cherrypy.config.update({
        "server.socket_host": "0.0.0.0",
        "server.socket_port": 8080,
    })
    cherrypy.quickstart(SimvaAPI())
