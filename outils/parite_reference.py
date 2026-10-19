"""
Fixe le corps de référence du POST de param.htm : fait tourner un script de pilotage
éprouvé sur la vraie carte, sur chaque variante de tests/variantes.py, et range ses
corps dans tests/fixtures/corps_reference.json. Le test de parité compare ensuite
analyse.corps_formulaire à ces corps, sans réseau ni dépendance.

    python outils/parite_reference.py <python avec bs4> <extracteur> <script de référence>

L'extracteur reçoit : <script de référence> <page.htm> '<modes JSON>' et écrit le corps
urlencodé sur sa sortie standard.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RACINE, "tests"))
from variantes import MODES, PAGE, REFERENCE, lire_page, variantes  # noqa: E402


def produire(python: str, extracteur: str, script: str) -> list[dict]:
    """Corps de référence de chaque (variante, modes)."""
    cas = []
    with tempfile.TemporaryDirectory(prefix="parite-solisart-") as dossier:
        chemin = os.path.join(dossier, "page.htm")
        for nom, contenu in variantes(lire_page()):
            with open(chemin, "wb") as f:
                f.write(contenu.encode("latin-1"))
            for modes in MODES:
                r = subprocess.run([python, extracteur, script, chemin, json.dumps(modes)], capture_output=True)
                if r.returncode or not r.stdout:
                    raise SystemExit(f"{nom} {modes} : référence en échec {r.stderr[-300:]!r}")
                cas.append({"variante": nom, "modes": modes, "corps": r.stdout.decode("ascii")})
    return cas


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    cas = produire(*sys.argv[1:])
    with open(PAGE, "rb") as f:
        empreinte = hashlib.sha256(f.read()).hexdigest()
    ancien = None
    if os.path.exists(REFERENCE):
        with open(REFERENCE, encoding="utf-8") as f:
            ancien = json.load(f)
    nouveau = {"page_sha256": empreinte, "cas": cas}
    with open(REFERENCE, "w", encoding="utf-8") as f:
        json.dump(nouveau, f, ensure_ascii=False, indent=1)
        f.write("\n")
    change = "inchangé" if ancien == nouveau else "modifié"
    print(f"corps de référence {change} : {len(cas)} cas, {len({c['corps'] for c in cas})} corps distincts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
