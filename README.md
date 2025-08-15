# RP2350 Laser Fault Injection Playground

This contains the `RP2350` _"Laser Fault Injection Playground"_, used during _DEFCON_ 33.

This interface is essentially a web application running on the _Raspberry Pi_ single-board computer that powers the _"Laser Fault Injection Platform"_.

It allows to:

- Control the _XYZ_ positioning stage
- Control the infrared _LED_ used to illuminate the die of the target `RP2350`
- Display the output of the camera, showing die features. This includes a post-processing step to improve image quality
- Configure the output power of the laser pulser
- Pulse the laser
- Load firmware onto a target `RP2350` and monitor its status to detect successful glitches

For more context, refer to:

- [Laser Fault Injection on a Budget: RP2350 Edition](https://courk.cc/rp2350-challenge-laser)
- [Laser Fault Injection on a Budget: DEFCON 33 Showcase](https://courk.cc/lfi-defcon-content)

Note that this code was hacked together right before _DEFCON_. It's _just_ good enough for a demo and is probably not suitable for anything else.

## Dependencies

This code is expected to run on [Raspberry Pi OS (64-bit)](https://www.raspberrypi.com/software/operating-systems/#raspberry-pi-os-64-bit), Debian version: 12 (bookworm).

The following dependencies are required:

- [`picotool`](https://github.com/raspberrypi/picotool)
- [`libcyusbserial`](https://github.com/cyrozap/libcyusbserial/tree/master)
- [`poetry`](https://python-poetry.org/docs/#installing-with-the-official-installer)

This project includes code from [`pySangaboard`](https://gitlab.com/bath_open_instrumentation_group/pysangaboard) under the terms of the _GNU General Public License v3_.

## Installation

On the target, a simple `poetry install` is sufficient.