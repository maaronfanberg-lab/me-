"""lapse-meter: measure where the learning signal reaches inside a neural network."""
from .core import lapse_profile, geometry, Geometry, slope, local_curvature

__version__ = "0.1.0"
__all__ = ["lapse_profile", "geometry", "Geometry", "slope", "local_curvature"]
