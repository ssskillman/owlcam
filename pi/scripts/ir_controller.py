#!/usr/bin/env python3
"""GPIO IR illuminator control with thermal safety timers."""

from __future__ import annotations

import atexit
import logging
import math
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from typing import Any, Callable, Protocol
from zoneinfo import ZoneInfo

LOG = logging.getLogger("owlcam.ir")

DEFAULT_GPIO = 23
DEFAULT_AUTO_TIMEOUT = 20
DEFAULT_MAX_CONTINUOUS = 60
DEFAULT_COOLDOWN = 10
DEFAULT_LAT = 35.7796
DEFAULT_LON = -78.6382
DEFAULT_TZ = "America/New_York"


class IrMode(str, Enum):
    OFF = "off"
    MANUAL_ON = "manual_on"
    AUTO = "auto"


class IrOutputState(str, Enum):
    OFF = "off"
    MANUAL_ON = "manual_on"
    AUTO_ON = "auto_on"


class GpioBackend(Protocol):
    def set_output(self, level: int) -> None: ...

    def read_output(self) -> int: ...

    def close(self) -> None: ...


class MockGpioBackend:
    def __init__(self, pin: int) -> None:
        self.pin = pin
        self._level = 0

    def set_output(self, level: int) -> None:
        self._level = 1 if level else 0

    def read_output(self) -> int:
        return self._level

    def close(self) -> None:
        self._level = 0


class LgpioBackend:
    def __init__(self, pin: int) -> None:
        import lgpio  # type: ignore[import-untyped]

        self._lgpio = lgpio
        self.pin = pin
        self.chip = lgpio.gpiochip_open(0)
        lgpio.gpio_claim_output(self.chip, pin, 0)
        self._level = 0

    def set_output(self, level: int) -> None:
        self._lgpio.gpio_write(self.chip, self.pin, 1 if level else 0)
        self._level = 1 if level else 0

    def read_output(self) -> int:
        return self._level

    def close(self) -> None:
        try:
            self.set_output(0)
            self._lgpio.gpio_free(self.chip, self.pin)
            self._lgpio.gpiochip_close(self.chip)
        except Exception:
            LOG.exception("GPIO cleanup failed")


def open_gpio_backend(pin: int) -> GpioBackend:
    if os.environ.get("OWLCAM_IR_MOCK_GPIO", "").strip() in ("1", "true", "yes"):
        return MockGpioBackend(pin)
    try:
        return LgpioBackend(pin)
    except Exception as exc:
        if os.uname().machine != "aarch64":
            LOG.warning("lgpio unavailable (%s); using mock GPIO", exc)
            return MockGpioBackend(pin)
        raise


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "")
    if not raw:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return float(raw)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


@dataclass(frozen=True)
class IrConfig:
    gpio: int = DEFAULT_GPIO
    mode: IrMode = IrMode.AUTO
    auto_timeout_seconds: int = DEFAULT_AUTO_TIMEOUT
    max_continuous_on_seconds: int = DEFAULT_MAX_CONTINUOUS
    cooldown_seconds: int = DEFAULT_COOLDOWN
    simulate_dark: bool = False
    latitude: float = DEFAULT_LAT
    longitude: float = DEFAULT_LON
    timezone: str = DEFAULT_TZ
    dark_offset_after_sunset_min: int = 0
    dark_offset_before_sunrise_min: int = 0

    @classmethod
    def from_environ(cls) -> IrConfig:
        mode_raw = os.environ.get("OWLCAM_IR_MODE", "auto").strip().lower()
        try:
            mode = IrMode(mode_raw)
        except ValueError:
            mode = IrMode.AUTO
        return cls(
            gpio=_env_int("OWLCAM_IR_GPIO", DEFAULT_GPIO),
            mode=mode,
            auto_timeout_seconds=_env_int(
                "OWLCAM_IR_AUTO_TIMEOUT_SECONDS",
                DEFAULT_AUTO_TIMEOUT,
            ),
            max_continuous_on_seconds=_env_int(
                "OWLCAM_IR_MAX_CONTINUOUS_ON_SECONDS",
                DEFAULT_MAX_CONTINUOUS,
            ),
            cooldown_seconds=_env_int("OWLCAM_IR_COOLDOWN_SECONDS", DEFAULT_COOLDOWN),
            simulate_dark=_env_bool("OWLCAM_IR_SIMULATE_DARK"),
            latitude=_env_float("OWLCAM_IR_LATITUDE", DEFAULT_LAT),
            longitude=_env_float("OWLCAM_IR_LONGITUDE", DEFAULT_LON),
            timezone=os.environ.get("OWLCAM_IR_TIMEZONE", DEFAULT_TZ).strip() or DEFAULT_TZ,
            dark_offset_after_sunset_min=_env_int(
                "OWLCAM_IR_DARK_OFFSET_AFTER_SUNSET_MIN",
                0,
            ),
            dark_offset_before_sunrise_min=_env_int(
                "OWLCAM_IR_DARK_OFFSET_BEFORE_SUNRISE_MIN",
                0,
            ),
        )


