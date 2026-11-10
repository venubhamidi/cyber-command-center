"""A plugin defined outside the built-ins, loaded through APP_PLUGIN_MODULES (see test_plugins.py)."""
from harness.plugins import register
from harness.plugins.ticketing import MemoryTicketing


class SampleTicketing(MemoryTicketing):
    pass


@register("ticketing", "sample")
def build(settings) -> SampleTicketing:
    return SampleTicketing()
