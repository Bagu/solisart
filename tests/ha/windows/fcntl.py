"""Remplaçant vide de fcntl pour lancer les tests HA sous Windows. Jamais livré."""
LOCK_EX = LOCK_NB = LOCK_UN = 0


def flock(*_):
    pass


def fcntl(*_):
    return 0
