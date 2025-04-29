import os
import random
import math

class TemperatureSensorSimulator:
    """
    Simula la temperatura ambiente a lo largo de un día.
    Parámetros configurables vía ENV:
      - TEMP_BASE         (float): temperatura media diaria (°C), default 15.0
      - TEMP_DAY_AMPL     (float): amplitud de variación diaria (°C), default 8.0
      - TEMP_NOISE_STD    (float): desviación estándar del ruido (°C), default 0.5
      - TEMP_ALPHA        (float): factor de suavizado exponencial (0–1), default 0.9
      - TEMP_PEAK_HOUR    (float): hora del máximo térmico, default 15.0
      - TEMP_MIN_HOUR     (float): hora del mínimo térmico, default 4.0
    """

    def __init__(self):
        # Leer parámetros desde ENV o usar valores por defecto
        self.base_temp = float(os.getenv("TEMP_BASE", 15.0))
        self.day_amplitude = float(os.getenv("TEMP_DAY_AMPL", 8.0))
        self.noise_std = float(os.getenv("TEMP_NOISE_STD", 0.5))
        self.alpha = float(os.getenv("TEMP_ALPHA", 0.9))
        self.peak_hour = float(os.getenv("TEMP_PEAK_HOUR", 15.0))
        self.min_hour = float(os.getenv("TEMP_MIN_HOUR", 4.0))

        self.current_temp = self.base_temp
        self.tick = 0  # minutos desde medianoche

    def _day_night_variation(self) -> float:
        """
        Calcula la variación temperatura según ciclo sinusoidal:
        - Mínimo alrededor de min_hour
        - Máximo alrededor de peak_hour
        """
        hour = (self.tick % 1440) / 60  # convierte minutos a [0,24)
        # Ajustar desfase para mínimo y máximo
        # Convertir a fase: shift = (min_hour + peak_hour)/2
        shift = (self.min_hour + self.peak_hour) / 2
        theta = (hour - shift) / 24 * 2 * math.pi
        return math.sin(theta) * (self.day_amplitude / 2)

    def simulate(self) -> float:
        """
        Avanza un minuto y devuelve la temperatura actual (°C).
        """
        self.tick += 1
        variation = self._day_night_variation()
        noise = random.gauss(0, self.noise_std)
        target_temp = self.base_temp + variation + noise

        # Suavizado exponencial
        self.current_temp = (
            self.alpha * self.current_temp +
            (1 - self.alpha) * target_temp
        )
        return round(self.current_temp, 2)
