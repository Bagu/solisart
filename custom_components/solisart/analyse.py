"""Lecture des pages de la carte SolisArt, sans dépendance à Home Assistant."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Sequence
from dataclasses import dataclass, field
from html.parser import HTMLParser
from urllib.parse import urlencode

TEMPERATURE = "temperature"
POURCENTAGE = "pourcentage"
DEBIT = "debit"
RELAIS = "relais"

NB_ZONES_CHAUFFAGE = 6
ZONE_ECS = 6
FORMULAIRE = "frm_params"
FORMULAIRE_PLANNING = "frm_prog"
ENCODAGE = "ISO-8859-1"

MODE_ARRET = "0"
MODE_SOLEIL = "1"
MODE_SOLEIL_APPOINT = "2"
MODES = (MODE_ARRET, MODE_SOLEIL, MODE_SOLEIL_APPOINT)

SONDE_ABSENTE = ("Dsc", "...")

CASE_HORS_GEL = "cb02"
CHAMPS_HORS_GEL = ("U03", "U14", "U13", "U04", "U15", "U17", "U16", "U05", "U18")
TYPES_IGNORES = ("submit", "button", "reset", "image")

JOURS = 7
CRENEAUX = 48
OCTETS_PAR_JOUR = 6
LISTE_ZONE_PLANNING = "U19_0"
LISTE_JOUR_PLANNING = "U20_0"

MOTIF_MODE = re.compile(r"FillUtilModeChauff\('(\w+)'\s*,\s*'([^']*)'\)")
MOTIF_ZONE = re.compile(
    r"EnableZoneDftParamsInputs\('(\d)'\s*,\s*document[^,)]+(?:,\s*'(\d)')?\s*\)"
)
MOTIF_BORNES = re.compile(r"CIV\((-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)")
MOTIF_VERSION = re.compile(r"(SRB_\S+)\s+-\s+(WEB_\S+)")
MOTIF_NOMBRE = re.compile(r"^[-+]?\d+(?:\.\d+)?")
MOTIF_CIBLE_CASE = re.compile(r"elements\['(\w+)'\]")
MOTIF_DECIMALES = re.compile(r"CIC\(event\s*,\s*(\d+)")
MOTIF_CHAMP_ZONE = re.compile(r"U(06|09|10)_(\d)")
MOTIF_HEURE = r"(\d{1,2})(?:[:hH](\d{2})?)?"
MOTIF_PLAGE = re.compile(rf"{MOTIF_HEURE}\s*-\s*{MOTIF_HEURE}")


class PageInattendue(ValueError):
    """La page reçue ne ressemble pas à celle d'une carte SolisArt."""


class ReglageRefuse(ValueError):
    """Changement demandé que le module ne peut pas transmettre : champ inconnu ou
    désactivé, zone absente, valeur hors des bornes de la carte."""


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
    decimales: int = 1


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
    plannings: dict[int, tuple[tuple[bool, ...], ...]] = field(default_factory=dict)


@dataclass
class _Champ:
    nom: str
    balise: str
    attributs: dict[str, str | None]
    texte: str = ""
    options: list[tuple[str, bool]] = field(default_factory=list)


