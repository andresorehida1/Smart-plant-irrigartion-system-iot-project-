import random

class WaterPumpSimulator:
    """
    Simula una bomba de riego con un caudal constante.
    - flow_rate_l_per_tick: litros bombeados por tick de simulación.
    - turn_on(duration): enciende la bomba durante 'duration' ticks.
    - tick(): extrae agua del tanque cada tick si está encendida.
    """

    def __init__(self, flow_rate_l_per_tick: float = 0.1):
        self.flow_rate             = flow_rate_l_per_tick
        self.remaining_ticks       = 0
        self.is_on                 = False
        self.linked_soil_sensor    = None
        self.linked_water_tank     = None
        self.on_irrigation_complete = None

    def link_soil_sensor(self, sensor):
        self.linked_soil_sensor = sensor

    def link_water_tank(self, tank):
        self.linked_water_tank = tank

    def set_on_irrigation_complete(self, callback):
        """
        Callback opcional al terminar el riego.
        """
        self.on_irrigation_complete = callback

    def turn_on(self, duration: int) -> bool:
        """
        Inicia la bomba durante 'duration' ticks.
        Devuelve False si el tanque está vacío.
        """
        if self.linked_water_tank and self.linked_water_tank.is_empty():
            print("❌ No se puede iniciar el riego: el tanque está vacío.")
            return False

        self.is_on = True
        self.remaining_ticks = duration

        # Notificar al soil sensor (una sola vez)
        if self.linked_soil_sensor and hasattr(self.linked_soil_sensor, "trigger_irrigation"):
            self.linked_soil_sensor.trigger_irrigation()

        print(f"✅ Bomba activada: {duration} ticks × {self.flow_rate} L/tick.")
        return True

    def tick(self):
        """
        Debe llamarse cada tick de simulación para extraer agua del tanque.
        """
        if not self.is_on:
            return

        # Extraer del tanque
        extracted = self.flow_rate
        if self.linked_water_tank:
            extracted = self.linked_water_tank.consume_liters(self.flow_rate)

        # Aplicar al sensor de suelo si soporta add_water
        if self.linked_soil_sensor and hasattr(self.linked_soil_sensor, "add_water"):
            self.linked_soil_sensor.add_water(extracted)

        self.remaining_ticks -= 1
        if self.remaining_ticks <= 0:
            self.is_on = False
            print("🛑 Bomba desactivada tras completar el riego.")
            if self.on_irrigation_complete:
                self.on_irrigation_complete()