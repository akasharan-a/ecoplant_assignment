# Compressed Air Systems — Domain Primer

This primer gives you enough background to work with the data. It covers the basics. Some concepts you'll encounter in the dataset are left for you to explore.

---

## What a Compressor Does

An air compressor takes in atmospheric air and pressurizes it for use in industrial processes — powering tools, actuating valves, controlling equipment. Electrically driven compressors convert electrical power (kW) into pressurized air flow (CFM — cubic feet per minute).

The two quantities you'll care about most are:

- **Pressure (PSI)** — how hard the air is being pushed.
- **Flow (CFM)** — how much air is being delivered per unit of time.

---

## Activity States

A compressor doesn't simply run or not run. It operates in one of three states:

- **LOADED** — the compressor is actively compressing air and delivering flow to the system. Power draw is at or near rated capacity.
- **UNLOADED** — the compressor is running (motor spinning) but not delivering air. It draws a fraction of its rated power (typically 10–40%). This happens when system pressure is satisfied and no more air is needed, but the operator prefers not to stop and restart the motor.
- **OFF** — the compressor is fully stopped. No power draw, no flow.

Fixed speed compressors (FSD) cycle between LOADED and UNLOADED to regulate output — they can't vary their speed. Variable speed drives (VSD) adjust motor speed continuously and therefore modulate flow and power directly, spending most of their time LOADED at varying output levels.

---

## Compressor Types in This Station

**Fixed Speed Drive (FSD):** Runs at constant motor speed. When demand is satisfied, it unloads rather than stopping. Load/unload transitions are controlled by pressure setpoints: the compressor loads when system pressure drops below a lower threshold and unloads when it rises above an upper threshold.

**Variable Speed Drive (VSD):** Adjusts motor speed to match demand in real time. More efficient at partial load than an FSD because it avoids the energy waste of running unloaded. Has a minimum operating speed below which it cannot run stably.

**Centrifugal:** A different compression mechanism — uses high-speed rotating impellers rather than positive displacement. Suited for high, sustained flow rates. Has different operating characteristics from screw-type compressors, including a minimum flow requirement below which instability can occur. The `bov_position` column is specific to this compressor type — its purpose and behavior are worth investigating if relevant to your analysis.

---

## Efficiency: Specific Power

The standard efficiency metric for compressed air is **specific power**:

```
Specific Power = Power (kW) / Flow (CFM)
```

Lower is better — it means you're getting more air per unit of energy. A compressor running inefficiently will show rising specific power over time even if its output appears normal. Specific power is meaningful only when a compressor is LOADED and delivering flow; it should be treated as undefined (or excluded) when a compressor is UNLOADED or OFF.

For fixed speed compressors, specific power is roughly constant at a given pressure — it's a nameplate characteristic. For variable speed and centrifugal machines, it varies with operating point.

---

## Station vs. Compressor Pressure

Each compressor reports its own discharge pressure. The station also reports a system-level pressure measured downstream in the distribution network.

These are not the same. Air loses energy as it travels through pipes, fittings, and filters — this is called **pressure drop**. The station pressure will always be somewhat lower than individual compressor discharge pressures, and the gap tends to grow with higher flow rates.

---

## Compressor Health Signals

A few sensor readings are particularly informative for health monitoring:

**Oil temperature** — lubricating oil circulates through the compressor to cool and protect moving parts. Nominal operating temperature varies by machine but is typically in the 75–95°C range. Sustained elevation above normal operating temperature is a meaningful warning sign.

**Power draw** — at constant load and pressure, a healthy compressor draws consistent power. Creeping power at the same output is a sign of degrading efficiency.

**Activity transitions** — for FSD compressors, frequent load/unload cycling can indicate the compressor is struggling to maintain pressure or that system demand is fluctuating unusually. Very rapid cycling puts mechanical stress on the machine.

---

## Availability

Each compressor has an availability status: `available` or `in_maintenance`. When a compressor is in maintenance, its flow and power go to zero and its activity shows as `off`, but it continues to report the pressure it sees passively from the surrounding system.

---

*Some aspects of the data are not covered here. If you encounter something unfamiliar, treat it as you would in a real project — look it up, make a reasonable assumption, and document what you did.*
