# SolisArt pour Home Assistant

[English version](README.md)

Une intégration Home Assistant pour suivre et piloter un régulateur de chauffage solaire
SolisArt. Je l'ai écrite pour mon propre système en gardant une approche générique : les
zones, les libellés et les limites sont lus directement depuis le régulateur. Rien de
spécifique à ma maison n'est codé en dur.

## Avertissement

Je ne travaille pas pour SolisArt, et ce projet n'a aucun lien avec la société. Le logo
affiché dans Home Assistant est le sien. J'ai écrit l'intégration pour ma propre
installation et je la partage telle quelle. Vous l'utilisez à vos risques. Je ne prends
aucune responsabilité en cas de mauvais usage, de réglage inadapté, de dommage à
l'installation, de surcoût d'énergie ou de toute autre conséquence de son utilisation.
La licence MIT dit la même chose.

## Ce que ça lit

Le régulateur publie un fichier `/XML/status.xml` sur son interface web. Chaque valeur
reconnue devient une entité dans Home Assistant :

- Les sondes de température (`T1` à `T16`) en °C. Une sonde déclarée déconnectée (`Dsc`)
  est créée désactivée, et passe à l'état indisponible si elle se déconnecte en cours de
  route.
- Les circulateurs (`TRIAC1` à `TRIAC13`) et les deux vannes trois voies, en %.
- Les débitmètres (`FL1` à `FL5`), en L/min.
- Les relais (`MREL1`, `SREL1`...), en marche ou à l'arrêt.

Les entités prennent le nom des balises du régulateur. Le rôle de chaque sonde dépend de
votre installation (visible sur la page Visualisation du régulateur). Vous pourrez les
renommer facilement dans Home Assistant.

L'intégration lit aussi la page Utilisateur (`/param.htm`) toutes les 5 minutes pour
récupérer les zones, leurs libellés, leurs modes, leurs consignes, ainsi que les versions
du régulateur et de l'interface web.

## Ce que ça pilote

Pour chaque zone gérée par le régulateur (chauffage et eau chaude sanitaire),
l'intégration ajoute :

- Un sélecteur de mode : Arrêt, Soleil seul, ou Soleil et appoint.
- Les consignes de confort et de réduit (en °C). Leurs limites proviennent directement du
  régulateur. Elles s'affichent comme indisponibles quand la zone est à l'arrêt, car le
  régulateur les verrouille alors.
- Le planning horaire (confort/réduit), sous forme d'une entité texte par jour (par
  exemple « Planning Rez-de-chaussée lundi »). On y indique les plages de confort comme
  `06:00-08:30, 18:00-22:00`, le reste de la journée étant en réduit. Une valeur vide
  signifie « réduit toute la journée ». Les heures vont à la demi-heure, et `6-8:30` ou
  `18h-22h` conviennent aussi. Ces entités sont rangées dans la partie Configuration de
  l'appareil.

Les entités prennent les libellés des zones saisis sur le régulateur (par exemple « Mode
Rez-de-chaussée »).

L'action `solisart.copier_planning` permet de copier un planning d'un jour sur d'autres
jours ou d'autres zones en une seule fois (par exemple, du lundi pour tout le reste de la
semaine).

Pour modifier une valeur, l'intégration se comporte comme votre navigateur : elle lit
`param.htm`, renvoie le formulaire complet avec la nouvelle valeur, puis relit la page
pour s'assurer que le régulateur l'a bien enregistrée. Si la modification échoue, Home
Assistant affiche une erreur.

Les modifications espacées de moins de 1,5 seconde sont regroupées en une seule requête :
si vous cliquez cinq fois d'affilée sur les flèches d'une consigne, seule la dernière
valeur est envoyée.

## Prérequis

