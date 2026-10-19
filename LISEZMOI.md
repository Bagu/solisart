# SolisArt pour Home Assistant

[English version](README.md)

Une intégration personnalisée qui lit et règle une carte de régulation SolisArt
(chauffage solaire) depuis Home Assistant. Je l'ai écrite pour ma propre installation
et je l'ai gardée générique. Les zones, leurs libellés et leurs bornes se lisent sur la
carte : rien de ma maison n'est écrit dans le code.

Ce projet n'a aucun lien avec la société SolisArt.

## Ce qu'elle lit

La carte publie `/XML/status.xml` sur son interface web. Chaque valeur de cette page
devient une entité :

- sondes de température `T1` à `T16` (°C). Une sonde que la carte signale débranchée
  (`Dsc`) est créée désactivée, et devient indisponible si elle se débranche plus tard ;
- circulateurs `TRIAC1` à `TRIAC13` et les deux vannes trois voies, en % ;
- débitmètres `FL1` à `FL5`, en L/min ;
- relais (`MREL1`, `SREL1`...), marche ou arrêt.

Les entités portent le nom des balises de la carte. Ce que mesure chaque sonde dépend du
montage de votre installation : la page Visualisation de la carte l'indique. Renommez-les
dans Home Assistant une fois que vous le savez.

L'intégration lit aussi `/param.htm` (la page Utilisateur) toutes les 5 minutes : zones,
libellés, modes, consignes, ainsi que les versions de la carte et de son interface web.

## Ce qu'elle règle

Pour chaque zone présente sur la carte (zones de chauffage et eau chaude), l'intégration
ajoute :

- le choix du mode : arrêt, soleil seul, ou soleil et appoint ;
- les consignes de confort et de réduit, en °C. Leurs bornes viennent de la page de la
  carte. Elles sont indisponibles tant que la zone est à l'arrêt, car la carte les
  verrouille alors.

Les entités prennent les libellés des zones saisis sur la carte (par exemple « Mode
RDC »).

Pour changer une valeur, l'intégration fait comme votre navigateur sur la page
Utilisateur. Elle lit `param.htm`, renvoie le formulaire complet avec la nouvelle valeur,
puis relit la page pour vérifier que la carte l'a gardée. Si la valeur n'a pas été prise,
Home Assistant affiche une erreur. Les changements faits à moins de 1,5 s d'intervalle
partent ensemble en un seul envoi : cinq clics sur les flèches d'une consigne n'envoient
que la dernière valeur.

## Prérequis

- Une carte SolisArt joignable sur le réseau local, avec son interface web. Je l'ai
  essayée avec le logiciel de carte `SRB_32MX_vD.50-5` et l'interface web `WEB_vA.98`.
- L'identifiant de la page Utilisateur de la carte.
- Home Assistant 2026.10. Je n'ai pas essayé les versions plus anciennes.

## Installation

Avec HACS : ajoutez ce dépôt comme dépôt personnalisé (type Intégration), installez
« SolisArt », puis redémarrez Home Assistant.

À la main : copiez `custom_components/solisart` dans le dossier `custom_components` de
votre configuration Home Assistant, puis redémarrez.

Ensuite : Paramètres, Appareils et services, Ajouter une intégration, SolisArt. Saisissez
l'adresse de la carte (par exemple `192.168.1.20`) et l'identifiant de son interface web.

Options : rythme de lecture de `status.xml` (30 s par défaut) et de `param.htm` (300 s
par défaut). La carte met près d'une seconde à produire `param.htm` : je ne la lirais
pas beaucoup plus souvent.

## Avant de vous y fier

- SolisArt ne publie pas d'interface de programmation. L'intégration lit les mêmes pages
  que votre navigateur. Une mise à jour du logiciel de la carte peut les changer et la
  casser.
- Un seul outil doit modifier les réglages de la carte. Si deux outils écrivent sur
  `param.htm`, chacun écrase ce que l'autre vient de régler.
- Chaque changement renvoie tout le formulaire de la page Utilisateur. Les autres
  réglages de cette page repartent tels que l'intégration vient de les lire.
- L'intégration donne à Home Assistant l'accès à la carte, rien de plus. Décider quand
  chauffer avec le surplus solaire ou en heures creuses revient à vos automatisations.

## Développement

```
python -m unittest discover tests
.venv/Scripts/python -m pytest
```

La première commande vérifie la lecture des pages, sur de vraies pages enregistrées
depuis une carte et anonymisées. La seconde fait tourner l'intégration dans un Home
Assistant de test ; elle demande `pytest-homeassistant-custom-component` dans un
environnement virtuel. Sous Windows, la précéder de `PYTHONPATH=tests/ha/windows` : ce
dossier contient des remplaçants vides de deux modules propres à Unix que Home Assistant
importe.

`outils/contre_epreuve.py` et `outils/contre_epreuve_ha.py` cassent le code exprès, un
défaut à la fois, et vérifient que les tests attrapent chacun d'eux. Le premier prend le
Python de `.venv` s'il existe, car les tests du client demandent aiohttp.

`tests/fixtures/corps_reference.json` garde les corps du formulaire qu'un script déjà
éprouvé sur une vraie carte construit à partir de la page de test et de ses variantes.
Les tests vérifient que l'intégration produit les mêmes octets.
`outils/parite_reference.py` refait ce fichier.

`outils/anonymiser.py` transforme une page `param.htm` enregistrée depuis votre carte en
page de test. Il masque le nom de l'installation et les identifiants. Il refuse d'écrire
le fichier s'il y reste une adresse IP, une adresse MAC ou un courriel.
