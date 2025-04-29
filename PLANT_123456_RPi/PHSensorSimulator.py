import random
import math

class PHSensorSimulator:
    """
    Simula el pH del suelo para diferentes tipos de planta, incorporando:
    - Efecto día-noche leve.
    - Deriva hacia el pH base de la planta.
    - Ruido aleatorio.
    - Eventos lógicos de intervención (riego, fertilización) en horas más probables.
    """

    def __init__(self,
                 plant_type: str = "spider plant",
                 fluctuation_std: float = 0.03,
                 base_intervention_chance: float = 0.005):
        """
        :param plant_type:      "cactus", "spider plant" o "peace lily"
        :param fluctuation_std: desviación estándar del ruido (< ±0.1 pH)
        :param base_intervention_chance: probabilidad base por minuto de un evento externo
        """
        self.base_ph                = self._base_ph_for(plant_type)
        self.current_ph             = self.base_ph + random.uniform(-0.2, 0.2)
        self.fluctuation_std        = fluctuation_std
        self.base_intervention_chance = base_intervention_chance
        self.tick                   = 0  # minutos desde medianoche

    def _base_ph_for(self, plant_type: str) -> float:
        mapping = {
            "cactus":      6.0,
            "spider plant":6.5,
            "peace lily":  6.2
        }
        return mapping.get(plant_type.lower(), 6.5)

    def _day_night_effect(self) -> float:
        """
        Ciclo diario: raíces activas de noche tienden a subir pH ligeramente,
        actividad fotosintética de día lo puede bajar.
        Amplitud ~±0.02 pH.
        """
        hour = (self.tick % 1440) / 60  # 0–24
        theta = (hour - 12) / 24 * 2 * math.pi
        return -math.sin(theta) * 0.02

    def _intervention_event(self) -> float:
        """
        Simula fertilización o acumulación de sales tras riego.
        - Intervenciones más probables en franjas 8–10h y 18–20h.
        - Magnitud entre -0.3 y +0.5 pH.
        """
        hour = (self.tick % 1440) / 60
        # Aumentar probabilidad en franjas típicas de intervención
        if 8 <= hour <= 10 or 18 <= hour <= 20:
            chance = self.base_intervention_chance * 3
        else:
            chance = self.base_intervention_chance

        if random.random() < chance:
            # Fertilizante (sube pH) o lavado de sales (baja pH)
            return random.uniform(-0.3, 0.5)
        return 0.0

    def simulate(self) -> float:
        """
        Avanza un minuto y devuelve el pH actual (0.0–14.0).
        """
        self.tick += 1

        # Deriva suave hacia pH base
        drift = (self.base_ph - self.current_ph) * 0.02

        # Ruido natural
        noise = random.gauss(0, self.fluctuation_std)

        # Efecto día-noche
        dn = self._day_night_effect()

        # Eventos externos lógicos
        intervention = self._intervention_event()

        # Calculamos nuevo pH y suavizamos
        target = self.current_ph + drift + noise + dn + intervention
        alpha = 0.85  # suavizado fuerte para evitar saltos bruscos
        self.current_ph = alpha * self.current_ph + (1 - alpha) * target

        # Clamp a rango físico
        self.current_ph = max(0.0, min(14.0, self.current_ph))

        return round(self.current_ph, 2)
