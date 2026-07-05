"""User-facing models for events (device→host) and actions (host→device).

These are the Python types library users see. The on-the-wire JSON envelope
(matching the firmware's ``AtechSerial`` class) is handled by the transport
layer — see :mod:`atech.runtime.transport`.

Wire format (for reference; not what users construct):

  Device → host:
    {"type":"event","payload":{"event_type":"sensor","key":"temperature",
                                "value":23.5,"source":"aht20"}}\\n

  Host → device:
    {"action":"set_led_color","value":"{\\"r\\":255,\\"g\\":0,\\"b\\":0}"}\\n
"""

from __future__ import annotations

from typing import Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

EventType = Literal["sensor", "button", "state", "log"]
EventValue = Union[float, int, str, dict, list, bool, None]


class Event(BaseModel):
    """A message from the board (sensor reading, button press, state change, log)."""

    model_config = ConfigDict(extra="ignore")

    type: EventType
    key: str
    value: EventValue = None
    module_type: Optional[str] = None
    received_at: Optional[float] = Field(
        default=None,
        description="Host-side wall-clock timestamp (seconds since epoch) "
        "when this event was parsed off the wire.",
    )


class Action(BaseModel):
    """A command sent to the board (LED color, motor speed, etc.).

    On the wire, ``value`` is stringified — the firmware reads action values as
    C-strings. Dicts/lists become JSON-encoded strings; numbers/bools become
    their string representations. Firmware-side user code parses with
    ``value.toInt()`` / ``deserializeJson()`` as needed.
    """

    model_config = ConfigDict(extra="ignore")

    key: str
    value: Union[str, int, float, bool, dict, list]
    module_type: Optional[str] = None


class PortInfo(BaseModel):
    """One port on the motherboard."""

    id: str
    name: Optional[str] = None
    side: Optional[str] = None
    slot_number: Optional[int] = None


class BoardInfo(BaseModel):
    """Metadata about a connected board (populated by hello-handshake, v0.2+)."""

    model: Optional[Literal["8port", "14port"]] = None
    firmware_version: Optional[str] = None
    ports: list[PortInfo] = Field(default_factory=list)
