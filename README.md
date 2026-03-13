# Outils d'Analyse OCR — Capture & Cycles

Suite de scripts Python pour **capturer des valeurs numériques à l'écran par OCR**,
les nettoyer, et analyser leurs patterns et cycles temporels.

---

## Pipeline complet

```
Écran
  │
  ▼
capture_ecran.py        →  captures/capture_YYYYMMDD_HHMMSS.png
  │
  ▼
selection_zones.py      →  zones_YYYYMMDD_HHMMSS.csv
  │
  ▼
ocr_zones.py            →  resultats_ocr_YYYYMMDD_HHMMSS.csv
  │
  ▼
filtrer_ocr.py          →  {nom}_chiffres.csv
  │
  ▼
dedupliquer_ocr.py      →  {nom}_dedup.csv
  │
  ├──▶ analyser_patterns.py
  ├──▶ comprendre_patterns.py
  ├──▶ analyser_cycles.py
  └──▶ predire_seuil.py
```

---

## Lancement rapide

```bash
python launcher.py
```

Interface graphique avec un onglet par script, console de sortie intégrée,
et suggestions automatiques des noms de fichiers.

---

## Scripts

### 1. `capture_ecran.py` — Capture automatique

Prend une capture d'écran toutes les **10 secondes** pendant N minutes.

```bash
python capture_ecran.py --duree 5
python capture_ecran.py --duree 10 --dossier mes_captures --delai 5 --ecran 2
```

| Argument | Défaut | Description |
|---|---|---|
| `--duree` | — | Durée en minutes (obligatoire) |
| `--dossier` | `captures` | Dossier de sortie |
| `--delai` | `3` | Secondes d'attente avant démarrage |
| `--ecran` | `1` | Numéro d'écran |

**Sortie :** `captures/capture_YYYYMMDD_HHMMSS.png`

---

### 2. `selection_zones.py` — Sélection de zones

