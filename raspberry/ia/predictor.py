import os

try:
    import joblib
except ImportError:  # el predictor sigue funcionando solo con la regla de pendiente
    joblib = None

MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'co2_model.joblib')
FEATURES = ['hora', 'dia_semana', 'co2_actual', 'co2_pendiente', 'temperatura', 'pulso']

# El ESP32 envia una lectura cada 5 s -> 12 lecturas por minuto
LECTURAS_POR_MIN = 12


class SIMVAPredictor:
    def __init__(self, model_path=MODEL_PATH):
        self.model = None
        if joblib is not None and os.path.exists(model_path):
            try:
                self.model = joblib.load(model_path)
            except Exception as e:
                print(f"[SIMVAPredictor] No se pudo cargar el modelo: {e}")
        else:
            print("[SIMVAPredictor] Modelo no encontrado, se usa solo la regla de pendiente "
                  "(ejecuta python ia/train.py)")

    @staticmethod
    def _pendiente_ppm_min(historial_co2):
        """Pendiente de regresion lineal del historial (ppm/min), 0.0 si hay pocos datos."""
        h = [x for x in (historial_co2 or []) if x is not None]
        n = len(h)
        if n < 2:
            return 0.0
        xm = (n - 1) / 2
        ym = sum(h) / n
        den = sum((i - xm) ** 2 for i in range(n))
        por_lectura = sum((i - xm) * (y - ym) for i, y in enumerate(h)) / den
        return por_lectura * LECTURAS_POR_MIN

    def evaluar(self, hora, dia_semana, co2_actual, historial_co2, temp, pulso, umbral=1000):
        pendiente = self._pendiente_ppm_min(historial_co2)

        # Minutos estimados para llegar al umbral si la tendencia continua
        minutos = None
        if co2_actual >= umbral:
            minutos = 0.0
        elif pendiente > 0.1:
            minutos = round((umbral - co2_actual) / pendiente, 1)

        recomendacion = False
        if self.model is not None:
            try:
                x = [[hora, dia_semana, co2_actual, pendiente, temp, pulso]]
                try:
                    import pandas as pd
                    x = pd.DataFrame(x, columns=FEATURES)
                except ImportError:
                    pass
                recomendacion = bool(self.model.predict(x)[0])
            except Exception as e:
                print(f"[SIMVAPredictor] Error en prediccion: {e}")

        return {
            'minutos_estimados_umbral': minutos,
            'recomendacion_ventilacion_ia': recomendacion,
            'co2_pendiente_ppm_min': round(pendiente, 2),
        }
