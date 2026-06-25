"""Integration interfaces and adapters.

Every external system is accessed through a Protocol with at least a mock implementation, so
the whole app runs offline in dev/test. Real adapters (Claude, Gmail, GitHub, etc.) are added
in later phases behind the same interfaces.
"""
