import cherrypy
import random
import database

class ServidorSIMVA:
    def __init__(self):
        # Asegura que la tabla exista al iniciar el servidor
        database.inicializar_db()

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def datos_actuales(self):
        # Datos simulados de sensores
        temp = round(random.uniform(21.0, 29.0), 1)
        hum = round(random.uniform(40.0, 65.0), 1)
        co2 = random.randint(400, 1200)
        ventilador = co2 > 800

        # Guarda la lectura en la base de datos SQLite
        database.guardar_lectura(temp, hum, co2, ventilador)

        return {
            "temperatura": temp,
            "humedad": hum,
            "co2": co2,
            "ventilador": ventilador
        }

    @cherrypy.expose
    @cherrypy.tools.json_out()
    def historial(self):
        # Endpoint para que el Dashboard pueda pedir las últimas 10 lecturas guardadas
        registros = database.obtener_historial(10)
        return [
            {
                "fecha": r[0],
                "temperatura": r[1],
                "humedad": r[2],
                "co2": r[3],
                "ventilador": bool(r[4])
            }
            for r in registros
        ]

if __name__ == '__main__':
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8080
    })
    cherrypy.quickstart(ServidorSIMVA())
