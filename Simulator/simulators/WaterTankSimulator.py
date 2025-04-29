# WaterTankSimulator.py
class WaterTankSimulator:
    """
    Simula un tanque de agua con:
    - capacidad en litros.
    - consumo por la bomba.
    - recarga automática (instantánea) si se vacía.
    - callback para publicar porcentaje.
    """

    def __init__(self,
                 capacity_liters: float = None,
                 auto_refill: bool = True):
        """
        :param capacity_liters:   capacidad en litros
                                 (default: env TANK_CAPACITY o 3.0)
        :param auto_refill:       si recarga al vaciarse
        """
        import os
        cap = (capacity_liters
               if capacity_liters is not None
               else float(os.getenv("TANK_CAPACITY", 3.0)))
        self.capacity        = cap
        self.level           = cap
        self.auto_refill     = auto_refill
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
        Si se vacía y auto_refill=True, recarga al 100%.
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
        return round((self.level / self.capacity) * 100, 2)

    def is_empty(self) -> bool:
        return self.level <= 0.0

    def _publish_percentage(self):
        if self.publish_callback:
            self.publish_callback(self.get_percentage())
