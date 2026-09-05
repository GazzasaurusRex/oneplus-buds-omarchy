"""OnePlus/OPPO earbud protocol proof of concept."""

__version__ = "0.0.1"

from .api import BudsBackend
from .controller import BudsController

__all__ = ["BudsBackend", "BudsController", "__version__"]
