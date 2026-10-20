# SolisArt pour Home Assistant

[English version](README.md)

Une intégration Home Assistant pour suivre et piloter une carte de régulation de chauffage solaire
SolisArt. Je l'ai écrite pour mon propre système en gardant une approche générique : les
zones, les libellés et les limites sont lus directement depuis la carte de régulation. Rien de
spécifique à ma maison n'est codé en dur.

## Avertissement

Je ne travaille pas pour SolisArt, et ce projet n'a aucun lien avec la société. Le logo
affiché dans Home Assistant est le sien. J'ai écrit l'intégration pour ma propre
installation et je la partage telle quelle. Vous l'utilisez à vos risques. Je ne prends
aucune responsabilité en cas de mauvais usage, de réglage inadapté, de dommage à
l'installation, de surcoût d'énergie ou de toute autre conséquence de son utilisation.
La licence MIT dit la même chose.

## Ce que ça lit

La carte de régulation publie un fichier `/XML/status.xml` sur son interface web. Chaque valeur
reconnue devient une entité dans Home Assistant :

- Les sondes de température (`T1` à `T16`) en °C. Une sonde déclarée déconnectée (`Dsc`)
  est créée désactivée, et passe à l'état indisponible si elle se déconnecte en cours de
  route.
- Les circulateurs (`TRIAC1` à `TRIAC13`) et les deux vannes trois voies, en %.
- Les débitmètres (`FL1` à `FL5`), en L/min.
- Les relais (`MREL1`, `SREL1`...), en marche ou à l'arrêt.

Les entités prennent le nom des balises de la carte de régulation. Le rôle de chaque sonde dépend de
votre installation (visible sur la page Visualisation de la carte de régulation). Vous pourrez les
renommer facilement dans Home Assistant.

L'intégration lit aussi la page Utilisateur (`/param.htm`) toutes les 5 minutes pour
récupérer les zones, leurs libellés, leurs modes de chauffage, leurs températures de confort et de réduit, ainsi que les versions
de la carte de régulation et de l'interface web.

Chaque zone reçoit aussi un capteur de plage en cours : Confort ou Réduit, selon la demi-heure
de sa programmation horaire qui s'applique en ce moment. Pour cela, l'intégration lit l'horloge de la
carte de régulation elle-même (`/XML/dtstat.xml`, sans identifiant, au même rythme que
`status.xml`) : un décalage d'heure entre Home Assistant et la carte de régulation ne change donc
rien. Si cette page ne répond pas, la plage en cours s'affiche comme indisponible et tout le
reste continue de fonctionner.

## Ce que ça pilote

Pour chaque zone gérée par la carte de régulation (chauffage et eau chaude sanitaire),
l'intégration ajoute :

- Le mode de chauffage, avec les libellés de la page Utilisateur de la carte de régulation : Arrêt,
  Solaire (soleil seul) ou Sol/App (soleil et appoint).
- Les températures de confort et de réduit (en °C). Leurs limites proviennent directement de la
  carte de régulation. Elles s'affichent comme indisponibles quand la zone est à l'arrêt, car la
  carte de régulation les verrouille alors.
- La programmation horaire (confort/réduit), sous forme d'une entité texte par jour (par
  exemple « Programmation Rez-de-chaussée lundi »). On y indique les plages de confort comme
  `06:00-08:30, 18:00-22:00`, le reste de la journée étant en réduit. Une valeur vide
  signifie « réduit toute la journée ». Les heures vont à la demi-heure, et `6-8:30` ou
  `18h-22h` conviennent aussi. Ces entités sont rangées dans la partie Configuration de
  l'appareil.

Chaque zone de chauffage reçoit aussi un thermostat, et l'eau chaude un chauffe-eau,
pour les tableaux de bord et les assistants vocaux :

- Thermostat : Arrêt pour le mode Arrêt de la carte de régulation, Chauffage pour les deux autres
  modes, que le préréglage distingue (Solaire ou Sol/App). Le rallumer
  remet le dernier préréglage. La température cible est la température de confort, et
  la température de réduit apparaît en attribut.
- Chauffe-eau : Arrêt, Solaire ou Sol/App, rangés sous les modes standard
  de Home Assistant `off`, `eco` et `performance`, avec la température de confort de l'eau
  chaude comme cible.
- La température actuelle vient de la sonde que vous choisissez pour chaque zone dans les
  options. Il n'y en a aucune par défaut, car la sonde d'une pièce dépend de
  l'installation.

Les entités prennent les libellés des zones saisis sur la carte de régulation (par exemple « Mode de
chauffage Rez-de-chaussée »).