class _LecteurPage(HTMLParser):
    """Relève les champs de chaque formulaire nommé (ceux de frm_params aussi par nom),
    les options des listes, le texte des cellules Txx, le texte des scripts en ligne et
    le texte visible."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.champs: dict[str, _Champ] = {}
        self.formulaires: dict[str, list[_Champ]] = {}
        self._zone_texte: _Champ | None = None
        self._liste: _Champ | None = None
        self._option: list | None = None
        self.cellules: dict[str, str] = {}
        self.scripts: list[str] = []
        self.texte: list[str] = []
        self._formulaire: str | None = None
        self._cellule: str | None = None
        self._dans_script = False

    @property
    def formulaire_vu(self) -> bool:
        return FORMULAIRE in self.formulaires

    @property
    def elements(self) -> list[_Champ]:
        return self.formulaires.get(FORMULAIRE, [])

    def handle_starttag(self, tag, attrs):
        attributs = dict(attrs)
        if tag == "form" and attributs.get("name"):
            self._formulaire = attributs["name"]
            self.formulaires.setdefault(self._formulaire, [])
        elif tag == "option" and self._liste is not None:
            self._fermer_option()
            self._option = [attributs.get("value"), "selected" in attributs, ""]
        elif tag == "script" and not attributs.get("src"):
            self._dans_script = True
            self.scripts.append("")
        elif tag == "td" and re.fullmatch(r"T0\d", attributs.get("id") or ""):
            self._cellule = attributs["id"]
            self.cellules[self._cellule] = ""
        if self._formulaire is not None and tag in ("input", "select", "textarea"):
            nom = attributs.get("name")
            element = _Champ(nom or "", tag, attributs)
            self.formulaires[self._formulaire].append(element)
            if tag == "textarea":
                self._zone_texte = element
            elif tag == "select":
                self._liste = element
            if nom and nom not in self.champs and self._formulaire == FORMULAIRE:
                self.champs[nom] = element

    def _fermer_option(self) -> None:
        """Range l'option en cours ; sans attribut value, sa valeur est son texte."""
        if self._option is not None and self._liste is not None:
            valeur, choisie, texte = self._option
            self._liste.options.append((valeur if valeur is not None else " ".join(texte.split()), choisie))
        self._option = None

    def handle_endtag(self, tag):
        if tag == "form":
            self._formulaire = None
        elif tag == "option":
            self._fermer_option()
        elif tag == "select":
            self._fermer_option()
            self._liste = None
        elif tag == "script":
            self._dans_script = False
        elif tag == "td":
            self._cellule = None
        elif tag == "textarea":
            self._zone_texte = None

    def handle_data(self, data):
        if self._dans_script:
            self.scripts[-1] += data
            return
        if self._zone_texte is not None:
            self._zone_texte.texte += data
        if self._option is not None:
            self._option[2] += data
        if self._cellule:
            self.cellules[self._cellule] += data
        self.texte.append(data)


def _consigne(lecteur: _LecteurPage, nom: str, desactives: set[str]) -> Consigne:
    """Lit un champ de température et ses bornes (appel CIV de son onchange)."""
    champ = lecteur.champs.get(nom)
    if champ is None:
        return Consigne(nom, None, None, None, False)
    bornes = MOTIF_BORNES.search(champ.attributs.get("onchange") or "")
    decimales = MOTIF_DECIMALES.search(champ.attributs.get("onkeypress") or "")
    actif = "disabled" not in champ.attributs and nom not in desactives
    return Consigne(
        nom,
        _nombre((champ.attributs.get("value") or "").strip()),
        float(bornes.group(1)) if bornes else None,
        float(bornes.group(2)) if bornes else None,
        actif,
        int(decimales.group(1)) if decimales else 1,
    )


def _analyser(html: str) -> _LecteurPage:
    """Lit la page entière ; lève PageInattendue sans formulaire frm_params."""
    lecteur = _LecteurPage()
    lecteur.feed(html)
    lecteur.close()
    if not lecteur.formulaire_vu:
        raise PageInattendue(f"formulaire {FORMULAIRE} absent de param.htm")
    return lecteur


def _modes(lecteur: _LecteurPage) -> dict[str, str]:
    """Valeur de chaque liste remplie par FillUtilModeChauff ; une valeur inconnue
    devient l'arrêt, première option de la liste, comme dans le navigateur."""
    scripts = "\n".join(lecteur.scripts)
    return {nom: (v if v in MODES else MODE_ARRET) for nom, v in MOTIF_MODE.findall(scripts)}


def lire_reglages(html: str) -> Reglages:
    """Analyse /param.htm : zones présentes, libellés, modes et consignes.

    Une zone de chauffage est présente quand la page l'active
    (EnableZoneDftParamsInputs avec '1'). L'eau chaude l'est quand sa liste U06_6
    existe. Un mode inconnu se lit comme l'arrêt, comme le fait la page elle-même.
    """
    lecteur = _analyser(html)
    scripts = "\n".join(lecteur.scripts)
    modes = _modes(lecteur)
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
        plannings=_plannings(lecteur),
    )


