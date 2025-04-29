import random
import math

class HumiditySensorSimulator:
    """
    Simula la humedad relativa a lo largo de un día de primavera en Europa.
    - Humedad máxima (pico) alrededor de las 4 h y mínima cerca de las 15 h.
    - Amplitud de variación diurna controlable (por defecto ±10 %).
    - Ruido gaussiano para pequeños vaivenes naturales.
    - Suavizado exponencial para evitar saltos bruscos.
    """

    def __init__(self,
                 base_humidity: float = 60.0,
                 day_amplitude: float = 20.0,
                 noise_std: float = 2.0):
        """
        :param base_humidity: humedad media diaria (%) — p. ej. 60 % en primavera.
        :param day_amplitude: amplitud pico-a-valle (%) — p. ej. 20 %, para variar entre 50 % y 70 %.
        :param noise_std:    desviación estándar del ruido gaussiano (%).
        """
        self.base_humidity    = base_humidity
        self.day_amplitude    = day_amplitude
        self.noise_std        = noise_std
        self.current_humidity = base_humidity
        self.tick             = 0  # minutos desde medianoche

    def _day_night_variation(self) -> float:
        """
        Calcula la variación debida al ciclo día-noche usando un seno desplazado:
        - Máximo de humedad alrededor de las 4 h (sin(0) → 0, pero el desplazamiento lo ajusta).
        - Mínimo alrededor de las 15 h.
        """
        hour = (self.tick % 1440) / 60  # convierte minutos a [0,24)
        theta = (hour - 4) / 24 * 2 * math.pi
        # Negamos el seno para invertir el pico (humedad alta de noche)
        return -math.sin(theta) * (self.day_amplitude / 2)

    def simulate(self) -> float:
        """
        Avanza un minuto en la simulación y devuelve la humedad actual (%).
        """
        self.tick += 1

        # Efecto día-noche + ruido
        variation = self._day_night_variation()
        noise     = random.gauss(0, self.noise_std)

        # Temperatura objetivo para este paso
        target = self.base_humidity + variation + noise

        # Suavizado exponencial (alpha alto = más inercia)
        alpha = 0.9
        self.current_humidity = alpha * self.current_humidity + (1 - alpha) * target

        # Limitar a un rango realista (20 %–90 %)
        self.current_humidity = max(20.0, min(self.current_humidity, 90.0))

        return round(self.current_humidity, 2)
