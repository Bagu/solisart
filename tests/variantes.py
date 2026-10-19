"""Variantes de la page réelle param_reel.htm, chacune exerçant une règle de la
reconstruction du formulaire, et changements de modes demandés sur chacune."""
import os

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGE = os.path.join(RACINE, "tests", "fixtures", "param_reel.htm")
REFERENCE = os.path.join(RACINE, "tests", "fixtures", "corps_reference.json")

MODES = [{}, {"U06_0": "0"}, {"U06_0": "1", "U06_1": "0", "U06_6": "1"}, {"U06_9": "1"}]


def lire_page() -> str:
    """Page réelle anonymisée, décodée comme la carte l'encode."""
    with open(PAGE, "rb") as f:
        return f.read().decode("latin-1")


def _remplacer(texte: str, avant: str, apres: str) -> str:
    assert texte.count(avant) == 1, avant
    return texte.replace(avant, apres)


def variantes(page: str) -> list[tuple[str, str]]:
    """(nom, contenu) : page réelle et modifications qui exercent chaque règle."""
    assert "checked" not in page.split("cb02", 1)[1][:80], "hors-gel déjà coché : variante sans effet"
    return [
        ("page réelle", page),
        ("étage arrêté par la page", _remplacer(page, "FillUtilModeChauff('U06_1','2')", "FillUtilModeChauff('U06_1','0')")),
        ("mode inconnu", _remplacer(page, "FillUtilModeChauff('U06_0','2')", "FillUtilModeChauff('U06_0','7')")),
        ("hors-gel coché", page.replace("id='cb02'", "id='cb02' checked", 1).replace('id="cb02"', 'id="cb02" checked', 1)),
        ("accents, espace, entité", _remplacer(page, "name='U09_0' value='18.5'", "name='U09_0' value='a b&amp;é~+'")),
        ("chevron dans un attribut", _remplacer(page, "name='U09_1' value='18.5'", "name='U09_1' onfocus=\"if(a>b){}\" value='18.5'")),
        ("champ désactivé", _remplacer(page, "name='U10_1' value=", "name='U10_1' disabled value=")),
    ]
