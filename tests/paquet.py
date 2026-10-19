"""Accès aux modules de l'intégration sans exécuter son __init__.py, qui importe Home Assistant."""
import importlib
import os
import sys
import types

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOSSIER = os.path.join(RACINE, "custom_components", "solisart")
NOM = "solisart_sans_ha"

if NOM not in sys.modules:
    paquet = types.ModuleType(NOM)
    paquet.__path__ = [DOSSIER]
    sys.modules[NOM] = paquet


def module(nom):
    """Importe custom_components/solisart/<nom>.py."""
    return importlib.import_module(f"{NOM}.{nom}")
