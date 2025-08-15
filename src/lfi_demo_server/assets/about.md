# What's This?

Welcome to the **`RP2350` Laser Fault Injection Playground**!

From this interface, a low-cost and partially 3D-printed **Laser Fault Injection Platform** can be controlled.

The target is Raspberry Pi's `RP2350`. Observe the silicon die and pulse the laser to attempt to inject faults into the chip!

---

# Hardware Overview

## Laser Fault Injection Platform

The **Laser Fault Injection Platform** can be divided into two subsystems.

### Positioning Stage

The positioning stage is used to precisely displace the die of the target `RP2350` for observation and laser focusing.

This stage is derived from the remarkable **OpenFlexure Delta Stage**.

![OFM](/static/ofm.jpg)

### Optical Subsystem

The optical subsystem is utilized for visualizing the die and focusing high-power laser pulses onto it.

![Optics](/static/optics.png)

Infrared light at about _1064 nm_ is used for both the imaging and fault injection features of the platform.

## Target

The target is Raspberry Pi's `RP2350`. The glitch detector circuits of the chip are enabled and configured to the highest sensitivity.

The backside ground pad of the target chip has been removed to expose the silicon die.

![Exposed Die](/static/backside_dremel.jpg)

The prepared integrated circuit can then be soldered to a custom carrier board, compatible with the **Laser Fault Injection Platform**.

![Carrier Board](/static/carrier_board.jpg)