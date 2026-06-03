"""frameworks: interchangeable narrative lenses behind a name registry.

Each framework wraps the pure analysis functions in narrative.py. Consumers
depend on the Framework ABC and the registry, never on a concrete framework.
"""
from app.frameworks.base import Framework, FrameworkResult
from app.frameworks.papalampidi import PapalampidiFramework
from app.frameworks.registry import DEFAULT_REGISTRY, FrameworkRegistry
from app.frameworks.vonnegut import VonnegutFramework

__all__ = [
    "Framework",
    "FrameworkResult",
    "FrameworkRegistry",
    "DEFAULT_REGISTRY",
    "VonnegutFramework",
    "PapalampidiFramework",
]
