"""Lecture des pages de la carte SolisArt, sans dépendance à Home Assistant."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from html.parser import HTMLParser

TEMPERATURE = "temperature"
POURCENTAGE = "pourcentage"
DEBIT = "debit"
RELAIS = "relais"

NB_ZONES_CHAUFFAGE = 6
ZONE_ECS = 6
FORMULAIRE = "frm_params"

MODE_ARRET = "0"
MODE_SOLEIL = "1"
MODE_SOLEIL_APPOINT = "2"
MODES = (MODE_ARRET, MODE_SOLEIL, MODE_SOLEIL_APPOINT)

SONDE_ABSENTE = ("Dsc", "...")

MOTIF_MODE = re.compile(r"FillUtilModeChauff\('(\w+)'\s*,\s*'([^']*)'\)")
MOTIF_ZONE = re.compile(
    r"EnableZoneDftParamsInputs\('(\d)'\s*,\s*document[^,)]+(?:,\s*'(\d)')?\s*\)"
)
MOTIF_BORNES = re.compile(r"CIV\((-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)")
MOTIF_VERSION = re.compile(r"(SRB_\S+)\s+-\s+(WEB_\S+)")
MOTIF_NOMBRE = re.compile(r"^[-+]?\d+(?:\.\d+)?")


class PageInattendue(ValueError):
    """La page reçue ne ressemble pas à celle d'une carte SolisArt."""


@dataclass(frozen=True)
class Mesure:
    """Une balise de status.xml : sa nature, sa valeur (None si la sonde est absente)
    et le texte brut renvoyé par la carte."""

    nature: str
    valeur: float | bool | None
    brut: str


@dataclass
class Etat:
    """Contenu de status.xml. `inconnues` garde les balises qu'aucune règle ne sait lire."""

    mesures: dict[str, Mesure] = field(default_factory=dict)
    inconnues: dict[str, str] = field(default_factory=dict)


def _nombre(texte: str) -> float | None:
    """Premier nombre en tête du texte, ou None."""
    trouve = MOTIF_NOMBRE.match(texte)
    return float(trouve.group(0)) if trouve else None


def _lire_balise(nom: str, texte: str) -> Mesure | None:
    """Reconnaît une balise par son nom et le format de sa valeur, ou rend None."""
    if re.fullmatch(r"t\d+", nom):
        if texte in SONDE_ABSENTE:
            return Mesure(TEMPERATURE, None, texte)
        if texte.endswith("dC"):
            return Mesure(TEMPERATURE, _nombre(texte), texte)
        return None
    if texte.endswith("pC") and _nombre(texte) is not None:
        return Mesure(POURCENTAGE, _nombre(texte), texte)
    if texte.endswith("l/mn") and _nombre(texte) is not None:
        return Mesure(DEBIT, _nombre(texte) + 0.0, texte)
    if texte in ("On", "Off"):
        return Mesure(RELAIS, texte == "On", texte)
    if nom.startswith("v3v") and _nombre(texte) is not None:
        return Mesure(POURCENTAGE, _nombre(texte), texte)
    return None


def lire_etat(xml: str | bytes) -> Etat:
    """Analyse /XML/status.xml.

    Une sonde absente (« Dsc ») donne une valeur None, jamais zéro. Une balise d'un
    format inconnu va dans `inconnues` au lieu d'être devinée.
    """
    try:
        racine = ET.fromstring(xml)
    except ET.ParseError as err:
        raise PageInattendue(f"status.xml illisible : {err}") from err
    etat = Etat()
    for element in racine:
        texte = (element.text or "").strip()
        mesure = _lire_balise(element.tag, texte)
        if mesure is None:
            etat.inconnues[element.tag] = texte
        else:
            etat.mesures[element.tag] = mesure
    if not etat.mesures:
        raise PageInattendue("status.xml ne contient aucune mesure reconnue")
    return etat


@dataclass(frozen=True)
class Consigne:
    """Une température réglable : valeur actuelle (None si vide), bornes de la carte et
    état du champ (un champ désactivé ne peut pas être changé)."""

    nom: str
    valeur: float | None
    minimum: float | None
    maximum: float | None
    actif: bool


@dataclass(frozen=True)
class Zone:
    """Une zone de chauffage (0 à 5) ou l'eau chaude (6)."""

    index: int
    libelle: str
    mode: str
    confort: Consigne
    reduit: Consigne

    @property
    def eau_chaude(self) -> bool:
        return self.index == ZONE_ECS


