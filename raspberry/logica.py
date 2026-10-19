from ia.predictor import SIMVAPredictor

predictor = SIMVAPredictor()

def decidir_estado(co2, historial_co2=None, temp=25, hum=50, pulso=None, pulso_base=70, hora=12, dia_semana=1):
    """
    Normal: CO2 < 1000 ppm. Si el pulso está elevado (>25% sobre su base) pero
            el aire está estable, se queda en Normal (puede ser esfuerzo físico),
            y solo se deja un aviso informativo en msg_ia para el supervisor.
    Alerta: CO2 > 1000 ppm, o la IA predice el umbral en < 5 min.
            Si además el pulso está elevado, se marca como riesgo combinado.
    Emergencia: CO2 > 2000 ppm, o CO2 > 1000 con pulso elevado (> 25% sobre su base).
    """
    historial_co2 = historial_co2 or []

    # 1. Consulta al predictor de IA
    evaluacion_ia = predictor.evaluar(
        hora=hora,
        dia_semana=dia_semana,
        co2_actual=co2,
        historial_co2=historial_co2,
        temp=temp,
        pulso=pulso if pulso else pulso_base,
        umbral=1000
    )

    minutos_a_umbral = evaluacion_ia.get('minutos_estimados_umbral')
    recomendacion_ia = evaluacion_ia.get('recomendacion_ventilacion_ia', False)
    pendiente = evaluacion_ia.get('co2_pendiente_ppm_min', 0.0)

    # 2. Evaluación de pulso
    pulso_alto = pulso is not None and pulso_base and pulso > (pulso_base * 1.25)

    # 3. Lógica de estados
    ia_predice_riesgo = (minutos_a_umbral is not None and minutos_a_umbral < 5) or recomendacion_ia

    if co2 > 2000 or (co2 > 1000 and pulso_alto):
        estado = "Emergencia"
        msg_ia = "Riesgo Crítico de CO2"
    elif co2 > 1000:
        estado = "Alerta"
        msg_ia = "Umbral Rebasado (>1000 ppm)"
    elif ia_predice_riesgo and pulso_alto:
        estado = "Alerta"
        msg_ia = "IA + Pulso: Posible Riesgo Combinado"
    elif ia_predice_riesgo:
        estado = "Alerta"
        msg_ia = f"IA: Ventilación Anticipada (~{minutos_a_umbral if minutos_a_umbral else '<5'} min)"
    elif pulso_alto:
        estado = "Normal"
        msg_ia = "Aviso: Pulso elevado, aire estable (posible esfuerzo físico, sin acción automática)"
    else:
        estado = "Normal"
        msg_ia = "Ambiente Estable (Monitoreando IA)"

    ventilador = 1 if estado in ("Alerta", "Emergencia") else 0

    return {
        "estado": estado,
        "ventilador": ventilador,
        "msg_ia": msg_ia,
        "pendiente": pendiente,
        "minutos_a_umbral": minutos_a_umbral
    }
