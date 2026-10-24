# SIMVA
**Sistema Inteligente de Monitoreo y Ventilación Automática de Calidad del Aire.**

Prototipo del curso *Implementación de Internet de las Cosas* (Tec de Monterrey, Campus Guadalajara, Gpo 503). Mide CO₂, temperatura, humedad y frecuencia cardiaca, decide un estado (Normal / Alerta / Emergencia) con apoyo de un módulo de IA y activa ventilación y alertas. Los datos se guardan en SQLite y se muestran en un dashboard web.

**Objetivo (Project Charter):** antes del **3 de diciembre de 2026**, registrar datos cada ≤ 5 s y activar ventilador y LED en ≤ 5 s tras superar el umbral de CO₂ (1000 ppm), con diferencia ≤ 15 % frente a un monitor de referencia.

> **Cambios recientes, cómo probar el código, pendientes y preguntas abiertas:** ver [`CAMBIOS_Y_PRUEBAS.md`](CAMBIOS_Y_PRUEBAS.md).

## Equipo
| Persona | Rol |
|---|---|
| Iván García Garza | Líder de proyecto, planeación y cronograma |
| Ingrid Araceli Domínguez Castillo | Hardware, adquisición y circuito de potencia |
| Leonardo Nájera Sandoval | ESP32, sensores, integración, interfaz y lógica de control |
| Edgar Esquivel Contreras | Servidor, base de datos, API y módulo de IA |
| Mauricio Alejandro Domínguez Ramírez | Documentación, pruebas y reporte |

## Arquitectura

```
SCD41 (CO₂/temp/hum) ─┐  I²C
MAX30102 (pulso) ─────┴─► ESP32 ──(WiFi, POST /lectura cada 5 s)──► Raspberry Pi 4
                           │  ▲                                      CherryPy + SQLite + IA
   PWM: ventilador (D4184) │  └── respuesta: estado + niveles ──────────┘
        vibrador, LED, buzzer                                              │
                                       Dashboard web (interfaz/) ◄─────────┘ GET /estado, /ultimas
```

### Hardware (listado final confirmado)
| Grupo | Componentes |
|---|---|
| Control y procesamiento | ESP32 (lógica de control y PWM), Raspberry Pi 4 de 4 GB (servidor), microSD |
| Sensores | SCD41 (CO₂, temperatura y humedad), MAX30102 (frecuencia cardiaca) |
| Actuadores | Ventilador Steren 12 V, módulo D4184 (PWM del ventilador), módulo vibratorio 5 V (intensidad regulable), LED, buzzer activo |
| Alimentación | Fuente de 12 V (ventilador) y fuente de 5 V (módulo vibratorio) |
| Montaje | Protoboard, jumpers, resistencias, diodos 1N5819 (protección del circuito de potencia) |

El relé aparece en la lista original pero el D4184 ya conmuta y regula el ventilador, así que el firmware no lo usa.

El ESP32 mide, manda la lectura y aplica los niveles que devuelve el servidor. Si no hay WiFi o el servidor no responde en 3 s, aplica las mismas reglas con el CO₂ local (`controlLocal()`).

## Estructura del repositorio

| Carpeta | Contenido |
|---|---|
| `esp32/` | `main_esp32.ino`: conecta por WiFi, lee el SCD41 y el MAX30102 por I²C (SDA 21, SCL 22), envía un JSON cada 5 s a `http://<IP_RPI>:8080/lectura` y aplica por PWM los niveles de ventilador y vibración que devuelve el servidor, más LED y buzzer. Pulso `0` significa que el MAX30102 no detecta el dedo. |
| `raspberry/` | `servidor.py` (API + servidor del dashboard), `logica.py` (estados), `ia/` (modelo), `requirements.txt`. |
| `interfaz/` | `index.html` (dashboard con Chart.js) y `manifest.json` (PWA). |
| `docs/` | Project Charter + WBS (PDF), Plan de Gestión de Riesgos (xlsx), Plan de RH: matriz de habilidades y RACI (docx). |

