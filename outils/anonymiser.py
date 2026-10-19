"""
Prépare une page param.htm enregistrée depuis la carte pour en faire une fixture de test.

    python outils/anonymiser.py <page enregistrée> <fixture produite>

Masque le nom de l'installation, les identifiants et mots de passe des zones, et retire
le pied de page. Échoue si une adresse IP, une adresse MAC ou un courriel reste dans la
page produite.
"""
import re
import sys

ENCODAGE = "ISO-8859-1"
MASQUE = "XXXX"


def anonymiser(page: str) -> str:
    """Rend la page sans donnée propre à l'installation."""
    page = re.sub(r"(?m)^[^<\r\n]*?(?= - SRB_)", MASQUE, page, count=1)
    page = re.sub(r"(name=['\"](?:UUs|UPw|Usr\d|Mdp\d)['\"][^>]*?value=)(['\"])[^'\"]*\2",
                  lambda m: f"{m.group(1)}{m.group(2)}{MASQUE}{m.group(2)}", page)
    page = re.sub(r"(?s)<div id='bottom_frame'>.*?</body>", "</body>", page)
    return page


def restes(page: str) -> list:
    """Liste les données personnelles encore présentes."""
    motifs = {
        "adresse IP": r"\b\d{1,3}(?:\.\d{1,3}){3}\b",
        "adresse MAC": r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b",
        "courriel": r"[\w.+-]+@[\w-]+\.[\w.]+",
    }
    return [f"{nom} : {m}" for nom, motif in motifs.items() for m in re.findall(motif, page)]


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    page = open(sys.argv[1], "rb").read().decode(ENCODAGE)
    propre = anonymiser(page)
    if MASQUE not in propre.split(" - SRB_", 1)[0][-20:]:
        print("nom de l'installation introuvable : page non reconnue")
        return 1
    reste = restes(propre)
    if reste:
        print("\n".join(reste))
        return 1
    open(sys.argv[2], "wb").write(propre.encode(ENCODAGE))
    print(f"fixture écrite : {len(propre)} caractères (page d'origine : {len(page)})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
