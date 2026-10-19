"""Effet d'un POST de param.htm sur la page servie par une fausse carte : les modes
(U06_x), les consignes (U09_x, U10_x) et les octets de planning (Pzjo) reçus
remplacent ceux de la page."""
import re
from urllib.parse import parse_qsl

ENCODAGE = "ISO-8859-1"


def appliquer(page: bytes, corps: bytes) -> bytes:
    """Page telle que la carte la servirait après avoir enregistré le corps reçu."""
    texte = page.decode(ENCODAGE)
    for nom, valeur in parse_qsl(corps.decode("ascii"), keep_blank_values=True, encoding=ENCODAGE):
        if re.fullmatch(r"U06_\d", nom):
            texte = re.sub(rf"FillUtilModeChauff\('{nom}','[^']*'\)",
                           f"FillUtilModeChauff('{nom}','{valeur}')", texte)
        elif re.fullmatch(r"U(09|10)_\d", nom):
            texte = re.sub(rf"(name='{nom}' value=')[^']*'", rf"\g<1>{valeur}'", texte)
        elif re.fullmatch(r"P\d{3}", nom):
            texte = re.sub(rf'(name="{nom}" value=")[^"]*"', rf'\g<1>{valeur}"', texte)
    return texte.encode(ENCODAGE)
