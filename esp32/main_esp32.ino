#include <WiFi.h>
#include <HTTPClient.h>
#include <DHT.h>

// --- CONFIGURACIÓN DE RED WI-FI ---
const char* ssid = "TU_RED_WIFI";
const char* password = "TU_PASSWORD";

// --- IP Y PUERTO DE LA RASPBERRY PI ---
// Reemplaza por la IP local que tenga tu Raspberry Pi (ejemplo: 192.168.1.50)
const char* serverUrl = "http://192.168.1.50:8080/lectura";

// --- CONFIGURACIÓN DE SENSORES ---
#define DHTPIN 4
#define DHTTYPE DHT22  // Sensor AM2302 / DHT22
DHT dht(DHTPIN, DHTTYPE);

// --- ACTUADORES (pines por definir con el circuito de potencia final) ---
const int PIN_RELE = 26;    // Relé del ventilador 12 V (activo en HIGH)
const int PIN_LED = 25;     // LED de alerta
const int PIN_BUZZER = 27;  // Buzzer, solo en Emergencia

unsigned long lastTime = 0;
const unsigned long timerDelay = 5000; // Enviar lecturas cada 5 segundos (Requerimiento Project Charter)

// Aplica la decisión del servidor a los actuadores
void aplicarActuadores(bool ventilador, bool emergencia) {
  digitalWrite(PIN_RELE, ventilador ? HIGH : LOW);
  digitalWrite(PIN_LED, ventilador ? HIGH : LOW);
  digitalWrite(PIN_BUZZER, emergencia ? HIGH : LOW);
}

// Lee "ventilador" y "estado" de la respuesta {"ok": true, "estado": "...", "ventilador": 1}
void procesarRespuesta(const String& response) {
  int pos = response.indexOf("\"ventilador\"");
  if (pos < 0) return;
  int dos = response.indexOf(':', pos);
  bool ventilador = dos >= 0 && response.substring(dos + 1).toInt() == 1;
  bool emergencia = response.indexOf("Emergencia") >= 0;
  aplicarActuadores(ventilador, emergencia);
}

void setup() {
  Serial.begin(115200);
  dht.begin();

  pinMode(PIN_RELE, OUTPUT);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  aplicarActuadores(false, false);

  // Conexión Wi-Fi
  WiFi.begin(ssid, password);
  Serial.print("Conectando a Wi-Fi");
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n¡Conectado exitosamente!");
  Serial.print("Dirección IP del ESP32: ");
  Serial.println(WiFi.localIP());
}

void loop() {
  // Enviar datos cada 5 segundos
  if ((millis() - lastTime) > timerDelay) {
    if (WiFi.status() == WL_CONNECTED) {
      
      // 1. Lectura de sensores
      float humedad = dht.readHumidity();
      float temperatura = dht.readTemperature();
      
      // CO2 y Pulso (Si aún no se tiene la lectura real del sensor físico SCD41/MAX30102, se simula o lee)
      float co2 = random(450, 1100);  // Reemplazar con scd41.readMeasurement() cuando esté armado
      float pulso = random(65, 95);   // Reemplazar con max30102.getHeartRate()

      if (isnan(humedad) || isnan(temperatura)) {
        // No se envían valores inventados: se reintenta en el siguiente ciclo
        Serial.println("Error leyendo el sensor AM2302/DHT22, lectura omitida");
        lastTime = millis();
        return;
      }

      // 2. Crear cliente HTTP
      HTTPClient http;
      http.begin(serverUrl);
      http.addHeader("Content-Type", "application/json");

      // 3. Crear Payload JSON
      String jsonPayload = "{";
      jsonPayload += "\"co2\":" + String(co2) + ",";
      jsonPayload += "\"temp\":" + String(temperatura) + ",";
      jsonPayload += "\"hum\":" + String(humedad) + ",";
      jsonPayload += "\"pulso\":" + String(pulso);  // el operador lo asigna el servidor
      jsonPayload += "}";

      Serial.print("Enviando JSON: ");
      Serial.println(jsonPayload);

      // 4. Enviar petición HTTP POST a la Raspberry Pi
      int httpResponseCode = http.POST(jsonPayload);

      if (httpResponseCode > 0) {
        String response = http.getString();
        Serial.print("Respuesta Servidor: ");
        Serial.print(httpResponseCode);
        Serial.print(" ");
        Serial.println(response);
        procesarRespuesta(response);
      } else {
        Serial.print("Error enviando POST: ");
        Serial.println(httpResponseCode);
      }

      http.end();
    } else {
      Serial.println("Wi-Fi desconectado");
    }
    lastTime = millis();
  }
}
