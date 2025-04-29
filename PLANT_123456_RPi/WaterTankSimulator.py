class WaterTankSimulator:
    """
    Simula un tanque de agua con:
    - capacidad en litros.
    - consumo por la bomba.
    - recarga automática (instantánea) si se vacía.
    - callback para publicar porcentaje.
    """

    def __init__(self, capacity_liters: float = 3.0, auto_refill: bool = True):
        self.capacity       = capacity_liters
        self.level          = capacity_liters
        self.auto_refill    = auto_refill
        self.publish_callback = None

    def set_publish_callback(self, callback):
        """
        Registra la función que se llamará al cambiar el nivel (%).
        """
        self.publish_callback = callback

    def consume_liters(self, liters: float) -> float:
        """
        Consume 'liters' del tanque. 
        Devuelve la cantidad realmente extraída.
        Si el tanque se vacía y auto_refill=True, recarga al 100%.
        """
        extracted = min(self.level, liters)
        self.level -= extracted

        if self.level <= 0 and self.auto_refill:
            print("[TANK] 🌀 Tanque vacío. Recargando automáticamente.")
            self.refill()
        else:
            self._publish_percentage()

        return extracted

    def refill(self):
        """
        Recarga instantánea al 100% y publica el nivel.
        """
        self.level = self.capacity
        print("[TANK] 💧 Tanque recargado al 100%.")
        self._publish_percentage()

    def get_percentage(self) -> float:
        """
        Nivel actual en porcentaje (0–100%).
        """
        return round((self.level / self.capacity) * 100, 2)

    def get_level_liters(self) -> float:
        """
        Litros actuales en el tanque.
        """
        return round(self.level, 3)

    def is_empty(self) -> bool:
        return self.level <= 0.0

    def is_low(self, threshold: float = 20.0) -> bool:
        """
        Indica si el nivel está por debajo del umbral (%) dado.
        """
        return self.get_percentage() <= threshold

    def _publish_percentage(self):
        """
        Llama al callback registrado con el nivel (%) actualizado.
        """
        if self.publish_callback:
            self.publish_callback(self.get_percentage())

