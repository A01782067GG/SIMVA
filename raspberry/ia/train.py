import os
import pandas as pd
import numpy as np
from sklearn.tree import DecisionTreeClassifier
import joblib

# Ruta donde se guardara el modelo entrenado
MODEL_PATH = os.path.join(os.path.dirname(__file__), 'models', 'co2_model.joblib')

def generar_datos_y_entrenar():
    # Crear carpeta models si no existe
    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    
    np.random.seed(42)
    n = 1000
    
    # Simulacion de datos historicos guardados en SQLite
    data = {
        'hora': np.random.randint(8, 20, size=n),
        'dia_semana': np.random.randint(0, 5, size=n),
        'co2_actual': np.random.uniform(400, 1500, size=n),
        'co2_pendiente': np.random.uniform(-5, 25, size=n),
        'temperatura': np.random.uniform(20, 30, size=n),
        'pulso': np.random.uniform(60, 110, size=n),
    }
    
    df = pd.DataFrame(data)
    
    # Etiqueta: Decision de ventilacion inteligente
    y = ((df['co2_actual'] > 900) | ((df['co2_actual'] > 750) & (df['co2_pendiente'] > 10))).astype(int)
    
    X = df[['hora', 'dia_semana', 'co2_actual', 'co2_pendiente', 'temperatura', 'pulso']]
    
    # Modelo
    model = DecisionTreeClassifier(max_depth=4)
    model.fit(X, y)
    
    # Guardar binario del modelo
    joblib.dump(model, MODEL_PATH)
    print(f"Modelo guardado exitosamente en: {MODEL_PATH}")

if __name__ == '__main__':
    generar_datos_y_entrenar()
