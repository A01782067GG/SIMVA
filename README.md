# SIMVA
**Sistema Inteligente de Monitoreo y Ventilación Automática de Calidad del Aire.**

Prototipo del curso *Implementación de Internet de las Cosas* (Tec de Monterrey, Campus Guadalajara, Gpo 503). Mide CO₂, temperatura, humedad y frecuencia cardiaca, decide un estado (Normal / Alerta / Emergencia) con apoyo de un módulo de IA y activa ventilación y alertas. Los datos se guardan en SQLite y se muestran en un dashboard web.

**Objetivo (Project Charter):** antes del **3 de diciembre de 2026**, registrar datos cada ≤ 5 s y activar ventilador y LED en ≤ 5 s tras superar el umbral de CO₂ (1000 ppm), con diferencia ≤ 15 % frente a un monitor de referencia.

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
SCD41 (CO₂/temp/hum) ─┐
MAX30102 (pulso) ─────┼─► ESP32 ──(WiFi, POST /lectura cada 5 s)──► Raspberry Pi 4
AM2302 (temp/hum) ────┘                                              CherryPy + SQLite + IA
                                                                          │
                                       Dashboard web (interfaz/) ◄────────┘ GET /estado, /ultimas
```

Hardware planeado: ESP32, Raspberry Pi 4, SCD41, MAX30102, relé, ventilador 12 V, LED y buzzer. Hoy el firmware solo lee el AM2302; CO₂ y pulso están simulados.

## Estructura del repositorio

| Carpeta | Contenido |
|---|---|
| `esp32/` | `main_esp32.ino`: conecta por WiFi, lee el AM2302 (DHT22, pin 4) y envía un JSON cada 5 s a `http://<IP_RPI>:8080/lectura`. CO₂ y pulso son `random()` hasta integrar el SCD41 y el MAX30102. `leer_am2302.ino`: sketch de prueba que solo imprime temperatura y humedad por Serial. |
| `raspberry/` | `servidor.py` (API + servidor del dashboard), `logica.py` (estados), `ia/` (modelo), `requirements.txt`. |
| `interfaz/` | `index.html` (dashboard con Chart.js) y `manifest.json` (PWA). |
| `docs/` | Project Charter + WBS (PDF), Plan de Gestión de Riesgos (xlsx), Plan de RH: matriz de habilidades y RACI (docx). |

### `raspberry/`
- **`servidor.py`** (puerto **8080**, `0.0.0.0`). Base SQLite `lecturas.db` (se crea sola), tabla `lecturas(id, fecha, co2, temp, hum, pulso, operador)`. Sirve también `interfaz/` como sitio estático en `/`. Endpoints:
  - `POST /lectura`: JSON `{"co2", "temp", "hum", "pulso", "operador"}` (`operador` opcional: si falta se usa el activo); guarda y responde `{"ok": true, "estado", "ventilador": 0|1}`. El ESP32 usa la respuesta para accionar relé, LED y buzzer.
  - `POST /operador`: JSON `{"operador": "ivan"}`; fija el operador que se asigna a las lecturas que no traen uno (lo llama el dashboard al cambiar el selector).
  - `GET /ultimas?n=20`: últimas N lecturas.
  - `GET /estado`: última lectura + evaluación: `{estado, temp, hum, co2, pulso, vent: "ON"|"OFF", ia_status, pendiente}`.
- **`logica.py`**: `decidir_estado()` consulta al predictor y aplica:
  - **Emergencia**: CO₂ > 2000 ppm, o CO₂ > 1000 con pulso > 25 % sobre su base (70 bpm).
  - **Alerta**: CO₂ > 1000 ppm, o la IA predice llegar al umbral en < 5 min (con aviso de riesgo combinado si el pulso también está alto).
  - **Normal**: el resto; un pulso alto con aire estable solo genera un aviso informativo (posible esfuerzo físico).
  - Ventilador encendido en Alerta y Emergencia.
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

**ESP32:** abrir `esp32/main_esp32.ino` en Arduino IDE, instalar *DHT sensor library* (Adafruit), poner `ssid`, `password` y la IP de la Raspberry en `serverUrl`, cargar y abrir el Monitor Serial a 115200.

## Problemas conocidos (a resolver)
- Sin `python ia/train.py` el predictor funciona solo con la regla de pendiente (el servidor lo avisa al arrancar).
- Los pines del relé (26), LED (25) y buzzer (27) en `main_esp32.ino` son provisionales y el código del actuador no se ha probado en hardware.
- El dashboard carga Chart.js desde un CDN (requiere internet).
- `manifest.json` ya no declara íconos; falta crear un `icon.png` para que la PWA sea instalable.
- Los endpoints de la versión anterior (`/enviar_lectura`, `/datos_actuales`, `/historial`) y `app.py`/`database.py` ya no existen.

## Comentarios para el equipo
Cosas que hay que revisar o confirmar antes de seguir (cambios del 19 oct 2026):
- **Pines del ESP32:** `main_esp32.ino` usa relé en GPIO 26, LED en 25 y buzzer en 27 como valores provisionales. Confirmar con el circuito de potencia de Ingrid y ajustar si es distinto.
- **Nivel del relé:** el código lo asume activo en HIGH. Si el módulo es activo en LOW hay que invertir los niveles en `aplicarActuadores()`.
- **Sin probar en hardware:** el control de relé/LED/buzzer y la lectura de la respuesta del servidor (`procesarRespuesta`) no se han compilado ni probado en el ESP32. Lo que sí se probó con `curl` es la API: `/operador`, `/lectura` (devuelve `estado` y `ventilador`), `/estado` y `/ultimas`.
- **Dashboard sin probar en navegador:** la tarjeta de Estado, el envío del operador y el aviso de datos simulados hay que verlos funcionando.
- **Operador:** ahora lo fija el dashboard con `POST /operador` y es global (el último que cambió el selector). Si hay varias personas con el dashboard abierto, gana la última. ¿Es suficiente para la demo?
- **Ícono de la PWA:** se quitó la referencia a `icon.png` del manifest; si se quiere instalar como app hay que crear el ícono y volver a declararlo.
- **Chart.js por CDN:** si la Raspberry no tendrá internet en la demo, descargar Chart.js y servirlo desde `interfaz/`.
- **Modelo de IA:** `ia/models/co2_model.joblib` no está en el repo; cada quien debe correr `python ia/train.py`. Sin él funciona solo la regla de pendiente. El modelo actual se entrena con datos sintéticos.

## Pendientes del proyecto
- Integrar SCD41 (CO₂) y MAX30102 (pulso) en el firmware; quitar los `random()`.
- Circuito de potencia: armar relé, ventilador, LED y buzzer y probar el código del ESP32 que ya los controla.
- Entrenar el modelo con datos reales de la base de datos (hoy usa datos sintéticos).
- Histórico y registro visible de anomalías en la interfaz.
- Pruebas integrales (exhalación en caja cerrada, tiempo de respuesta ≤ 5 s) y validación contra el monitor de referencia.
- Documentación final y demostración (3 dic 2026).