L'action `solisart.copier_planning` permet de copier la programmation d'un jour sur d'autres
jours ou d'autres zones en une seule fois (par exemple, du lundi pour tout le reste de la
semaine).

Pour modifier une valeur, l'intégration se comporte comme votre navigateur : elle lit
`param.htm`, renvoie le formulaire complet avec la nouvelle valeur, puis relit la page
pour s'assurer que la carte de régulation l'a bien enregistrée. Si la modification échoue, Home
Assistant affiche une erreur.

Les modifications espacées de moins de 1,5 seconde sont regroupées en une seule requête :
si vous cliquez cinq fois d'affilée sur les flèches d'une température, seule la dernière
valeur est envoyée.

## Prérequis

- Une carte de régulation SolisArt accessible sur votre réseau local (testée avec le logiciel
  `SRB_32MX_vD.50-5` et l'interface web `WEB_vA.98`).
- Les identifiants de la page Utilisateur de votre carte de régulation.
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
intégration, cherchez SolisArt et entrez l'adresse IP de la carte de régulation (par exemple
`192.168.1.20`) ainsi que vos identifiants.

La carte de régulation n'expose aucun numéro de série : l'intégration la reconnaît donc à son
adresse. Si l'adresse change (nouveau routeur, nouveau bail DHCP), ouvrez le menu de
l'entrée de l'intégration (les trois points) et choisissez Reconfigurer. Vous pouvez y
saisir la nouvelle adresse ou un nouvel identifiant, et les entités conservent leur nom
et leur historique. Laissez le mot de passe vide pour conserver celui enregistré.

Dans les options, vous pouvez régler le rythme de lecture de `status.xml` (30 s par
défaut) et de `param.htm` (300 s par défaut). La carte de régulation met près d'une seconde à
produire `param.htm` : mieux vaut ne pas la lire beaucoup plus souvent. Une autre option
autorise les modifications sur une version de la carte de régulation non testée (voir plus bas).
Par défaut, elle reste désactivée. Les derniers champs servent à choisir la sonde de
température de chaque zone pour les thermostats et le chauffe-eau.

## À savoir avant de l'utiliser

- Pas d'API officielle : SolisArt ne propose pas d'API. Cette intégration lit et écrit
  sur les pages de l'interface web. Une mise à jour logicielle de la carte de régulation peut casser
  son fonctionnement.
- Un seul pilote : un seul outil doit modifier les réglages de la carte de régulation. Chaque
  modification renvoie tout le formulaire de la page Utilisateur, avec les autres
  réglages tels que l'intégration vient de les lire. Si un autre outil écrit aussi sur
  `param.htm`, chacun écrase ce que l'autre vient de régler.
- Identifiant en clair : la carte de régulation ne répond qu'en HTTP simple. L'identifiant de sa
  page Utilisateur part donc avec chaque lecture de `param.htm` et chaque modification,
  et toute personne qui peut observer votre réseau local peut le lire. Gardez la
  carte de régulation sur un réseau de confiance, avec un mot de passe que vous n'utilisez nulle
  part ailleurs.
- Versions testées : l'intégration ne modifie les réglages qu'avec le logiciel
  `SRB_32MX_vD.50-5` et l'interface web `WEB_vA.98`. Sur une autre version, la lecture
  continue, mais toute modification est refusée, et Home Assistant affiche un message
  dans Paramètres, Système, Réparations avec les versions trouvées. Si tout fonctionne
  chez vous, ouvrez un ticket avec ces versions pour les faire ajouter à la liste. Les
  options permettent aussi d'autoriser les modifications sur une version non testée, à
  vos risques.
- Gestion externe : l'intégration donne accès au matériel depuis Home Assistant, mais
  c'est à vous de créer vos automatisations (par exemple pour chauffer en heures creuses
  ou profiter du surplus solaire).
- Signaler un problème : joignez le diagnostic de l'intégration et, si le problème touche
  la page Utilisateur, une copie de `param.htm` passée par
  `python outils/anonymiser.py param.htm param_anonyme.htm`, qui masque le nom de
  l'installation et les identifiants (détails en anglais dans
  [CONTRIBUTING.md](CONTRIBUTING.md)).

## Licence

Ce projet est sous licence MIT (voir [LICENSE](LICENSE) et [NOTICE](NOTICE)).

Note concernant la marque : le nom et le logo SolisArt (ainsi que les images du dossier
`custom_components/solisart/brand`) appartiennent à la société SolisArt. La licence ne
les couvre pas : ils sont uniquement présents pour vous permettre de reconnaître
facilement le matériel dans Home Assistant.
