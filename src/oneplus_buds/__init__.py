"""OnePlus/OPPO earbud protocol proof of concept."""

__version__ = "0.1.0"

from .api import BudsBackend
from .bridge import BudsFrontendBridge, serialize_snapshot
from .controller import BudsController
from .service import BudsServiceRunner, ServiceState

__all__ = [
    "BudsBackend",
    "BudsController",
    "BudsFrontendBridge",
    "BudsServiceRunner",
    "ServiceState",
    "serialize_snapshot",
    "__version__",
]
