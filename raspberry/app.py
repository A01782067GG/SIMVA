import cherrypy
import random

class ServidorSIMVA:
    @cherrypy.expose
    @cherrypy.tools.json_out()
    def datos_actuales(self):
        # Datos simulados mientras no hay componentes físicos
        temp = round(random.uniform(21.0, 29.0), 1)
        hum = round(random.uniform(40.0, 65.0), 1)
        co2 = random.randint(400, 1200)

        return {
            "temperatura": temp,
            "humedad": hum,
            "co2": co2,
            "ventilador": co2 > 800
        }

if __name__ == '__main__':
    cherrypy.config.update({
        'server.socket_host': '0.0.0.0',
        'server.socket_port': 8080
    })
    cherrypy.quickstart(ServidorSIMVA())