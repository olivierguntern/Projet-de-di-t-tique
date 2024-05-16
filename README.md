# Application de Suivi Nutritionnel

## Contexte et Objectif
Ce projet vise à développer une application pour la santé publique, permettant de suivre et d'analyser la consommation quotidienne de graisses. L'objectif principal est d'aider les utilisateurs à maintenir un équilibre nutritionnel sain en surveillant la quantité et la qualité des graisses consommées.

## Utilisation des Données
Les données utilisées proviennent de la base de données open source [Open Food Facts](https://fr.openfoodfacts.org/), qui contient des informations sur les produits alimentaires commercialisés dans le monde entier. Cette base de données, bien que riche, présente des limitations en termes de fiabilité et d'exactitude des informations, ce qui a été pris en compte lors de l'analyse.

## Étapes du Projet
### 1. Nettoyage des Données
- **Traitement des valeurs manquantes** : Suppression ou imputation des valeurs manquantes.
- **Détection et gestion des incohérences** : Identification et correction des données incohérentes.
- **Filtrage des variables et individus** : Sélection des variables pertinentes pour l'analyse (par exemple, types de graisses comme les oméga-3, oméga-6, graisses saturées, etc.).

### 2. Exploration des Données
- **Analyse univariée** : Étude des distributions de chaque variable (graisses totales, graisses saturées, etc.).
- **Analyse multivariée** : Corrélations entre différentes types de graisses et utilisation de l'ANOVA pour identifier les relations significatives.
- **Détection des outliers** : Gestion des valeurs extrêmes sans les exclure, car elles peuvent être pertinentes pour certains aliments (ex : huiles, fromages).

### 3. Développement de l'Application
- **Fonctionnalité de Scan** : Permet à l'utilisateur de scanner les produits alimentaires pour obtenir instantanément des informations nutritionnelles.
- **Suivi Journalier** : Stockage des données scannées pour un suivi quotidien de la consommation de graisses.
- **Propositions d'Aliments Alternatifs** : Suggère des alternatives plus saines en fonction des taux de graisses des produits consommés.

## Méthodologies et Techniques Utilisées
- **Manipulation des données** avec Pandas pour la lecture, l'écriture, le filtrage et l'agrégation des données.
- **Visualisation des données** avec Matplotlib et Seaborn pour créer des graphiques et des tableaux de corrélation.
- **Analyse statistique** avec des techniques comme l'ANOVA et les tableaux de corrélation de Kendall pour comprendre les relations entre différentes variables nutritionnelles.

## Résultats et Conclusions
- Création d'une base de données cohérente sur les graisses alimentaires, permettant des analyses fiables malgré les limitations initiales des données.
- Développement d'une application fonctionnelle qui peut aider les utilisateurs à mieux gérer leur consommation de graisses et à faire des choix alimentaires plus sains.
- L'application peut indiquer les carences ou les excès de graisses et proposer des alternatives nutritionnelles plus équilibrées.

## Perspectives d'Avenir
- Amélioration continue de l'application avec des mises à jour régulières des données et des fonctionnalités supplémentaires basées sur les retours des utilisateurs.
- Intégration avec d'autres bases de données nutritionnelles pour enrichir les informations fournies.
- Expansion des fonctionnalités pour inclure le suivi d'autres aspects nutritionnels, comme les vitamines et les minéraux.

## Compétences et Techniques Utilisées

### Nettoyage de données
- **Traitement des valeurs manquantes**
- **Détection et gestion des données incohérentes**
- **Suppression des variables et des individus non pertinents**

### Exploration de données
- **Analyse univariée** :
  - Statistiques descriptives
  - Distribution des données
- **Analyse multivariée** :
  - Corrélations
  - ANOVA
- **Détection et gestion des outliers**
- **Utilisation de bases de données open source** :
  - Open Food Facts (base de données libre et ouverte sur les produits alimentaires)

### Visualisation de données
- **Création de graphiques** pour l'exploration des variables et des distributions
- **Tableaux de corrélation**

### Compétences en Programmation
- **Manipulation de DataFrame avec Pandas** :
  - Lecture et écriture de fichiers de données
  - Sélection et filtrage de données
  - Agrégation et transformation des données
- **Utilisation de bibliothèques de visualisation** :
  - Matplotlib
  - Seaborn

### Compétences en Statistiques
- **Statistiques descriptives** :
  - Calcul des moyennes, médianes, variances, écart-types, quartiles
  - Calcul des pourcentages de valeurs remplies
- **Analyse de la variance (ANOVA)** :
  - Test de l'hypothèse de corrélation entre différentes variables
- **Calcul de corrélations** :
  - Tableau de corrélation de Kendall

### Compétences en Développement d'Applications
- **Développement d'une application pour la santé publique** :
  - Conception d'une application de suivi de la consommation de graisses
  - Utilisation de la base de données Open Food Facts pour récupérer les informations nutritionnelles
  - Fonctionnalité de scan des produits et stockage des données pour un suivi journalier
  - Proposition d'alternatives alimentaires basées sur les taux de graisses

### Compétences en Gestion de Projet
- **Définition des objectifs et des variables** :
  - Choix des variables pertinentes pour l'analyse (graisses totales, graisses saturées, graisses monoinsaturées, etc.)
  - Définition des objectifs de l'application de santé (équilibre de la consommation en lipides, suivi des graisses consommées)

### Compétences en Communication et Présentation
- **Rédaction de rapports et de présentations** :
  - Création de supports de présentation détaillant les étapes du projet, les analyses effectuées et les conclusions
  - Explication des résultats statistiques et des implications pour l'application de santé
