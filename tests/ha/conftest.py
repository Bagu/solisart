"""Réglages communs des tests Home Assistant."""
import sys

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Autorise le chargement de custom_components/solisart."""
    yield


if sys.platform == "win32":
    import pytest_socket

    def _blocage_sans_effet(*_args, **_kwargs):
        """La boucle asyncio de Windows ouvre ses propres sockets locaux, que le greffon HA
        bloquerait. Sous Windows seulement, le blocage est neutralisé : les requêtes vers
        la carte restent simulées par aioclient_mock, et la résolution de noms reste
        interdite par le greffon."""

    pytest_socket.disable_socket = _blocage_sans_effet