- Un régulateur SolisArt accessible sur votre réseau local (testé avec le logiciel
  `SRB_32MX_vD.50-5` et l'interface web `WEB_vA.98`).
- Les identifiants de la page Utilisateur de votre régulateur.
- Home Assistant 2026.10 ou plus récent. HACS refuse les versions plus anciennes.

## Installation

### Via HACS (recommandé)

HACS doit déjà être installé dans votre Home Assistant.

1. Ouvrez HACS dans la barre latérale de Home Assistant.
2. Cliquez sur les trois points en haut à droite, puis sur Dépôts personnalisés.
3. Collez l'adresse `https://github.com/Bagu/solisart`, sélectionnez le type Intégration,
   puis cliquez sur Ajouter.
4. Recherchez SolisArt dans HACS et téléchargez-la.
5. Redémarrez Home Assistant.

Ce bouton ouvre directement le dépôt dans votre HACS :

[![Ouvrir le dépôt SolisArt dans HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Bagu&repository=solisart&category=integration)

### Installation manuelle

Copiez le dossier `custom_components/solisart` dans le répertoire `custom_components` de
votre configuration Home Assistant, puis redémarrez.

### Configuration

Dans Home Assistant, allez dans Paramètres > Appareils et services > Ajouter une
intégration, cherchez SolisArt et entrez l'adresse IP du régulateur (par exemple
`192.168.1.20`) ainsi que vos identifiants.

Le régulateur n'expose aucun numéro de série : l'intégration le reconnaît donc à son
adresse. Si l'adresse change (nouveau routeur, nouveau bail DHCP), ouvrez le menu de
l'entrée de l'intégration (les trois points) et choisissez Reconfigurer. Vous pouvez y
saisir la nouvelle adresse ou un nouvel identifiant, et les entités conservent leur nom
et leur historique. Laissez le mot de passe vide pour conserver celui enregistré.

Dans les options, vous pouvez régler le rythme de lecture de `status.xml` (30 s par
défaut) et de `param.htm` (300 s par défaut). Le régulateur met près d'une seconde à
produire `param.htm` : je ne la lirais pas beaucoup plus souvent. La dernière option
autorise les modifications sur une version du régulateur non testée (voir plus bas).
Par défaut, elle reste désactivée.

## À savoir avant de l'utiliser

- Pas d'API officielle : SolisArt ne propose pas d'API. Cette intégration lit et écrit
  sur les pages de l'interface web. Une mise à jour logicielle du régulateur peut casser
  son fonctionnement.
- Un seul pilote : un seul outil doit modifier les réglages du régulateur. Chaque
  modification renvoie tout le formulaire de la page Utilisateur, avec les autres
  réglages tels que l'intégration vient de les lire. Si un autre outil écrit aussi sur
  `param.htm`, chacun écrase ce que l'autre vient de régler.
- Identifiant en clair : le régulateur ne répond qu'en HTTP simple. L'identifiant de sa
  page Utilisateur part donc avec chaque lecture de `param.htm` et chaque modification,
  et toute personne qui peut observer votre réseau local peut le lire. Gardez le
  régulateur sur un réseau de confiance, avec un mot de passe que vous n'utilisez nulle
  part ailleurs.
- Versions testées : l'intégration ne modifie les réglages qu'avec le logiciel
  `SRB_32MX_vD.50-5` et l'interface web `WEB_vA.98`. Sur une autre version, la lecture
  continue, mais toute modification est refusée, et Home Assistant affiche un message
  dans Paramètres, Système, Réparations avec les versions trouvées. Si tout fonctionne
  chez vous, ouvrez un ticket avec ces versions pour que je les ajoute à la liste. Les
  options permettent aussi d'autoriser les modifications sur une version non testée, à
  vos risques.
- Gestion externe : l'intégration donne accès au matériel depuis Home Assistant, mais
  c'est à vous de créer vos automatisations (par exemple pour chauffer en heures creuses
  ou profiter du surplus solaire).

## Développement et tests

```
python -m unittest discover tests
.venv/Scripts/python -m pytest
```

Le premier jeu de tests vérifie la lecture des pages à partir de fichiers de référence
enregistrés sur un vrai régulateur et anonymisés. Le second lance l'intégration au sein
d'un environnement de test Home Assistant (nécessite
`pytest-homeassistant-custom-component` dans un environnement virtuel). Sous Windows,
précédez-le de `PYTHONPATH=tests/ha/windows` : ce dossier contient des remplaçants vides
de deux modules propres à Unix que Home Assistant importe.

`outils/contre_epreuve.py` et `outils/contre_epreuve_ha.py` cassent le code exprès, un
défaut à la fois, et vérifient que les tests attrapent chacun d'eux. Le premier prend le
Python de `.venv` s'il existe, car les tests du client demandent aiohttp.

`tests/fixtures/corps_reference.json` conserve les corps du formulaire qu'un script déjà
éprouvé sur un vrai régulateur construit à partir de la page de test et de ses variantes.
Les tests vérifient que l'intégration produit exactement les mêmes octets.
`outils/parite_reference.py` refait ce fichier.

`outils/anonymiser.py` transforme une page `param.htm` enregistrée depuis votre
régulateur en page de test. Il masque le nom de l'installation et les identifiants. Il
refuse d'écrire le fichier s'il y reste une adresse IP, une adresse MAC ou un courriel.

## Licence

Ce projet est sous licence MIT (voir [LICENSE](LICENSE) et [NOTICE](NOTICE)).

Note concernant la marque : le nom et le logo SolisArt (ainsi que les images du dossier
`custom_components/solisart/brand`) appartiennent à la société SolisArt. La licence ne
les couvre pas : ils sont uniquement présents pour vous permettre de reconnaître
facilement le matériel dans Home Assistant.
