"""Addon source providers."""

from .base import AddonProvider, AddonRef
from .curseforge import CurseForgeProvider, CurseForgeWebProvider, slug_from_ref
from .github import GitHubProvider, pick_asset
from .tukui import TukuiProvider
from .wago import WagoProvider
from .wowinterface import WoWInterfaceProvider

# Registry: provider name → instance
_REGISTRY: dict[str, AddonProvider] = {
    "github":         GitHubProvider(),
    "tukui":          TukuiProvider(),
    "wowi":           WoWInterfaceProvider(),
    "curseforge":     CurseForgeProvider(),
    "curseforge_web": CurseForgeWebProvider(),
    "wago":           WagoProvider(),
}


def get_provider(name: str) -> AddonProvider:
    """Return the provider registered under ``name``.

    Raises :class:`KeyError` for unknown providers — that's a bug in
    the catalog and we want it loud.
    """
    return _REGISTRY[name]


def list_providers() -> list[str]:
    return sorted(_REGISTRY.keys())


__all__ = [
    "AddonProvider", "AddonRef",
    "GitHubProvider", "TukuiProvider", "WoWInterfaceProvider",
    "CurseForgeProvider", "CurseForgeWebProvider", "WagoProvider",
    "pick_asset", "slug_from_ref",
    "get_provider", "list_providers",
]
