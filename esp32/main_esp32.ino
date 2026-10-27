#include <WiFi.h>
#include <HTTPClient.h>
#include <Wire.h>
#include <SensirionI2cScd4x.h>  // Sensirion I2C SCD4x
#include <MAX30105.h>           // SparkFun MAX3010x (sirve para el MAX30102)
#include <heartRate.h>

// --- CONFIGURACIÓN DE RED WI-FI ---
const char* ssid = "TU_RED_WIFI";
const char* password = "TU_PASSWORD";

// --- IP Y PUERTO DE LA RASPBERRY PI ---
// Reemplaza por la IP local que tenga tu Raspberry Pi (ejemplo: 192.168.1.50)
const char* serverUrl = "http://192.168.1.50:8080/lectura";

// --- SENSORES (bus I2C: SDA = GPIO 21, SCL = GPIO 22) ---
SensirionI2cScd4x scd4x;  // CO2, temperatura y humedad
MAX30105 particleSensor;  // frecuencia cardiaca

// --- ACTUADORES (pines provisionales, confirmar con el circuito de potencia) ---
const int PIN_VENTILADOR = 26;  // PWM hacia el módulo D4184 (ventilador 12 V)
const int PIN_VIBRADOR = 27;    // PWM hacia el módulo vibratorio de 5 V
const int PIN_LED = 25;         // LED de estado
const int PIN_BUZZER = 33;      // Buzzer activo (solo en Emergencia)

// Relé en serie entre la fuente de 12 V y el ventilador (no en paralelo con el D4184).
// Se cierra solo cuando el ventilador tiene que girar, así el ventilador queda sin
// alimentación si el ESP32 está apagado, arrancando o con el ventilador al 0 %.
// GPIO 14 no sirve: emite PWM al arrancar y activaría el relé sin querer.
const int PIN_RELE = 32;               // pin provisional, confirmar con el circuito
const bool RELE_ACTIVO_ALTO = true;    // false si el módulo se activa con LOW

const int PWM_FREQ = 5000;  // Hz
const int PWM_BITS = 8;
const int CANAL_VENTILADOR = 0;  // solo se usan con el core ESP32 2.x
const int CANAL_VIBRADOR = 1;

// --- RESPALDO LOCAL (si no hay WiFi o el servidor no responde) ---
const float UMBRAL_CO2 = 1000.0;
const float UMBRAL_EMERGENCIA = 2000.0;

unsigned long lastTime = 0;
const unsigned long timerDelay = 5000;  // Enviar lecturas cada 5 segundos (Requerimiento Project Charter)

// Última medición válida del SCD41 (llega cada ~5 s en modo periódico)
float co2 = 0, temperatura = 0, humedad = 0;
bool hayMedicionScd = false;
unsigned long lastScdCheck = 0;

// Frecuencia cardiaca: promedio de los últimos latidos (0 = sin dedo / sin lectura)
const int PROMEDIO_LATIDOS = 4;
float latidos[PROMEDIO_LATIDOS];
int latidoIdx = 0;
int latidosValidos = 0;
unsigned long ultimoLatido = 0;
float pulso = 0;

void pwmInit(int pin, int canal) {
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(pin, PWM_FREQ, PWM_BITS);
#else
  ledcSetup(canal, PWM_FREQ, PWM_BITS);
  ledcAttachPin(pin, canal);
#endif
}

void pwmEscribir(int pin, int canal, int porcentaje) {
  int duty = (constrain(porcentaje, 0, 100) * ((1 << PWM_BITS) - 1)) / 100;
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(pin, duty);
#else
  ledcWrite(canal, duty);
#endif
}

// Aplica los niveles a los actuadores
void aplicarActuadores(int ventiladorPct, int vibracionPct, bool emergencia) {
  bool ventiladorEncendido = ventiladorPct > 0;
  digitalWrite(PIN_RELE, (ventiladorEncendido == RELE_ACTIVO_ALTO) ? HIGH : LOW);
  pwmEscribir(PIN_VENTILADOR, CANAL_VENTILADOR, ventiladorPct);
  pwmEscribir(PIN_VIBRADOR, CANAL_VIBRADOR, vibracionPct);
  digitalWrite(PIN_LED, (ventiladorPct > 0 || vibracionPct > 0) ? HIGH : LOW);
  digitalWrite(PIN_BUZZER, emergencia ? HIGH : LOW);
}

// Mismas reglas que logica.py, solo con CO2, para cuando el servidor no responde
void controlLocal(float co2Actual) {
  if (co2Actual > UMBRAL_EMERGENCIA) {
    aplicarActuadores(100, 100, true);
  } else if (co2Actual >= UMBRAL_CO2) {
    int pct = min(100, (int)(40 + (co2Actual - UMBRAL_CO2) * 0.06));
    aplicarActuadores(pct, 50, false);
  } else {
    aplicarActuadores(0, 0, false);
  }
}

