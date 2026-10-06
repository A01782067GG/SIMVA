def decidir_estado(co2, pulso=None, pulso_base=None, minutos_a_umbral=None):
    """
    Normal: CO2 < 1000 ppm y pulso dentro de su base
    Alerta: CO2 > 1000 ppm, o la IA predice el umbral en < 5 min, o pulso alto
    Emergencia: CO2 > 2000 ppm, o CO2 > 1000 con pulso elevado (> 25% sobre su base)
    """
    pulso_alto = pulso is not None and pulso_base and pulso > pulso_base * 1.25

    if co2 > 2000 or (co2 > 1000 and pulso_alto):
        estado = "Emergencia"
    elif co2 > 1000 or (minutos_a_umbral is not None and minutos_a_umbral < 5):
        estado = "Alerta"
    elif pulso_alto:
        estado = "Alerta"
    else:
        estado = "Normal"

    ventilador = 1 if estado in ("Alerta", "Emergencia") else 0
    return estado, ventilador
