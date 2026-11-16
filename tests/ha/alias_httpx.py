"""Greffon pytest chargé avant le harnais (option -p de pytest.ini), qui permet de
lancer le harnais de Home Assistant 2026.10 sur Home Assistant 2026.11.

1. Depuis 2026.11, l'import de homeassistant redirige httpx vers httpx2 et échoue si
   httpx est déjà chargé. Le harnais importe respx, donc httpx, avant Home Assistant :
   la redirection est faite ici en premier. Home Assistant la refait sans effet.
2. Le harnais importe _clear_logger_overwrites, retirée en 2026.11. Elle ne sert qu'à
   un utilitaire que ces tests n'appellent pas : elle est remplacée par une fonction qui
   lève une erreur si elle est appelée.

Sans effet avant 2026.11 (pas de httpx2, fonction présente).
"""
try:
    import httpx2
except ImportError:
    pass
else:
    httpx2.alias_httpx()

    import homeassistant.components.logger as _journal

    if not hasattr(_journal, "_clear_logger_overwrites"):

        def _clear_logger_overwrites(hass: object) -> None:
            """Remplaçant de la fonction retirée de Home Assistant 2026.11."""
            raise NotImplementedError("_clear_logger_overwrites n'existe plus depuis Home Assistant 2026.11")

        _journal._clear_logger_overwrites = _clear_logger_overwrites
