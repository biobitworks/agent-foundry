"""Deterministic Moddik-style plate simulator. LOCAL SIMULATION: every reading carries source=SIMULATED.

This is a scripted scenario, not a physical model. The trajectory anchors and the intervention rule are
SCENARIO_PARAMETER=ILLUSTRATIVE: they come from neither the Moddik deck nor a publication and are not calibrated.
Noise is a pure function of (seed, sensor, tick) via sha256, so the stream is byte-identical on every replay and
independent of Python/NumPy RNG implementations.
"""
import hashlib

LEAF_SCHEMA = "agent-foundry.moddik.sensor_leaf.v1"
SEED = "moddik-demo-seed-v1"
HARDWARE_ID = "moddik-sim-plate-01"
PLATE_ID = "moddik-sim-plate-01/well-array"
TICKS = 11  # ticks 0..10
TICK_SECONDS = 600  # one tick = 10 simulated minutes

# sensor -> (unit, value at tick 0, value at last tick, noise amplitude)
SENSORS = {
    "pH": ("pH", 7.40, 7.02, 0.010),
    "O2": ("%", 18.5, 15.8, 0.10),
    "CO2": ("%", 5.00, 5.35, 0.03),
    "nutrient": ("mM", 25.0, 8.0, 0.15),
    "waste": ("mM", 2.0, 19.0, 0.15),
    "mechanical_stress": ("Pa", 0.80, 0.84, 0.01),
}
ORDER = list(SENSORS) + ["actuator_state"]  # fixed leaf order within a tick

# ILLUSTRATIVE scenario rule (not Moddik's, not calibrated). Declared in the run's first event.
POLICY = {"id": "illustrative-medium-exchange-v1", "status": "SCENARIO_PARAMETER=ILLUSTRATIVE", "rule": "nutrient < 12.0 mM AND waste > 15.0 mM",
          "nutrient_below": 12.0, "waste_above": 15.0, "action_if_met": "MEDIUM_EXCHANGE_RECOMMENDED"}
DECISION_TICK = 9  # the tick at which the scripted trajectory has crossed the rule


def _noise(seed: str, sensor: str, tick: int, amp: float, perturb: dict = None) -> float:
    h = int.from_bytes(hashlib.sha256(f"{seed}|{sensor}|{tick}".encode()).digest()[:8], "big") / 2**64
    return (h - 0.5) * 2 * amp


def reading(tick: int, sensor: str, seed: str = SEED, perturb: dict = None) -> dict:
    """One canonical sensor leaf. `perturb` = {(sensor, tick): delta} is the controlled difference for the replay bonus."""
    if sensor == "actuator_state":
        value, unit = "IDLE", "state"
    else:
        unit, v0, v1, amp = SENSORS[sensor]
        frac = tick / (TICKS - 1)
        # gentle curve: waste/nutrient follow a slightly accelerating scripted path; others linear
        shaped = frac ** 1.3 if sensor in ("nutrient", "waste") else frac
        value = round(v0 + (v1 - v0) * shaped + _noise(seed, sensor, tick, amp), 3)
        value = round(value + (perturb or {}).get((sensor, tick), 0.0), 3)
    return {"schema": LEAF_SCHEMA, "run_scope": "simulated", "hardware_id": HARDWARE_ID, "plate_id": PLATE_ID, "sequence": tick * len(ORDER) + ORDER.index(sensor),
            "tick": tick, "sim_time_s": tick * TICK_SECONDS, "sensor": sensor, "value": value, "unit": unit, "source": "SIMULATED"}


def tick_readings(tick: int, seed: str = SEED, perturb: dict = None) -> list:
    return [reading(tick, s, seed, perturb) for s in ORDER]


def policy_met(nutrient: float, waste: float) -> bool:
    return nutrient < POLICY["nutrient_below"] and waste > POLICY["waste_above"]


def stream(ticks: int = TICKS, seed: str = SEED, perturb: dict = None):
    for t in range(ticks):
        yield from tick_readings(t, seed, perturb)
