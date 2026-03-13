"""
Détection de patterns dans les valeurs OCR
===========================================
Lit le CSV filtré (produit par filtrer_ocr.py) et, pour chaque zone (label),
effectue plusieurs tests statistiques pour déterminer si les valeurs sont
aléatoires ou si elles contiennent des patterns :

  - Autocorrélation (lag 1 à 5)        → tendance / oscillation
  - Test de stationnarité ADF           → dérive longue
  - Test de runs (Wald–Wolfowitz)       → monotonie / alternance
  - Variance glissante                  → stabilité locale
  - Régression linéaire                 → tendance globale (pente)

Usage :
    python analyser_patterns.py --input resultats_ocr_chiffres.csv
    python analyser_patterns.py --input resultats_ocr_chiffres.csv --graph patterns.png --alpha 0.05
"""

import argparse
import csv
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np


# ---------------------------------------------------------------------------
# Chargement
# ---------------------------------------------------------------------------

def charger_series(chemin: str) -> dict[str, list[float]]:
    chemin = Path(chemin)
    if not chemin.is_file():
        print(f"ERREUR : fichier introuvable : {chemin}")
        sys.exit(1)

    series: dict[str, list[float]] = defaultdict(list)
    with open(chemin, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            label = row.get("label") or f"zone_{row.get('zone_id', '?')}"
            try:
                series[label].append(float(row["texte_ocr"]))
            except (ValueError, KeyError):
                pass
    return dict(series)


# ---------------------------------------------------------------------------
# Tests statistiques
# ---------------------------------------------------------------------------

def autocorrelation(x: np.ndarray, lag: int) -> float:
    """Corrélation de Pearson entre x[t] et x[t-lag]."""
    if len(x) <= lag:
        return float("nan")
    return float(np.corrcoef(x[:-lag], x[lag:])[0, 1])


def test_runs(x: np.ndarray) -> tuple[float, float, bool]:
    """
    Test de Wald–Wolfowitz (runs test).
    Retourne (z_stat, p_value, pattern_détecté).
    H0 = aléatoire ; p < alpha → pattern.
    """
    from scipy.stats import norm
    median = np.median(x)
    signs = x > median          # True / False
    runs = 1 + np.sum(signs[:-1] != signs[1:])
    n1 = np.sum(signs)
    n2 = len(signs) - n1
    n = n1 + n2
    if n1 == 0 or n2 == 0:
        return 0.0, 1.0, False
    mu = (2 * n1 * n2) / n + 1
    sigma2 = (2 * n1 * n2 * (2 * n1 * n2 - n)) / (n ** 2 * (n - 1))
    if sigma2 <= 0:
        return 0.0, 1.0, False
    z = (runs - mu) / np.sqrt(sigma2)
    p = 2 * (1 - norm.cdf(abs(z)))
    return float(z), float(p), bool(p < 0.05)


def test_adf(x: np.ndarray) -> tuple[float, float, bool]:
    """
    Test ADF (Augmented Dickey-Fuller) via statsmodels.
    p < 0.05 → série stationnaire (pas de dérive).
    pattern = NON stationnaire (p >= 0.05).
    """
    try:
        from statsmodels.tsa.stattools import adfuller
        stat, p, *_ = adfuller(x, autolag="AIC")
        return float(stat), float(p), bool(p >= 0.05)   # True = dérive détectée
    except Exception:
        return float("nan"), float("nan"), False


def regression_lineaire(x: np.ndarray) -> tuple[float, float, bool]:
    """
    Régression linéaire simple.
    Retourne (pente, p_value, tendance_significative).
    """
    from scipy.stats import linregress
    t = np.arange(len(x), dtype=float)
    slope, intercept, r, p, se = linregress(t, x)
    return float(slope), float(p), bool(p < 0.05)


def variance_glissante(x: np.ndarray, fenetre: int = 5) -> float:
    """Écart-type moyen des fenêtres glissantes → stabilité locale."""
    if len(x) < fenetre:
        return float(np.std(x))
    stds = [np.std(x[i:i+fenetre]) for i in range(len(x) - fenetre + 1)]
    return float(np.mean(stds))


# ---------------------------------------------------------------------------
# Analyse complète d'une série
# ---------------------------------------------------------------------------

def analyser_serie(label: str, valeurs: list[float], alpha: float) -> dict:
    x = np.array(valeurs)
    result = {
        "label":  label,
        "n":      len(x),
        "mean":   float(np.mean(x)),
        "std":    float(np.std(x)),
        "min":    float(np.min(x)),
        "max":    float(np.max(x)),
    }

    # Autocorrélations lag 1-3
    for lag in (1, 2, 3):
        result[f"autocorr_lag{lag}"] = autocorrelation(x, lag)

    # Tests formels (besoin de scipy / statsmodels)
    try:
        result["runs_z"], result["runs_p"], result["runs_pattern"] = test_runs(x)
    except ImportError:
        result["runs_z"] = result["runs_p"] = float("nan")
        result["runs_pattern"] = False

    try:
        result["adf_stat"], result["adf_p"], result["adf_derive"] = test_adf(x)
    except ImportError:
        result["adf_stat"] = result["adf_p"] = float("nan")
        result["adf_derive"] = False

    try:
        result["pente"], result["trend_p"], result["trend"] = regression_lineaire(x)
    except ImportError:
        result["pente"] = result["trend_p"] = float("nan")
        result["trend"] = False

    result["var_glissante"] = variance_glissante(x)

    # Verdict global
    patterns = []
    if abs(result.get("autocorr_lag1", 0) or 0) > 0.4:
        patterns.append("autocorrélation forte")
    if result.get("runs_pattern"):
        patterns.append("runs non-aléatoires")
    if result.get("adf_derive"):
        patterns.append("dérive/tendance (non-stationnaire)")
    if result.get("trend"):
        patterns.append(f"tendance linéaire (pente={result['pente']:+.4f})")

    result["patterns_detectes"] = patterns
    result["verdict"] = "PATTERNS" if patterns else "ALEATOIRE"
    return result


# ---------------------------------------------------------------------------
# Rapport texte
# ---------------------------------------------------------------------------

def afficher_rapport(resultats: list[dict]):
    sep = "─" * 60
    for r in resultats:
        print(f"\n{sep}")
        print(f"Zone : {r['label']}   (n={r['n']})")
        print(f"  Moyenne={r['mean']:.3f}  Écart-type={r['std']:.3f}  "
              f"[{r['min']:.3f} – {r['max']:.3f}]")
        print(f"  Autocorrélation  lag1={r['autocorr_lag1']:.3f}  "
              f"lag2={r['autocorr_lag2']:.3f}  lag3={r['autocorr_lag3']:.3f}")
        runs_p = r.get('runs_p', float('nan'))
        adf_p  = r.get('adf_p',  float('nan'))
        trend_p= r.get('trend_p',float('nan'))
        print(f"  Runs test        z={r.get('runs_z', float('nan')):.3f}  p={runs_p:.4f}")
        print(f"  ADF (dérive)     stat={r.get('adf_stat', float('nan')):.3f}  p={adf_p:.4f}")
        print(f"  Tendance linéaire pente={r.get('pente', 0):.5f}  p={trend_p:.4f}")
        print(f"  Variance glissante (fenêtre=5) : {r['var_glissante']:.4f}")
        if r["patterns_detectes"]:
            print(f"  >> Patterns : {', '.join(r['patterns_detectes'])}")
        print(f"  ==> VERDICT : {r['verdict']}")
    print(f"\n{sep}")


# ---------------------------------------------------------------------------
# Graphique
# ---------------------------------------------------------------------------

def tracer(resultats: list[dict], series: dict[str, list[float]], chemin_graph: str):
    try:
        import matplotlib.pyplot as plt
        from matplotlib.gridspec import GridSpec
    except ImportError:
        print("matplotlib non disponible, graphique ignoré.")
        return

    n = len(resultats)
    fig = plt.figure(figsize=(14, 4 * n))
    gs  = GridSpec(n, 2, figure=fig, hspace=0.5, wspace=0.35)

    for i, r in enumerate(resultats):
        x = np.array(series[r["label"]])
        t = np.arange(len(x))

        # --- Courbe temporelle ---
        ax1 = fig.add_subplot(gs[i, 0])
        ax1.plot(t, x, marker="o", markersize=3, lw=1, label=r["label"])
        # tendance linéaire
        if r.get("trend") and not np.isnan(r.get("pente", float("nan"))):
            trend_line = r["pente"] * t + (np.mean(x) - r["pente"] * np.mean(t))
            ax1.plot(t, trend_line, "--", color="red", lw=1, label="tendance")
        ax1.set_title(f"{r['label']} — {r['verdict']}", fontsize=10)
        ax1.set_xlabel("Index")
        ax1.set_ylabel("Valeur")
        ax1.legend(fontsize=8)
        ax1.grid(True, alpha=0.3)

        # --- Autocorrélogramme ---
        ax2 = fig.add_subplot(gs[i, 1])
        lags  = [1, 2, 3, 4, 5]
        acorr = [autocorrelation(x, lag) for lag in lags]
        bars  = ax2.bar(lags, acorr, color=["red" if abs(a) > 0.4 else "steelblue"
                                             for a in acorr])
        ax2.axhline(0.4,  color="red",   lw=0.8, linestyle="--", label="seuil ±0.4")
        ax2.axhline(-0.4, color="red",   lw=0.8, linestyle="--")
        ax2.axhline(0,    color="black", lw=0.5)
        ax2.set_xlim(0.5, 5.5)
        ax2.set_ylim(-1, 1)
        ax2.set_title(f"Autocorrélogramme — {r['label']}", fontsize=10)
        ax2.set_xlabel("Lag")
        ax2.set_ylabel("r")
        ax2.legend(fontsize=8)
        ax2.grid(True, alpha=0.3)

    plt.suptitle("Analyse des patterns dans les valeurs OCR", fontsize=13, y=1.01)
    plt.savefig(chemin_graph, dpi=150, bbox_inches="tight")
    print(f"Graphique sauvegardé → {chemin_graph}")
    plt.show()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Détecte les patterns statistiques dans les valeurs OCR."
    )
    parser.add_argument("--input",  required=True, help="CSV filtré (_chiffres.csv)")
    parser.add_argument("--graph",  default=None,  help="Fichier graphique de sortie")
    parser.add_argument("--alpha",  type=float, default=0.05,
                        help="Seuil de significativité (défaut : 0.05)")
    args = parser.parse_args()

    chemin_graph = args.graph or Path(args.input).stem + "_patterns.png"

    series    = charger_series(args.input)
    resultats = [analyser_serie(label, vals, args.alpha)
                 for label, vals in series.items()]

    afficher_rapport(resultats)
    tracer(resultats, series, chemin_graph)


if __name__ == "__main__":
    main()