### `raspberry/`
- **`servidor.py`** (puerto **8080**, `0.0.0.0`). Base SQLite `lecturas.db` (se crea sola), tabla `lecturas(id, fecha, co2, temp, hum, pulso, operador)`. Sirve también `interfaz/` como sitio estático en `/`. Endpoints:
  - `POST /lectura`: JSON `{"co2", "temp", "hum", "pulso", "operador"}` (`operador` opcional: si falta se usa el activo); guarda y responde `{"ok": true, "estado", "ventilador": 0|1, "ventilador_pct": 0-100, "vibracion_pct": 0-100}`. El ESP32 usa la respuesta para accionar ventilador y vibrador por PWM, LED y buzzer.
  - `POST /operador`: JSON `{"operador": "ivan"}`; fija el operador que se asigna a las lecturas que no traen uno (lo llama el dashboard al cambiar el selector).
  - `GET /ultimas?n=20`: últimas N lecturas.
  - `GET /estado`: última lectura + evaluación: `{estado, temp, hum, co2, pulso, vent: "ON"|"OFF", ia_status, pendiente}`.
- **`logica.py`**: `decidir_estado()` consulta al predictor y aplica:
  - **Emergencia**: CO₂ > 2000 ppm, o CO₂ > 1000 con pulso > 25 % sobre su base (70 bpm).
  - **Alerta**: CO₂ > 1000 ppm, o la IA predice llegar al umbral en < 5 min (con aviso de riesgo combinado si el pulso también está alto).
  - **Normal**: el resto; un pulso alto con aire estable solo genera un aviso informativo (posible esfuerzo físico).
  - **Ventilador** proporcional al CO₂: 40 % en 1000 ppm hasta 100 % en 2000 ppm; 100 % en Emergencia; 30 % si la IA anticipa el umbral aún bajo 1000 ppm; 0 % en Normal.
  - **Módulo vibratorio**: 0 % en Normal, 50 % en Alerta, 100 % en Emergencia. **Buzzer**: solo en Emergencia. **LED**: encendido en Alerta y Emergencia.
- **`ia/train.py`**: genera datos sintéticos y entrena un `DecisionTreeClassifier` (features: hora, día, CO₂, pendiente, temperatura, pulso) guardado en `ia/models/co2_model.joblib`. **`ia/predictor.py`** debe exponer `SIMVAPredictor.evaluar(...)`, que devuelve `minutos_estimados_umbral`, `recomendacion_ventilacion_ia` y `co2_pendiente_ppm_min`.

### `interfaz/`
Dashboard oscuro con tarjetas (temperatura, humedad, CO₂, pulso, ventilación, diagnóstico IA), selector de operador (Iván, Ingrid, Edgar, Leonardo) y gráfica de CO₂ en tiempo real, actualizado cada 3 s. Si el backend no responde, cae a **datos simulados** sin avisar.

## Puesta en marcha

```bash
cd raspberry
pip install -r requirements.txt
python ia/train.py        # genera el modelo (una vez)
python servidor.py        # dashboard en http://localhost:8080
```

Probar la API:
```bash
curl -X POST http://localhost:8080/lectura -H "Content-Type: application/json" \
  -d '{"co2": 1200, "temp": 24.5, "hum": 55, "pulso": 80, "operador": "ivan"}'
curl http://localhost:8080/estado
```

**ESP32:** abrir `esp32/main_esp32.ino` en Arduino IDE, instalar las librerías *Sensirion I2C SCD4x* y *SparkFun MAX3010x Pulse and Proximity Sensor Library*, poner `ssid`, `password` y la IP de la Raspberry en `serverUrl`, cargar y abrir el Monitor Serial a 115200.