// Busca "clave": <entero> en el JSON de respuesta
int leerEntero(const String& json, const char* clave, int porDefecto) {
  int pos = json.indexOf(String("\"") + clave + "\"");
  if (pos < 0) return porDefecto;
  int dosPuntos = json.indexOf(':', pos);
  if (dosPuntos < 0) return porDefecto;
  return json.substring(dosPuntos + 1).toInt();
}

// Respuesta: {"ok": true, "estado": "...", "ventilador": 1, "ventilador_pct": 70, "vibracion_pct": 50}
void procesarRespuesta(const String& response) {
  if (response.indexOf("\"ventilador_pct\"") < 0) {
    controlLocal(co2);
    return;
  }
  int ventiladorPct = leerEntero(response, "ventilador_pct", 0);
  int vibracionPct = leerEntero(response, "vibracion_pct", 0);
  bool emergencia = response.indexOf("Emergencia") >= 0;
  aplicarActuadores(ventiladorPct, vibracionPct, emergencia);
}

// Consulta el SCD41 sin bloquear; guarda la medición cuando está lista
void leerScd41() {
  if (millis() - lastScdCheck < 500) return;
  lastScdCheck = millis();

  bool lista = false;
  if (scd4x.getDataReadyStatus(lista) != 0 || !lista) return;

  uint16_t co2Raw = 0;
  float t = 0, h = 0;
  if (scd4x.readMeasurement(co2Raw, t, h) != 0 || co2Raw == 0) return;
  co2 = co2Raw;
  temperatura = t;
  humedad = h;
  hayMedicionScd = true;
}

// Debe llamarse en cada vuelta del loop: la detección de latidos necesita muestreo continuo
void leerMax30102() {
  long ir = particleSensor.getIR();

  if (ir < 50000) {  // sin dedo sobre el sensor
    latidosValidos = 0;
    pulso = 0;
    return;
  }

  if (checkForBeat(ir)) {
    unsigned long ahora = millis();
    if (ultimoLatido > 0) {
      float bpm = 60000.0 / (ahora - ultimoLatido);
      if (bpm > 30 && bpm < 220) {
        latidos[latidoIdx] = bpm;
        latidoIdx = (latidoIdx + 1) % PROMEDIO_LATIDOS;
        if (latidosValidos < PROMEDIO_LATIDOS) latidosValidos++;

        float suma = 0;
        for (int i = 0; i < latidosValidos; i++) suma += latidos[i];
        pulso = suma / latidosValidos;
      }
    }
    ultimoLatido = ahora;
  }
}

void setup() {
  Serial.begin(115200);

  // El relé arranca abierto: primero el nivel de apagado y luego el pin como salida
  digitalWrite(PIN_RELE, RELE_ACTIVO_ALTO ? LOW : HIGH);
  pinMode(PIN_RELE, OUTPUT);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pwmInit(PIN_VENTILADOR, CANAL_VENTILADOR);
  pwmInit(PIN_VIBRADOR, CANAL_VIBRADOR);
  aplicarActuadores(0, 0, false);

  Wire.begin();

  // SCD41 en medición periódica (una lectura cada ~5 s)
  scd4x.begin(Wire, SCD41_I2C_ADDR_62);
  scd4x.wakeUp();
  scd4x.stopPeriodicMeasurement();
  scd4x.reinit();
  if (scd4x.startPeriodicMeasurement() != 0) {
    Serial.println("Error iniciando el SCD41");
  }

  // MAX30102: LED rojo bajo, sin LED verde (solo hace falta rojo + IR)
  if (!particleSensor.begin(Wire, I2C_SPEED_FAST)) {
    Serial.println("No se encontró el MAX30102");
  } else {
    particleSensor.setup();
    particleSensor.setPulseAmplitudeRed(0x0A);
    particleSensor.setPulseAmplitudeGreen(0);
  }

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
  leerMax30102();
  leerScd41();

  // Enviar datos cada 5 segundos
  if ((millis() - lastTime) > timerDelay) {
    lastTime = millis();

    if (!hayMedicionScd) {
      Serial.println("Aún no hay medición del SCD41, lectura omitida");
      return;
    }

    if (WiFi.status() != WL_CONNECTED) {
      Serial.println("Wi-Fi desconectado, control local");
      controlLocal(co2);
      WiFi.reconnect();
      return;
    }

    HTTPClient http;
    http.begin(serverUrl);
    http.addHeader("Content-Type", "application/json");
    http.setTimeout(3000);  // sin respuesta en 3 s -> control local

    // Pulso 0 = sin dedo en el MAX30102
    String jsonPayload = "{";
    jsonPayload += "\"co2\":" + String(co2) + ",";
    jsonPayload += "\"temp\":" + String(temperatura) + ",";
    jsonPayload += "\"hum\":" + String(humedad) + ",";
    jsonPayload += "\"pulso\":" + String(pulso);  // el operador lo asigna el servidor
    jsonPayload += "}";

    Serial.print("Enviando JSON: ");
    Serial.println(jsonPayload);

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
      controlLocal(co2);
    }

    http.end();
  }
}
