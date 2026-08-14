"""Uitvoer naar het e-ink paneel, met een PNG-fallback om zonder hardware
te kunnen ontwikkelen.

E-ink slijt van onnodig verversen en mag niet wakker blijven staan: na elke
refresh gaat het paneel weer slapen. Daarom tekenen we alleen bij een echte
toestandswissel, nooit op een timer.
"""

from __future__ import annotations

import importlib
import logging
import os

log = logging.getLogger("display")


class PngDisplay:
    """Schrijft elk scherm naar een PNG. Voor ontwikkelen op een pc."""

    def __init__(self, size=(400, 300), out_dir="preview"):
        self.size = size
        self.out_dir = out_dir
        self.count = 0
        os.makedirs(out_dir, exist_ok=True)

    def show(self, image):
        self.count += 1
        path = os.path.join(self.out_dir, f"{self.count:02d}.png")
        image.convert("L").save(path)
        log.info("scherm -> %s", path)
        return path

    def clear(self):
        pass

    def sleep(self):
        pass


class EpaperDisplay:
    """Waveshare e-Paper via hun waveshare_epd-module."""

    def __init__(self, driver: str, rotate: int = 0):
        module = importlib.import_module(f"waveshare_epd.{driver}")
        self.epd = module.EPD()
        self.rotate = rotate % 360
        panel = (self.epd.width, self.epd.height)
        self.size = (panel[1], panel[0]) if self.rotate in (90, 270) else panel
        self._awake = False
        log.info("paneel %s, %dx%d, rotatie %d", driver, *self.size, self.rotate)

    def _wake(self):
        if not self._awake:
            self.epd.init()
            self._awake = True

    def show(self, image):
        self._wake()
        if self.rotate:
            image = image.rotate(self.rotate, expand=True)
        self.epd.display(self.epd.getbuffer(image))
        self.sleep()

    def clear(self):
        self._wake()
        try:
            self.epd.Clear()
        except TypeError:  # sommige drivers willen een vulwaarde
            self.epd.Clear(0xFF)
        self.sleep()

    def sleep(self):
        if self._awake:
            self.epd.sleep()
            self._awake = False


def make_display(driver: str, rotate: int = 0, size=(400, 300), out_dir="preview"):
    """E-ink als het kan, anders PNG. Zo draait dezelfde code op de pc."""
    try:
        return EpaperDisplay(driver, rotate)
    except Exception as exc:  # geen SPI, geen waveshare_epd, geen paneel
        log.warning("geen e-ink (%s) -- val terug op PNG in %s/", exc, out_dir)
        return PngDisplay(size, out_dir)
