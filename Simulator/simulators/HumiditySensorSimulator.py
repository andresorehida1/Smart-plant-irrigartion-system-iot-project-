import os
import random
import math

class HumiditySensorSimulator:

    def __init__(self):
        # Leer parámetros desde ENV (o usar valores por defecto)
        self.base_humidity    = float(os.getenv("HUM_BASE",      60.0))
        self.day_amplitude    = float(os.getenv("HUM_DAY_AMPL",  20.0))
        self.noise_std        = float(os.getenv("HUM_NOISE_STD",   2.0))
        self.alpha            = float(os.getenv("HUM_ALPHA",      0.9))

        self.current_humidity = self.base_humidity
        self.tick             = 0  # minutos desde medianoche

    def _day_night_variation(self) -> float:
        hour = (self.tick % 1440) / 60  # convierte minutos a [0,24)
        theta = (hour - 4) / 24 * 2 * math.pi
        # Negamos el seno para invertir el pico (humedad alta de noche)
        return -math.sin(theta) * (self.day_amplitude / 2)

    def simulate(self) -> float:
        self.tick += 1
        variation = self._day_night_variation()
        noise     = random.gauss(0, self.noise_std)
        target    = self.base_humidity + variation + noise

        # Suavizado exponencial
        self.current_humidity = (
            self.alpha * self.current_humidity +
            (1 - self.alpha) * target
        )
        # Limitar a rango realista
        self.current_humidity = max(20.0, min(self.current_humidity, 90.0))
        return round(self.current_humidity, 2)
