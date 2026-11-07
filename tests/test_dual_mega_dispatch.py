from src.models import ServoCommand
from src.serial.mega_client import MegaClient


def test_mod1_payload_shape():
    # 不连硬件：只验证参数校验
    c = MegaClient("COM8")
    try:
        c.send_set_mod1(125, [60] * 14)
        assert False, "should reject wrong length"
    except ValueError:
        pass


def test_servo_command_split():
    cmd = ServoCommand(ns_angle=125, small_angles=list(range(30, 60)))
    assert cmd.small_angles[:15] == list(range(30, 45))
    assert cmd.small_angles[15:] == list(range(45, 60))
