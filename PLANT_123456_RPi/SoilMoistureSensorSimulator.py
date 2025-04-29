import random
import math

class SoilMoistureSensorSimulator:
    """
    Simula la humedad del suelo a lo largo de un día de primavera en Europa.
    - Evaporación diaria máxima al mediodía y mínima de noche.
    - Ruido aleatorio pequeño para variaciones naturales.
    - Refrescamiento (irrigación) que aumenta la humedad instantáneamente.
    """

    def __init__(self,
                 plant_type: str = "spider plant",
                 base_noise: float = 0.3):
        """
        :param plant_type:      "cactus", "peace lily" o "spider plant"
        :param base_noise:      ruido uniforme en % de humedad
        """
        # Configuración según tipo de planta
        plant = plant_type.lower()
        if plant == "cactus":
            base       = 25.0 + random.uniform(-3.0, 3.0)
            evap_rate  = 0.02    # % por minuto como base
            irrig_rate = 5.0     # % que aporta una intervención de riego
        elif plant == "peace lily":
            base       = 60.0 + random.uniform(-3.0, 3.0)
            evap_rate  = 0.10
            irrig_rate = 20.0
        else:  # spider plant
            base       = 45.0 + random.uniform(-3.0, 3.0)
            evap_rate  = 0.06
            irrig_rate = 15.0

        self.base_moisture     = base
        self.evaporation_rate  = evap_rate
        self.irrigation_boost  = irrig_rate
        self.noise_level       = base_noise

        self.current_moisture  = base
        self.tick              = 0    # minutos desde medianoche
        self.irrigating        = False

    def _day_night_factor(self) -> float:
        """
        Factor [0,1] para modular la evaporación:
        - Mínimo a las ~0h (factor ≈ 0)
        - Máximo a las ~12h (factor ≈ 1)
        """
        hour = (self.tick % 1440) / 60  # 0–24
        theta = (hour - 6) / 24 * 2 * math.pi
        # seno en [-1,1], lo normalizamos a [0,1]
        return (math.sin(theta) + 1) / 2

    def simulate(self) -> float:
        """
        Avanza un minuto en la simulación y devuelve la humedad actual (%).
        """
        self.tick += 1

        if self.irrigating:
            # Riego: aumenta instantáneamente
            boost = self.irrigation_boost * random.uniform(0.9, 1.1)
            self.current_moisture += boost
            self.irrigating = False
        else:
            # Evaporación modulada por día-noche y ruido
            factor = self._day_night_factor()
            evap   = self.evaporation_rate * factor
            noise  = random.uniform(-self.noise_level, self.noise_level)
            self.current_moisture -= (evap + noise)

        # Clamp a rango realista 5%–100%
        self.current_moisture = max(5.0, min(100.0, self.current_moisture))
        return round(self.current_moisture, 2)

    def trigger_irrigation(self):
        """
        Marca que en el siguiente paso de simulación
        se aplique el boost de riego.
        """
        self.irrigating = True