Ouvre une image (ou capture d'écran) et permet de dessiner des zones
rectangulaires à la souris pour définir les régions à analyser par OCR.

```bash
python selection_zones.py
python selection_zones.py --image mon_image.png --csv mes_zones.csv
```

**Contrôles :** clic+glisser pour tracer · Entrée pour valider · Z pour annuler · Q pour quitter

**Sortie :** `zones_YYYYMMDD_HHMMSS.csv`

---

### 3. `ocr_zones.py` — OCR par zone

Applique l'OCR sur chaque zone de chaque image d'un répertoire.

```bash
python ocr_zones.py --zones zones.csv --images ./captures
python ocr_zones.py --zones zones.csv --images ./captures --engine easyocr --preprocess neon
```

| Argument | Défaut | Description |
|---|---|---|
| `--zones` | — | CSV des zones (obligatoire) |
| `--images` | `.` | Répertoire d'images |
| `--out` | auto | CSV de sortie |
| `--engine` | `tesseract` | Moteur OCR : `tesseract` \| `easyocr` |
| `--preprocess` | `auto` | Prétraitement : `auto` \| `neon` \| `aucun` |
| `--debug` | — | Sauvegarde les zones découpées |

**Sortie :** `resultats_ocr_YYYYMMDD_HHMMSS.csv`

---

### 4. `filtrer_ocr.py` — Filtrage des chiffres

Ne conserve que les lignes dont `texte_ocr` contient une valeur décimale valide
(format `chiffre.chiffre`). Trace une courbe par zone.

```bash
python filtrer_ocr.py --input resultats_ocr_20260313_120000.csv
python filtrer_ocr.py --input resultats_ocr.csv --out propre.csv --graph courbe.png
```

**Sortie :** `{nom_entrée}_chiffres.csv`

---

### 5. `dedupliquer_ocr.py` — Suppression des doublons consécutifs

Élimine les valeurs identiques qui se suivent.
`1.2, 1.2, 1.2, 1.5, 1.5` → `1.2, 1.5`

```bash
python dedupliquer_ocr.py --input resultats_ocr_chiffres.csv
python dedupliquer_ocr.py --input resultats_ocr_chiffres.csv --out propre.csv
```

**Sortie :** `{nom_entrée}_dedup.csv`

---

### 6. `analyser_patterns.py` — Détection de patterns

Tests statistiques sur les séries temporelles pour déterminer si les valeurs
sont aléatoires ou structurées.

- Autocorrélation (lags 1–5)
- Test de stationnarité ADF
- Test de runs (Wald–Wolfowitz)
- Variance glissante
- Régression linéaire (pente)

```bash
python analyser_patterns.py --input resultats_ocr_chiffres.csv
python analyser_patterns.py --input f.csv --graph patterns.png --alpha 0.05
```

---

### 7. `comprendre_patterns.py` — Analyse approfondie

Étend `analyser_patterns.py` avec des méthodes avancées.

- FFT / Spectre de puissance → période dominante
- Décomposition STL → tendance + saisonnalité + résidu
- Détection de points de rupture (PELT)
- Clustering temporel k-means → régimes distincts
- Corrélation croisée inter-zones

```bash
python comprendre_patterns.py --input resultats_ocr_chiffres.csv
python comprendre_patterns.py --input f.csv --saison 7 --clusters 3 --out rapport.png
```

---

### 8. `analyser_cycles.py` — Analyse des cycles de reset

Détecte les cycles (montée → pic → reset) et calcule leur durée pour
estimer quand le prochain passage bas va survenir.

```bash
python analyser_cycles.py --input propre.csv
python analyser_cycles.py --input propre.csv --seuil-reset 1.2 --seuil-haut 2.0 --detail
```

| Argument | Défaut | Description |
|---|---|---|
| `--seuil-reset` | `1.2` | Valeur ≤ ce seuil = reset |
| `--seuil-haut` | `2.0` | Valeur ≥ ce seuil = pic atteint |
| `--detail` | — | Affiche chaque cycle individuellement |

**Exemple de sortie :**
```
Cycles détectés  : 174
Durée moyenne    : 37.9 s  (±11.3 s)
Prochaine phase basse dans ~38 s  [fourchette : 27 s – 49 s]
```

---

### 9. `predire_seuil.py` — Prévisibilité d'un seuil

Répond à la question : *les valeurs < SEUIL arrivent-elles aléatoirement
ou peut-on les prévoir ?*

- Distribution temporelle des événements
- Intervalles inter-événements (test de Poisson)
- Matrice de transition
- Corrélations laggées
- Régression logistique (score de prédictibilité)
- Fenêtre glissante de probabilité

```bash
python predire_seuil.py --input resultats_ocr_chiffres.csv --seuil 1.2
python predire_seuil.py --input f.csv --seuil 1.2 --lags 5 --out rapport.png
```

---

## Noms de fichiers — convention

| Étape | Fichier produit |
|---|---|
| Capture | `captures/capture_YYYYMMDD_HHMMSS.png` |
| Zones | `zones_YYYYMMDD_HHMMSS.csv` |
| OCR brut | `resultats_ocr_YYYYMMDD_HHMMSS.csv` |
| Filtré | `resultats_ocr_YYYYMMDD_HHMMSS_chiffres.csv` |
| Dédupliqué | `resultats_ocr_YYYYMMDD_HHMMSS_chiffres_dedup.csv` |

---

## Dépendances

```bash
pip install mss opencv-python pytesseract easyocr matplotlib \
            scipy statsmodels ruptures scikit-learn
```

Tesseract doit être installé séparément :
- Linux : `sudo apt install tesseract-ocr tesseract-ocr-fra`
- Windows : [github.com/UB-Mannheim/tesseract](https://github.com/UB-Mannheim/tesseract/wiki)

---

## Interface graphique

```bash
python launcher.py
```

- 9 onglets (un par script)
- Champs de saisie avec boutons Parcourir
- Noms de fichiers de sortie suggérés automatiquement
- Console de sortie en temps réel
