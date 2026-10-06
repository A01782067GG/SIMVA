#include "DHT.h"

#define DHTPIN 4       // Pin de datos del sensor conectado al GPIO 4
#define DHTTYPE DHT22  // El sensor AM2302 se configura como DHT22

DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(115200);
  Serial.println("Iniciando prueba AM2302...");
  dht.begin();
}

void loop() {
  delay(2000); // Lee los datos cada 2 segundos

  float h = dht.readHumidity();
  float t = dht.readTemperature();

  if (isnan(h) || isnan(t)) {
    Serial.println("Error al leer el sensor AM2302. Revisa la conexión.");
    return;
  }

  Serial.print("Humedad: ");
  Serial.print(h);
  Serial.print("%  |  Temperatura: ");
  Serial.print(t);
  Serial.println("°C");
}