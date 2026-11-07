from src.config import BIG_SERVO_ZERO_DEG, DEMO_BIG_SERVO_ABS_DEG, DEMO_EW_DEG, DEMO_NS_DEG
from src.models import SunAngles
from src.sunroom_control import (
    demo_big_servo_hold_command,
    logical_ns_to_servo,
    resolve_ns_servo,
    with_ns_servo,
)
from src.angle_predict import demo_sun_angles, predict_sun_angles


def test_logical_ns_to_servo():
    assert logical_ns_to_servo(0) == int(BIG_SERVO_ZERO_DEG)
    assert logical_ns_to_servo(15) == 125
    assert logical_ns_to_servo(100) == 180  # clamped


def test_resolve_ns_servo_override():
    assert resolve_ns_servo(75, abs_override=DEMO_BIG_SERVO_ABS_DEG) == 125
    assert resolve_ns_servo(15) == 125


def test_demo_big_servo_hold_command():
    cmd = demo_big_servo_hold_command()
    assert cmd.ns_angle == DEMO_BIG_SERVO_ABS_DEG
    assert len(cmd.small_angles) == 30
    assert all(a == int(DEMO_EW_DEG) for a in cmd.small_angles)


def test_with_ns_servo():
    from src.models import ServoCommand

    base = ServoCommand(ns_angle=45, small_angles=[30] * 30)
    out = with_ns_servo(base, 125)
    assert out.ns_angle == 125
    assert out.small_angles == [30] * 30


def test_predict_force_demo_no_hardware():
    result = predict_sun_angles(port=None, force_demo=True, sample_hardware=False)
    assert result.forced_demo is True
    assert result.sun == SunAngles(ns_angle=DEMO_NS_DEG, ew_zero=DEMO_EW_DEG)
    assert demo_sun_angles() == result.sun
