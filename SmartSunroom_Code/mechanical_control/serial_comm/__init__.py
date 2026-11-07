"""Serial communication with Mega servo boards."""

from mechanical_control.serial_comm.mega_client import MegaClient, dispatch_servo_command
from mechanical_control.serial_comm.ports import list_serial_ports

__all__ = ["MegaClient", "dispatch_servo_command", "list_serial_ports"]