@dataclass
class Reglages:
    """Contenu utile de /param.htm."""

    zones: list[Zone]
    version_carte: str | None
    version_web: str | None


@dataclass
class _Champ:
    nom: str
    balise: str
    attributs: dict[str, str | None]


class _LecteurPage(HTMLParser):
    """Relève les champs du formulaire frm_params, le texte des cellules Txx, le texte
    des scripts en ligne et le texte visible."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.champs: dict[str, _Champ] = {}
        self.cellules: dict[str, str] = {}
        self.scripts: list[str] = []
        self.texte: list[str] = []
        self._dans_formulaire = False
        self._cellule: str | None = None
        self._dans_script = False
        self.formulaire_vu = False

    def handle_starttag(self, tag, attrs):
        attributs = dict(attrs)
        if tag == "form" and attributs.get("name") == FORMULAIRE:
            self._dans_formulaire = True
            self.formulaire_vu = True
        elif tag == "script" and not attributs.get("src"):
            self._dans_script = True
            self.scripts.append("")
        elif tag == "td" and re.fullmatch(r"T0\d", attributs.get("id") or ""):
            self._cellule = attributs["id"]
            self.cellules[self._cellule] = ""
        if self._dans_formulaire and tag in ("input", "select", "textarea"):
            nom = attributs.get("name")
            if nom and nom not in self.champs:
                self.champs[nom] = _Champ(nom, tag, attributs)

    def handle_endtag(self, tag):
        if tag == "form":
            self._dans_formulaire = False
        elif tag == "script":
            self._dans_script = False
        elif tag == "td":
            self._cellule = None

    def handle_data(self, data):
        if self._dans_script:
            self.scripts[-1] += data
            return
        if self._cellule:
            self.cellules[self._cellule] += data
        self.texte.append(data)


def _consigne(lecteur: _LecteurPage, nom: str, desactives: set[str]) -> Consigne:
    """Lit un champ de température et ses bornes (appel CIV de son onchange)."""
    champ = lecteur.champs.get(nom)
    if champ is None:
        return Consigne(nom, None, None, None, False)
    bornes = MOTIF_BORNES.search(champ.attributs.get("onchange") or "")
    actif = "disabled" not in champ.attributs and nom not in desactives
    return Consigne(
        nom,
        _nombre((champ.attributs.get("value") or "").strip()),
        float(bornes.group(1)) if bornes else None,
        float(bornes.group(2)) if bornes else None,
        actif,
    )


def lire_reglages(html: str) -> Reglages:
    """Analyse /param.htm : zones présentes, libellés, modes et consignes.

    Une zone de chauffage est présente quand la page l'active
    (EnableZoneDftParamsInputs avec '1'). L'eau chaude l'est quand sa liste U06_6
    existe. Un mode inconnu se lit comme l'arrêt, comme le fait la page elle-même.
    """
    lecteur = _LecteurPage()
    lecteur.feed(html)
    lecteur.close()
    if not lecteur.formulaire_vu:
        raise PageInattendue(f"formulaire {FORMULAIRE} absent de param.htm")

    scripts = "\n".join(lecteur.scripts)
    modes = {nom: (v if v in MODES else MODE_ARRET) for nom, v in MOTIF_MODE.findall(scripts)}
    presentes = {int(i) for i, drapeau in MOTIF_ZONE.findall(scripts) if drapeau == "1"}
    if f"U06_{ZONE_ECS}" in lecteur.champs:
        presentes.add(ZONE_ECS)

    zones = []
    for index in sorted(presentes):
        mode = modes.get(f"U06_{index}", MODE_ARRET)
        desactives = {f"U09_{index}", f"U10_{index}"} if mode == MODE_ARRET else set()
        libelle = " ".join(lecteur.cellules.get(f"T0{index}", "").split())
        zones.append(Zone(
            index=index,
            libelle=libelle,
            mode=mode,
            confort=_consigne(lecteur, f"U09_{index}", desactives),
            reduit=_consigne(lecteur, f"U10_{index}", desactives),
        ))

    version = MOTIF_VERSION.search(" ".join(" ".join(lecteur.texte).split()))
    return Reglages(
        zones=zones,
        version_carte=version.group(1) if version else None,
        version_web=version.group(2) if version else None,
    )
