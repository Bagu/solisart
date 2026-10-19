"""Remplaçant vide de resource pour lancer les tests HA sous Windows. Jamais livré."""
RLIMIT_NOFILE = 7
RLIM_INFINITY = -1


def getrlimit(*_):
    return (4096, 4096)


def setrlimit(*_):
    pass
