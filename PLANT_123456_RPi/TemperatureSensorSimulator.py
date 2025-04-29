import random
import math

class TemperatureSensorSimulator:
    """
    Simula la temperatura ambiente a lo largo de un día de primavera en Europa.
    - Efecto día-noche con ciclo sinusoidal: mínimo ~4 h, máximo ~15 h.
    - Ruido gaussiano pequeño y suavizado exponencial.
    """

    def __init__(self,
                 base_temp: float = 15.0,
                 day_amplitude: float = 8.0,
                 noise_std: float = 0.5):
        """
        :param base_temp: temperatura media diaria (°C), p. ej. 15°C en primavera.
        :param day_amplitude: amplitud de variación diaria (°C pico a valle), p. ej. ±8°C.
        :param noise_std: desviación estándar del ruido aleatorio (°C).
        """
        # Estado interno
        self.base_temp      = base_temp
        self.day_amplitude  = day_amplitude
        self.noise_std      = noise_std
        self.current_temp   = base_temp
        self.tick           = 0  # minutos desde medianoche

    def _day_night_variation(self) -> float:
        """
        Calcula la variación por hora según un ciclo sinusoidal:
        - Mínimo a las ~4:00, máximo a las ~15:00.
        """
        hour = (self.tick % 1440) / 60  # convierte minutos a [0,24)
        # Desfase para que sin(0) en 4h y sin(pi/2) en 16h:
        # usamos sin((hour - 4)/24*2π)
        theta = (hour - 4) / 24 * 2 * math.pi
        return math.sin(theta) * (self.day_amplitude / 2)

    def simulate(self) -> float:
        """
        Avanza un minuto en la simulación y devuelve la temperatura actual (°C).
        """
        # Avanzamos el tiempo
        self.tick += 1

        # Efecto día-noche
        variation = self._day_night_variation()

        # Ruido aleatorio
        noise = random.gauss(0, self.noise_std)

        # Suavizado exponencial para evitar saltos bruscos
        alpha = 0.9
        target_temp = self.base_temp + variation + noise

        # Actualiza el estado
        self.current_temp = alpha * self.current_temp + (1 - alpha) * target_temp

        return round(self.current_temp, 2)