def _champ_planning(zone: int, jour: int, octet: int) -> str:
    return f"P{zone}{jour}{octet}"


def _plannings(lecteur: _LecteurPage) -> dict[int, tuple[tuple[bool, ...], ...]]:
    """Plannings du formulaire frm_prog, par zone : 7 jours (lundi d'abord) de 48
    demi-heures, vrai pour confort. Une zone dont un champ manque ou n'est pas un
    octet est écartée."""
    valeurs = {e.nom: (e.attributs.get("value") or "").strip()
               for e in lecteur.formulaires.get(FORMULAIRE_PLANNING, [])}
    plannings = {}
    for zone in range(ZONE_ECS + 1):
        jours = []
        for jour in range(JOURS):
            brut = [valeurs.get(_champ_planning(zone, jour, o), "") for o in range(OCTETS_PAR_JOUR)]
            if not all(v.isdigit() and int(v) <= 255 for v in brut):
                break
            jours.append(creneaux_depuis_octets([int(v) for v in brut]))
        else:
            plannings[zone] = tuple(jours)
    return plannings


def creneaux_depuis_octets(octets: Sequence[int]) -> tuple[bool, ...]:
    """6 octets de la carte vers 48 demi-heures : la demi-heure i est le bit i % 8 de
    l'octet i // 8, à 1 pour confort."""
    return tuple(bool(octets[i // 8] >> (i % 8) & 1) for i in range(CRENEAUX))


def octets_depuis_creneaux(creneaux: Sequence[bool]) -> list[int]:
    """48 demi-heures vers les 6 octets de la carte."""
    octets = [0] * OCTETS_PAR_JOUR
    for i, confort in enumerate(creneaux):
        if confort:
            octets[i // 8] |= 1 << (i % 8)
    return octets


def _heure(creneau: int, compact: bool) -> str:
    heures, demie = divmod(creneau, 2)
    if compact:
        return f"{heures}:30" if demie else str(heures)
    return f"{heures:02d}:{30 * demie:02d}"


def texte_planning(creneaux: Sequence[bool], compact: bool = False) -> str:
    """Plages de confort d'une journée, par exemple « 06:00-08:00, 18:00-24:00 », ou
    « 6-8,18:30-24 » en compact (tient en 255 caractères même pour 24
    plages). Chaîne vide quand toute la journée est en réduit."""
    plages, debut = [], None
    for i, confort in enumerate([*creneaux, False]):
        if confort and debut is None:
            debut = i
        elif not confort and debut is not None:
            plages.append(f"{_heure(debut, compact)}-{_heure(i, compact)}")
            debut = None
    return ("," if compact else ", ").join(plages)


def lire_texte_planning(texte: str) -> tuple[bool, ...]:
    """Plages de confort saisies (« 6:00-8:30, 18h-24h », « 6-8:30 ») vers 48 demi-heures.
    Les heures tombent sur une demi-heure, de 00:00 à 24:00 ; les plages peuvent se
    chevaucher. Lève ReglageRefuse sur une saisie illisible."""
    creneaux = [False] * CRENEAUX
    for morceau in re.split(r"[,;]", texte):
        morceau = morceau.strip()
        if not morceau:
            continue
        trouve = MOTIF_PLAGE.fullmatch(morceau)
        if not trouve:
            raise ReglageRefuse(f"plage illisible : {morceau!r} (attendu par exemple 06:00-08:30)")
        bornes = []
        for heures, minutes in (trouve.group(1, 2), trouve.group(3, 4)):
            h, m = int(heures), int(minutes or 0)
            if m not in (0, 30) or h > 24 or (h == 24 and m):
                raise ReglageRefuse(f"plage {morceau!r} : heures à la demi-heure, de 00:00 à 24:00")
            bornes.append(2 * h + m // 30)
        if bornes[0] >= bornes[1]:
            raise ReglageRefuse(f"plage {morceau!r} : le début doit précéder la fin")
        for i in range(*bornes):
            creneaux[i] = True
    return tuple(creneaux)


def corps_planning(html: str, changements: dict[tuple[int, int], Sequence[bool]]) -> dict[str, str]:
    """Corps du POST de frm_prog tel que le navigateur l'enverrait après avoir changé
    les journées demandées ((zone, jour) vers 48 demi-heures).

    Les listes de zone et de jour pointent sur le premier changement, comme après
    une saisie dans la page ; les autres listes gardent leur option choisie, ou la
    première. Lève ReglageRefuse si un champ de la journée manque.
    """
    lecteur = _analyser(html)
    elements = lecteur.formulaires.get(FORMULAIRE_PLANNING)
    if not elements:
        raise PageInattendue(f"formulaire {FORMULAIRE_PLANNING} absent de param.htm")
    nouveaux: dict[str, str] = {}
    for (zone, jour), creneaux in changements.items():
        for octet, valeur in enumerate(octets_depuis_creneaux(creneaux)):
            nouveaux[_champ_planning(zone, jour, octet)] = str(valeur)
    if changements:
        zone, jour = next(iter(changements))
        nouveaux[LISTE_ZONE_PLANNING] = str(zone)
        nouveaux[LISTE_JOUR_PLANNING] = str(jour)

    corps: dict[str, str] = {}
    for element in elements:
        nom, attributs = element.nom, element.attributs
        if not nom or "disabled" in attributs:
            continue
        if element.balise == "select":
            if element.options:
                choisies = [v for v, choisie in element.options if choisie]
                corps.setdefault(nom, choisies[-1] if choisies else element.options[0][0])
        elif element.balise == "textarea":
            corps.setdefault(nom, element.texte)
        else:
            genre = (attributs.get("type") or "text").lower()
            if genre in TYPES_IGNORES:
                continue
            if genre in ("checkbox", "radio"):
                if "checked" in attributs:
                    corps.setdefault(nom, attributs.get("value") or "on")
                continue
            corps.setdefault(nom, attributs.get("value") or "")
    manquants = [nom for nom in nouveaux if nom not in corps]
    if manquants:
        raise ReglageRefuse(f"champs de planning absents de la page : {', '.join(manquants)}")
    corps.update(nouveaux)
    return corps


def ecarts_planning(reglages: Reglages, changements: dict[tuple[int, int], Sequence[bool]]
                    ) -> dict[str, tuple[str, str | None]]:
    """Journées relues qui diffèrent de la demande : « zone/jour » vers (plages
    voulues, plages lues)."""
    trouves: dict[str, tuple[str, str | None]] = {}
    for (zone, jour), creneaux in changements.items():
        planning = reglages.plannings.get(zone)
        lu = planning[jour] if planning else None
        if lu != tuple(creneaux):
            trouves[f"planning {zone}/{jour}"] = (texte_planning(creneaux),
                                                 texte_planning(lu) if lu else None)
    return trouves


def corps_formulaire(html: str, changements: dict[str, str] | None = None) -> dict[str, str]:
    """Corps du POST de frm_params, champ par champ, tel que le navigateur l'enverrait
    après les changements demandés (nom du champ vers valeur).

    Rejoue le JavaScript de la page : listes remplies par FillUtilModeChauff, cases
    recopiées dans leur champ caché par CheckboxVal, champs désactivés par
    EnableZoneDftParamsInputs (zone à l'arrêt ou absente) et par EnableHorsGel (case
    cb02 décochée). Un champ désactivé n'est jamais transmis. Un changement qui vise
    un champ absent ou désactivé est ignoré : `champs_refuses` le signale.
    """
    changements = changements or {}
    lecteur = _analyser(html)
    listes = _modes(lecteur)
    listes.update({nom: v for nom, v in changements.items() if nom in listes})

    corps: dict[str, str] = {}
    cases: dict[str, bool] = {}
    for element in lecteur.elements:
        nom, attributs = element.nom, element.attributs
        if not nom or "disabled" in attributs:
            continue
        if element.balise == "select":
            corps[nom] = listes.get(nom, MODE_ARRET)
            continue
        if element.balise == "textarea":
            corps[nom] = element.texte
            continue
        genre = (attributs.get("type") or "text").lower()
        if genre in TYPES_IGNORES:
            continue
        if genre == "checkbox":
            cochee = "checked" in attributs
            cases[nom] = cochee
            if cochee:
                corps[nom] = "on"
            cible = MOTIF_CIBLE_CASE.search(attributs.get("onclick") or "")
            if cible:
                corps[cible.group(1)] = "1" if cochee else "0"
            continue
        corps.setdefault(nom, changements.get(nom, attributs.get("value") or ""))

    desactives: set[str] = set()
    for zone, drapeau in MOTIF_ZONE.findall("\n".join(lecteur.scripts)):
        if drapeau == "0":
            desactives.add(f"U06_{zone}")
        if listes.get(f"U06_{zone}") == MODE_ARRET:
            desactives.update(f"U{p}_{zone}" for p in ("07", "09", "10", "11"))
    if not cases.get(CASE_HORS_GEL, False):
        desactives.update(CHAMPS_HORS_GEL)
    for nom in desactives:
        corps.pop(nom, None)
    return corps


def champs_refuses(corps: dict[str, str], changements: dict[str, str]) -> list[str]:
    """Champs demandés que le corps ne transmet pas avec la valeur voulue."""
    return [nom for nom, valeur in changements.items() if corps.get(nom) != valeur]


def encoder_corps(corps: dict[str, str]) -> bytes:
    """Corps urlencodé en ISO-8859-1, l'encodage des pages de la carte."""
    return urlencode(corps, encoding=ENCODAGE).encode("ascii")


def preparer_changements(reglages: Reglages, demandes: dict[str, str | float]) -> dict[str, str]:
    """Contrôle les changements demandés et les met au format de la page.

    Seuls les modes (U06_x) et les consignes (U09_x, U10_x) des zones présentes sont
    acceptés. Un mode vaut 0, 1 ou 2 ; une consigne tient dans les bornes lues sur la
    page et s'écrit avec ses décimales. Lève ReglageRefuse sinon.
    """
    zones = {zone.index: zone for zone in reglages.zones}
    prets: dict[str, str] = {}
    for nom, valeur in demandes.items():
        trouve = MOTIF_CHAMP_ZONE.fullmatch(nom)
        if not trouve:
            raise ReglageRefuse(f"{nom} : champ non pris en charge")
        zone = zones.get(int(trouve.group(2)))
        if zone is None:
            raise ReglageRefuse(f"{nom} : zone absente de la carte")
        if trouve.group(1) == "06":
            if str(valeur) not in MODES:
                raise ReglageRefuse(f"{nom} : mode {valeur!r} inconnu")
            prets[nom] = str(valeur)
            continue
        consigne = zone.confort if trouve.group(1) == "09" else zone.reduit
        try:
            nombre = float(valeur)
        except (TypeError, ValueError):
            raise ReglageRefuse(f"{nom} : {valeur!r} n'est pas un nombre") from None
        if consigne.minimum is None or consigne.maximum is None:
            raise ReglageRefuse(f"{nom} : bornes absentes de la page")
        if not consigne.minimum <= nombre <= consigne.maximum:
            raise ReglageRefuse(
                f"{nom} : {nombre} hors des bornes {consigne.minimum} à {consigne.maximum}")
        prets[nom] = f"{nombre:.{consigne.decimales}f}"
    return prets


def ecarts(html: str, changements: dict[str, str]) -> dict[str, tuple[str, str | None]]:
    """Compare la page relue aux changements demandés. Rend, pour chaque champ qui
    diffère, (valeur voulue, valeur lue) ; les nombres se comparent comme nombres."""
    lecteur = _analyser(html)
    modes = _modes(lecteur)
    trouves: dict[str, tuple[str, str | None]] = {}
    for nom, voulu in changements.items():
        if nom in modes:
            lu = modes[nom]
        elif nom in lecteur.champs:
            lu = (lecteur.champs[nom].attributs.get("value") or "").strip()
        else:
            lu = None
        if lu == voulu or (lu and _nombre(lu) is not None and _nombre(lu) == _nombre(voulu)):
            continue
        trouves[nom] = (voulu, lu)
    return trouves
