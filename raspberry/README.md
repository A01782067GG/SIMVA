# Servidor CherryPy, base de datos e IA

| Archivo | Función |
|---|---|
| `servidor.py` | API (`/lectura`, `/estado`, `/ultimas`, `/operador`) y servidor del dashboard en el puerto 8080. Crea `lecturas.db` (SQLite) al arrancar. |
| `logica.py` | `decidir_estado()`: estado (Normal / Alerta / Emergencia), ventilador proporcional al CO₂ y vibración. |
| `ia/train.py` | Entrena el modelo (datos sintéticos) y lo guarda en `ia/models/` (ignorado por git). |
| `ia/predictor.py` | `SIMVAPredictor`: pendiente de CO₂, minutos al umbral y recomendación del modelo. |

```bash
pip install -r requirements.txt
python ia/train.py
python servidor.py
```

Detalle de la API y las reglas en el `README.md` principal; instrucciones de prueba en `../CAMBIOS_Y_PRUEBAS.md`.
