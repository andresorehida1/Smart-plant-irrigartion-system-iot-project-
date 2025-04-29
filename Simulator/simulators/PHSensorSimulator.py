import os
import random
import math

class PHSensorSimulator:
    """
    Simula el pH del suelo para diferentes tipos de planta.
    Ahora acepta plant_type directamente en el constructor.
    Parámetros:
      - plant_type (str): "cactus", "spider plant" o "peace lily"
      - fluctuation_std (float, opcional): desviación estándar del ruido (override env PH_FLUCT_STD)
      - base_intervention_chance (float, opcional): probabilidad base (override env PH_BASE_INTERV)
      - day_effect_ampl (float, opcional): amplitud ciclo día-noche (override env PH_DAY_EFFECT_AMPL)
      - alpha (float, opcional): factor de suavizado (override env PH_ALPHA)
    """

    def __init__(self,
                 plant_type: str = "spider plant",
                 fluctuation_std: float = None,
                 base_intervention_chance: float = None,
                 day_effect_ampl: float = None,
                 alpha: float = None):
        # Parámetros de ruido e intervención
        self.fluctuation_std = (fluctuation_std
                                if fluctuation_std is not None
                                else float(os.getenv("PH_FLUCT_STD", 0.03)))
        self.base_interv_chance = (base_intervention_chance
                                   if base_intervention_chance is not None
                                   else float(os.getenv("PH_BASE_INTERV", 0.005)))
        self.day_effect_ampl = (day_effect_ampl
                                if day_effect_ampl is not None
                                else float(os.getenv("PH_DAY_EFFECT_AMPL", 0.02)))
        self.alpha = (alpha
                      if alpha is not None
                      else float(os.getenv("PH_ALPHA", 0.85)))

        # pH base según tipo de planta
        base_map = {
            "cactus":       6.0,
            "spider plant": 6.5,
            "peace lily":   6.2
        }
        self.base_ph    = base_map.get(plant_type.lower(), 6.5)
        self.current_ph = self.base_ph + random.uniform(-0.2, 0.2)
        self.tick       = 0

    def _day_night_effect(self) -> float:
        hour = (self.tick % 1440) / 60
        theta = (hour - 12) / 24 * 2 * math.pi
        return -math.sin(theta) * self.day_effect_ampl

    def _intervention_event(self) -> float:
        hour = (self.tick % 1440) / 60
        chance = (self.base_interv_chance * 3
                  if 8 <= hour <= 10 or 18 <= hour <= 20
                  else self.base_interv_chance)
        return random.uniform(-0.3, 0.5) if random.random() < chance else 0.0

    def simulate(self) -> float:
        self.tick += 1
        drift = (self.base_ph - self.current_ph) * 0.02
        noise = random.gauss(0, self.fluctuation_std)
        dn    = self._day_night_effect()
        inter = self._intervention_event()

        target = self.current_ph + drift + noise + dn + inter
        self.current_ph = self.alpha * self.current_ph + (1 - self.alpha) * target
        self.current_ph = max(0.0, min(14.0, self.current_ph))
        return round(self.current_ph, 2)