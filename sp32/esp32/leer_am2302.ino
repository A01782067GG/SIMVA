#include <DHT.h>

#define DHTPIN 4       // pin de datos del AM2302
#define DHTTYPE DHT22   // AM2302 = mismo chip que el DHT22

DHT dht(DHTPIN, DHTTYPE);

void setup() {
  Serial.begin(115200);
  dht.begin();
  Serial.println("Iniciando lectura del AM2302...");
}

void loop() {
  delay(2000); // el sensor necesita al menos 2s entre lecturas

  float humedad = dht.readHumidity();
  float temperatura = dht.readTemperature();

  if (isnan(humedad) || isnan(temperatura)) {
    Serial.println("Error leyendo el sensor AM2302");
    return;
  }

  Serial.print("Temperatura: ");
  Serial.print(temperatura);
  Serial.print(" °C   Humedad: ");
  Serial.print(humedad);
  Serial.println(" %");
}