def _solar_declination(day: date) -> float:
    """Approximate solar declination in radians (NOAA-style simplification)."""
    n = day.timetuple().tm_yday
    return math.radians(23.45) * math.sin(math.radians((360 / 365) * (n - 81)))


def _solar_event_utc(
    day: date,
    latitude: float,
    longitude: float,
    *,
    sunrise: bool,
) -> datetime:
    """Civil twilight (~6°) sunrise or sunset as UTC datetime."""
    lat = math.radians(latitude)
    decl = _solar_declination(day)
    zenith = math.radians(96.0)
    cos_hour = (math.cos(zenith) / (math.cos(lat) * math.cos(decl))) - math.tan(
        lat
    ) * math.tan(decl)
    cos_hour = max(-1.0, min(1.0, cos_hour))
    hour_angle = math.degrees(math.acos(cos_hour))
    solar_noon_utc = 720 - 4 * longitude
    minutes = solar_noon_utc - hour_angle if sunrise else solar_noon_utc + hour_angle
    while minutes < 0:
        minutes += 24 * 60
    while minutes >= 24 * 60:
        minutes -= 24 * 60
    hours = int(minutes // 60)
    mins = int(minutes % 60)
    secs = int((minutes - (hours * 60 + mins)) * 60)
    return datetime(day.year, day.month, day.day, hours, mins, secs, tzinfo=UTC)


def is_dark_now(config: IrConfig, when: datetime | None = None) -> bool:
    if config.simulate_dark:
        return True
    tz = ZoneInfo(config.timezone)
    local = (when or datetime.now(tz)).astimezone(tz)
    today = local.date()
    sunset = _solar_event_utc(
        today,
        config.latitude,
        config.longitude,
        sunrise=False,
    ).astimezone(tz) + timedelta(minutes=config.dark_offset_after_sunset_min)
    sunrise = _solar_event_utc(
        today,
        config.latitude,
        config.longitude,
        sunrise=True,
    ).astimezone(tz) - timedelta(minutes=config.dark_offset_before_sunrise_min)
    return local >= sunset or local < sunrise


@dataclass
class IRController:
    config: IrConfig
    gpio: GpioBackend
    clock: Callable[[], float] = time.monotonic
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _mode: IrMode = IrMode.OFF
    _output_state: IrOutputState = IrOutputState.OFF
    _on_reason: str | None = None
    _on_until: float = 0.0
    _segment_started_at: float | None = None
    _cooldown_until: float = 0.0
    _last_on_at: datetime | None = None
    _last_off_at: datetime | None = None
    _last_off_reason: str | None = None

    @property
    def mode(self) -> IrMode:
        return self._mode

    def __post_init__(self) -> None:
        self._mode = self.config.mode
        self._force_gpio_low("startup")
        atexit.register(self.cleanup)

    def _now(self) -> float:
        return self.clock()

    def _utc_now(self) -> datetime:
        return datetime.now(UTC)

    def _set_gpio(self, on: bool) -> None:
        self.gpio.set_output(1 if on else 0)

    def _force_gpio_low(self, reason: str) -> None:
        self._set_gpio(False)
        self._output_state = IrOutputState.OFF
        self._on_reason = None
        self._on_until = 0.0
        self._segment_started_at = None
        LOG.info("IR OFF reason=%s gpio=%s", reason, self.config.gpio)

    def set_mode(self, mode: IrMode) -> None:
        with self._lock:
            previous = self._mode
            self._mode = mode
            LOG.info("IR mode %s -> %s", previous.value, mode.value)
            if mode == IrMode.OFF:
                self._turn_off("mode_off")
            elif mode == IrMode.MANUAL_ON:
                self._turn_on("manual", IrOutputState.MANUAL_ON, extend_seconds=None)
            elif mode == IrMode.AUTO:
                if self._output_state == IrOutputState.MANUAL_ON:
                    self._turn_off("auto_enabled")

    def on(self, reason: str = "manual") -> None:
        with self._lock:
            if self._mode == IrMode.OFF:
                LOG.warning("IR on ignored while mode=off reason=%s", reason)
                return
            if self._in_cooldown() and reason != "manual":
                LOG.warning("IR on blocked by cooldown reason=%s", reason)
                return
            state = (
                IrOutputState.MANUAL_ON
                if self._mode == IrMode.MANUAL_ON
                else IrOutputState.AUTO_ON
            )
            self._turn_on(reason, state, extend_seconds=None)

    def off(self, reason: str = "manual") -> None:
        with self._lock:
            if self._mode == IrMode.MANUAL_ON and reason not in (
                "manual",
                "mode_off",
                "shutdown",
                "startup",
            ):
                return
            self._turn_off(reason)

    def pulse(self, seconds: float | None = None, reason: str = "motion") -> None:
        with self._lock:
            if self._mode != IrMode.AUTO:
                return
            if self._in_cooldown():
                LOG.debug("IR pulse ignored during cooldown")
                return
            duration = seconds if seconds is not None else float(self.config.auto_timeout_seconds)
            self._turn_on(reason, IrOutputState.AUTO_ON, extend_seconds=duration)

    def tick(self) -> None:
        with self._lock:
            now = self._now()
            if self._output_state != IrOutputState.OFF and self._segment_started_at is not None:
                elapsed = now - self._segment_started_at
                if elapsed >= self.config.max_continuous_on_seconds:
                    self._turn_off("thermal_timeout")
                    self._cooldown_until = now + self.config.cooldown_seconds
                    self._mode = IrMode.OFF if self._mode == IrMode.MANUAL_ON else self._mode
                    return
            if self._mode != IrMode.AUTO:
                return
            if self._output_state != IrOutputState.OFF and self._on_until and now >= self._on_until:
                self._turn_off("motion_timeout" if self._on_reason == "motion" else "timeout")

    def _in_cooldown(self) -> bool:
        return self._now() < self._cooldown_until

    def _turn_on(
        self,
        reason: str,
        state: IrOutputState,
        *,
        extend_seconds: float | None,
    ) -> None:
        now = self._now()
        if self._in_cooldown():
            LOG.warning("IR on blocked by cooldown reason=%s", reason)
            return
        if self._output_state == IrOutputState.OFF:
            self._segment_started_at = now
            self._set_gpio(True)
            self._last_on_at = self._utc_now()
            LOG.info(
                "IR ON reason=%s gpio=%s state=%s",
                reason,
                self.config.gpio,
                state.value,
            )
        self._output_state = state
        self._on_reason = reason
        if extend_seconds is not None:
            self._on_until = max(self._on_until, now + extend_seconds)
        elif state == IrOutputState.MANUAL_ON:
            self._on_until = 0.0

    def _turn_off(self, reason: str) -> None:
        if self._output_state == IrOutputState.OFF:
            return
        started = self._segment_started_at
        self._set_gpio(False)
        duration = (self._now() - started) if started is not None else 0.0
        self._output_state = IrOutputState.OFF
        self._on_reason = None
        self._on_until = 0.0
        self._segment_started_at = None
        self._last_off_at = self._utc_now()
        self._last_off_reason = reason
        LOG.info(
            "IR OFF reason=%s duration=%.1fs gpio=%s",
            reason,
            duration,
            self.config.gpio,
        )

    def status(self) -> dict[str, Any]:
        with self._lock:
            gpio_level = self.gpio.read_output()
            return {
                "mode": self._mode.value,
                "state": self._output_state.value,
                "gpio": self.config.gpio,
                "gpioLevel": gpio_level,
                "reason": self._on_reason,
                "lastOnAt": self._last_on_at.isoformat() if self._last_on_at else None,
                "lastOffAt": self._last_off_at.isoformat() if self._last_off_at else None,
                "lastOffReason": self._last_off_reason,
                "autoTimeoutSeconds": self.config.auto_timeout_seconds,
                "maxContinuousSeconds": self.config.max_continuous_on_seconds,
                "cooldownSeconds": self.config.cooldown_seconds,
                "inCooldown": self._in_cooldown(),
                "isDark": is_dark_now(self.config),
                "simulateDark": self.config.simulate_dark,
            }

    def cleanup(self) -> None:
        with self._lock:
            self._turn_off("shutdown")
            self.gpio.close()