## Problemas conocidos (a resolver)
- Sin `python ia/train.py` el predictor funciona solo con la regla de pendiente (el servidor lo avisa al arrancar).
- Los pines de ventilador (26), vibrador (27), LED (25) y buzzer (33) en `main_esp32.ino` son provisionales y el firmware nuevo no se ha compilado ni probado en hardware.
- El dashboard carga Chart.js desde un CDN (requiere internet).
- `manifest.json` ya no declara íconos; falta crear un `icon.png` para que la PWA sea instalable.
- Los endpoints de la versión anterior (`/enviar_lectura`, `/datos_actuales`, `/historial`) y `app.py`/`database.py` ya no existen.

## Comentarios para el equipo
Cosas que hay que revisar o confirmar antes de seguir (cambios del 19 oct 2026):
- **Pines del ESP32:** `main_esp32.ino` usa PWM del ventilador en GPIO 26, vibrador en 27, LED en 25 y buzzer en 33 como valores provisionales (I²C en 21/22). Confirmar con el circuito de potencia de Ingrid y ajustar si es distinto.
- **Sin compilar ni probar:** el firmware (SCD41, MAX30102, PWM, respaldo local) se escribió sin compilar ni probar en el ESP32. Revisar sobre todo la API de las librerías según su versión y que el PWM use `ledcAttach` (core 3.x) o `ledcSetup` (core 2.x); el código acepta ambos. Lo que sí se probó es la lógica de `logica.py` (niveles por CO₂ y estado).
- **Frecuencia PWM y módulos:** se usan 5 kHz; verificar con el D4184, el ventilador Steren y el módulo vibratorio (si hacen ruido o no responden, probar otra frecuencia). Confirmar si el módulo vibratorio recibe PWM directo por su pin de señal.
- **Circuito de potencia:** unir las tierras (GND) de las fuentes de 12 V y 5 V con la del ESP32, y poner los diodos 1N5819 en antiparalelo con el ventilador y el vibrador si sus módulos no los traen. Resistencia en serie para el LED.
- **Relé:** no se usa en el firmware. Si el equipo lo quiere mantener como corte de seguridad, definir su pin y regla.
- **Documentación pendiente (`docs/`):** el Charter, el plan de riesgos (PRR 2 habla de un relé con optoacoplador) y el presupuesto no incluyen D4184, módulo vibratorio, fuente de 5 V ni diodos. Falta el diagrama de conexiones y el AM2302 ya no forma parte del proyecto.
- **Selector de operador:** falta Mauricio en la lista del dashboard.
- **Pulso `0`:** el ESP32 manda 0 cuando no hay dedo en el MAX30102; la lógica lo toma como pulso base (70) y el dashboard muestra `--`.
- **Dashboard sin probar en navegador:** la tarjeta de Estado, el envío del operador y el aviso de datos simulados hay que verlos funcionando.
- **Operador:** ahora lo fija el dashboard con `POST /operador` y es global (el último que cambió el selector). Si hay varias personas con el dashboard abierto, gana la última. ¿Es suficiente para la demo?
- **Ícono de la PWA:** se quitó la referencia a `icon.png` del manifest; si se quiere instalar como app hay que crear el ícono y volver a declararlo.
- **Chart.js por CDN:** si la Raspberry no tendrá internet en la demo, descargar Chart.js y servirlo desde `interfaz/`.
- **Modelo de IA:** `ia/models/co2_model.joblib` no está en el repo; cada quien debe correr `python ia/train.py`. Sin él funciona solo la regla de pendiente. El modelo actual se entrena con datos sintéticos.

## Pendientes del proyecto
- Probar en hardware el firmware que ya integra SCD41 y MAX30102 (calibrar CO₂ y validar el pulso).
- Circuito de potencia: armar D4184 + ventilador, módulo vibratorio, LED y buzzer, y probar el control por PWM.
- Entrenar el modelo con datos reales de la base de datos (hoy usa datos sintéticos).
- Histórico y registro visible de anomalías en la interfaz.
- Pruebas integrales (exhalación en caja cerrada, tiempo de respuesta ≤ 5 s) y validación contra el monitor de referencia.
- Documentación final y demostración (3 dic 2026).
