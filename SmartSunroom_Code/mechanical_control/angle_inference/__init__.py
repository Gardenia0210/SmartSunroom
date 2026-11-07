"""Solar-angle inference from photoresistor board + trained model."""

from mechanical_control.angle_inference.predict import (
    AnglePredictResult,
    predict_sun_angles,
    sample_angle_board,
)

__all__ = ["AnglePredictResult", "predict_sun_angles", "sample_angle_board"]
