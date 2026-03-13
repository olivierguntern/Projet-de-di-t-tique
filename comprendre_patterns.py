"""
Compréhension approfondie des patterns OCR
==========================================
Étend analyser_patterns.py avec des analyses plus fines :

  1. FFT / Spectre de puissance      → période dominante (cycles)
  2. Décomposition STL                → tendance + saisonnalité + résidu
  3. Détection de points de rupture   → où la distribution change (PELT)
  4. Clustering temporel (k-means)    → régimes / phases distinctes
  5. Corrélation croisée inter-zones  → dépendance entre zones

Usage :
    python comprendre_patterns.py --input resultats_ocr_chiffres.csv
    python comprendre_patterns.py --input f.csv --saison 7 --clusters 3 --out rapport.png
"""

import argparse
import csv
import sys
import warnings
from collections import defaultdict
from pathlib import Path

import numpy as np

warnings.filterwarnings("ignore")


# ─────────────────────────────────────────────
# Chargement
# ─────────────────────────────────────────────

def charger_series(chemin: str) -> dict[str, np.ndarray]:
    p = Path(chemin)
    if not p.is_file():
        sys.exit(f"ERREUR : fichier introuvable : {chemin}")
    series: dict[str, list] = defaultdict(list)
    with open(p, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            label = row.get("label") or f"zone_{row.get('zone_id','?')}"
            try:
                series[label].append(float(row["texte_ocr"]))
            except (ValueError, KeyError):
                pass
    return {k: np.array(v) for k, v in series.items()}


# ─────────────────────────────────────────────
# 1. FFT – période dominante
# ─────────────────────────────────────────────

def analyser_fft(x: np.ndarray) -> dict:
    n = len(x)
    if n < 4:
        return {"periode_dominante": None, "puissance_ratio": 0.0}
    freqs = np.fft.rfftfreq(n)
    power = np.abs(np.fft.rfft(x - x.mean())) ** 2
    # Ignorer fréquence 0 (DC)
    idx = np.argmax(power[1:]) + 1
    periode = 1.0 / freqs[idx] if freqs[idx] > 0 else None
    ratio   = float(power[idx] / (power.sum() + 1e-10))
    return {"periode_dominante": round(periode, 1) if periode else None,
            "puissance_ratio": round(ratio, 4)}


# ─────────────────────────────────────────────
# 2. Décomposition STL
# ─────────────────────────────────────────────

def decomposer_stl(x: np.ndarray, periode: int) -> dict | None:
    try:
        from statsmodels.tsa.seasonal import STL
        if len(x) < 2 * periode:
            return None
        res = STL(x, period=periode, robust=True).fit()
        force_saison = 1 - np.var(res.resid) / (np.var(res.seasonal + res.resid) + 1e-10)
        force_trend  = 1 - np.var(res.resid) / (np.var(res.trend  + res.resid) + 1e-10)
        return {
            "trend":    res.trend,
            "seasonal": res.seasonal,
            "resid":    res.resid,
            "force_saisonnalite": round(float(force_saison), 4),
            "force_tendance":     round(float(force_trend),  4),
        }
    except Exception:
        return None


# ─────────────────────────────────────────────
# 3. Détection de points de rupture
# ─────────────────────────────────────────────

def detecter_ruptures(x: np.ndarray, n_max: int = 5) -> list[int]:
    """
    Algorithme PELT via ruptures ; fallback maison si absent.
    Retourne les indices des points de rupture.
    """
    try:
        import ruptures as rpt
        model = rpt.Pelt(model="rbf").fit(x)
        breaks = model.predict(pen=np.log(len(x)) * x.std())
        return [b for b in breaks if b < len(x)]
    except ImportError:
        pass

    # Fallback : sliding window – cherche les sauts de moyenne les plus nets
    n = len(x)
    if n < 6:
        return []
    scores = []
    for i in range(2, n - 2):
        m1, m2 = x[:i].mean(), x[i:].mean()
        scores.append((abs(m2 - m1), i))
    scores.sort(reverse=True)
    breaks = sorted({i for _, i in scores[:n_max]})
    # Fusionner les ruptures trop proches (< 3 points)
    merged = []
    for b in breaks:
        if not merged or b - merged[-1] >= 3:
            merged.append(b)
    return merged[:n_max]


# ─────────────────────────────────────────────
# 4. Clustering temporel
# ─────────────────────────────────────────────

def clustering_temporel(x: np.ndarray, k: int, fenetre: int = 3) -> dict:
    """
    Découpe x en fenêtres glissantes de taille `fenetre`,
    applique k-means, retourne les labels de cluster et les centres.
    """
    try:
        from sklearn.cluster import KMeans
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return {"labels": None, "centres": None, "inertie": None}

    if len(x) < fenetre + 1:
        return {"labels": None, "centres": None, "inertie": None}

    # Construire des vecteurs de features par fenêtre
    features = []
    for i in range(len(x) - fenetre + 1):
        w = x[i:i+fenetre]
        features.append([w.mean(), w.std(), w[-1] - w[0]])   # moyenne, écart-type, delta

    F = StandardScaler().fit_transform(np.array(features))
    km = KMeans(n_clusters=min(k, len(F)), random_state=42, n_init=10).fit(F)

    # Étendre les labels sur toute la série (premier point de chaque fenêtre)
    labels_full = np.full(len(x), -1, dtype=int)
    for i, lbl in enumerate(km.labels_):
        labels_full[i] = lbl
    # Remplir les trous en fin de série
    labels_full[labels_full == -1] = labels_full[labels_full != -1][-1]

    return {
        "labels":   km.labels_,
        "labels_full": labels_full,
        "centres":  km.cluster_centers_,
        "inertie":  round(float(km.inertia_), 4),
        "n_clusters": int(km.n_clusters),
    }


# ─────────────────────────────────────────────
# 5. Corrélation croisée inter-zones
# ─────────────────────────────────────────────

def correlations_croisees(series: dict[str, np.ndarray]) -> list[tuple]:
    """
    Calcule la corrélation de Pearson entre chaque paire de zones
    (sur la longueur minimale commune).
    Retourne liste de (zone_a, zone_b, r, lag_optimal).
    """
    from scipy.stats import pearsonr
    labels = list(series.keys())
    resultats = []
    for i in range(len(labels)):
        for j in range(i + 1, len(labels)):
            a, b = series[labels[i]], series[labels[j]]
            n = min(len(a), len(b))
            if n < 4:
                continue
            r, p = pearsonr(a[:n], b[:n])
            # Corrélation croisée pour trouver le lag optimal
            cc = np.correlate(a[:n] - a[:n].mean(), b[:n] - b[:n].mean(), mode="full")
            lag_opt = int(cc.argmax()) - (n - 1)
            resultats.append((labels[i], labels[j], round(float(r), 4), lag_opt, round(float(p), 5)))
    return resultats


# ─────────────────────────────────────────────
# Rapport texte
# ─────────────────────────────────────────────

def afficher_rapport(serie_resultats: list[dict], croisees: list[tuple]):
    sep = "═" * 65
    for r in serie_resultats:
        print(f"\n{sep}")
        print(f"  ZONE : {r['label']}   (n={r['n']})")
        print(sep)

        # FFT
        fft = r["fft"]
        if fft["periode_dominante"]:
            print(f"  FFT  → période dominante : {fft['periode_dominante']} captures "
                  f"({fft['puissance_ratio']*100:.1f}% de la puissance totale)")
        else:
            print("  FFT  → aucune période détectable")

        # STL
        stl = r.get("stl")
        if stl:
            print(f"  STL  → force saisonnalité={stl['force_saisonnalite']:.3f}  "
                  f"force tendance={stl['force_tendance']:.3f}")
            if stl["force_saisonnalite"] > 0.4:
                print("         ↳ Composante saisonnière forte")
            if stl["force_tendance"] > 0.4:
                print("         ↳ Tendance structurelle forte")
        else:
            print("  STL  → série trop courte pour la décomposition")

        # Ruptures
        breaks = r["ruptures"]
        if breaks:
            print(f"  Ruptures → indices {breaks}  ({len(breaks)} changement(s) de régime)")
        else:
            print("  Ruptures → aucune rupture significative")

        # Clustering
        cl = r["clustering"]
        if cl["labels"] is not None:
            print(f"  Clustering → {cl['n_clusters']} régimes détectés  "
                  f"(inertie={cl['inertie']})")
        else:
            print("  Clustering → sklearn absent ou données insuffisantes")

    # Corrélations croisées
    if croisees:
        print(f"\n{sep}")
        print("  CORRÉLATIONS CROISÉES ENTRE ZONES")
        print(sep)
        for za, zb, r_val, lag, p in sorted(croisees, key=lambda x: -abs(x[2])):
            force = "FORTE" if abs(r_val) > 0.7 else ("MODÉRÉE" if abs(r_val) > 0.4 else "faible")
            print(f"  {za} ↔ {zb}  r={r_val:+.3f}  lag={lag:+d}  p={p:.4f}  [{force}]")
    print()


# ─────────────────────────────────────────────
# Graphiques
# ─────────────────────────────────────────────

def tracer(serie_resultats: list[dict], series: dict[str, np.ndarray],
           croisees: list[tuple], chemin: str):
    try:
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as mgrid
    except ImportError:
        print("matplotlib absent, graphique ignoré.")
        return

    n_zones   = len(serie_resultats)
    n_colonnes = 4   # courbe | spectre | ruptures+clusters | STL résidu
    fig = plt.figure(figsize=(18, 4.5 * n_zones + (3 if croisees else 0)))
    outer = mgrid.GridSpec(n_zones + (1 if croisees else 0), 1,
                           hspace=0.6, figure=fig)

    couleurs_clusters = ["#e41a1c", "#377eb8", "#4daf4a", "#984ea3", "#ff7f00"]

    for i, r in enumerate(serie_resultats):
        x = series[r["label"]]
        t = np.arange(len(x))
        inner = mgrid.GridSpecFromSubplotSpec(1, n_colonnes, subplot_spec=outer[i],
                                              wspace=0.4)

        # ── col 0 : courbe + ruptures ──────────────────────────────
        ax0 = fig.add_subplot(inner[0])
        ax0.plot(t, x, lw=1, color="steelblue")
        for b in r["ruptures"]:
            ax0.axvline(b, color="red", lw=1.2, linestyle="--", alpha=0.8)
        ax0.set_title(f"{r['label']}\n(ruptures)", fontsize=9)
        ax0.set_xlabel("index"); ax0.grid(True, alpha=0.25)

        # ── col 1 : spectre de puissance ──────────────────────────
        ax1 = fig.add_subplot(inner[1])
        if len(x) >= 4:
            freqs = np.fft.rfftfreq(len(x))
            power = np.abs(np.fft.rfft(x - x.mean())) ** 2
            ax1.plot(freqs[1:], power[1:], color="darkorange", lw=1)
            pd = r["fft"]["periode_dominante"]
            if pd:
                f_dom = 1 / pd
                ax1.axvline(f_dom, color="red", lw=1, linestyle="--",
                            label=f"T={pd}")
                ax1.legend(fontsize=7)
        ax1.set_title("Spectre FFT", fontsize=9)
        ax1.set_xlabel("Fréquence"); ax1.grid(True, alpha=0.25)

        # ── col 2 : clusters ──────────────────────────────────────
        ax2 = fig.add_subplot(inner[2])
        cl = r["clustering"]
        if cl["labels_full"] is not None:
            for c in range(cl["n_clusters"]):
                mask = cl["labels_full"] == c
                col  = couleurs_clusters[c % len(couleurs_clusters)]
                ax2.scatter(t[mask], x[mask], s=15, color=col,
                            label=f"régime {c}", zorder=3)
            ax2.plot(t, x, lw=0.5, color="gray", alpha=0.4)
            ax2.legend(fontsize=7, loc="upper right")
        else:
            ax2.plot(t, x, lw=1, color="steelblue")
            ax2.text(0.5, 0.5, "sklearn absent", ha="center",
                     transform=ax2.transAxes, fontsize=8, color="gray")
        ax2.set_title("Régimes (clusters)", fontsize=9)
        ax2.set_xlabel("index"); ax2.grid(True, alpha=0.25)

        # ── col 3 : STL résidu ou diff ────────────────────────────
        ax3 = fig.add_subplot(inner[3])
        stl = r.get("stl")
        if stl:
            ax3.fill_between(t, stl["resid"], alpha=0.6, color="purple")
            ax3.axhline(0, color="black", lw=0.5)
            ax3.set_title(f"Résidu STL\n(saison={stl['force_saisonnalite']:.2f})", fontsize=9)
        else:
            diff = np.diff(x)
            ax3.plot(diff, lw=1, color="teal")
            ax3.axhline(0, color="black", lw=0.5)
            ax3.set_title("Différences 1er ordre", fontsize=9)
        ax3.set_xlabel("index"); ax3.grid(True, alpha=0.25)

    # ── Heatmap corrélations croisées ─────────────────────────────
    if croisees:
        zones = list(series.keys())
        nz    = len(zones)
        mat   = np.eye(nz)
        idx   = {z: i for i, z in enumerate(zones)}
        for za, zb, rv, _, _ in croisees:
            mat[idx[za], idx[zb]] = rv
            mat[idx[zb], idx[za]] = rv
        ax_h = fig.add_subplot(outer[n_zones])
        im = ax_h.imshow(mat, vmin=-1, vmax=1, cmap="RdBu_r", aspect="auto")
        ax_h.set_xticks(range(nz)); ax_h.set_xticklabels(zones, rotation=30,
                                                           fontsize=8, ha="right")
        ax_h.set_yticks(range(nz)); ax_h.set_yticklabels(zones, fontsize=8)
        for ii in range(nz):
            for jj in range(nz):
                ax_h.text(jj, ii, f"{mat[ii,jj]:.2f}", ha="center",
                          va="center", fontsize=7,
                          color="white" if abs(mat[ii,jj]) > 0.6 else "black")
        plt.colorbar(im, ax=ax_h, fraction=0.03, pad=0.02)
        ax_h.set_title("Corrélations croisées inter-zones", fontsize=10)

    plt.suptitle("Compréhension approfondie des patterns OCR", fontsize=13, y=1.005)
    plt.savefig(chemin, dpi=150, bbox_inches="tight")
    print(f"Graphique sauvegardé → {chemin}")
    plt.show()


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Comprendre en profondeur les patterns dans les valeurs OCR."
    )
    parser.add_argument("--input",    required=True, help="CSV filtré (_chiffres.csv)")
    parser.add_argument("--saison",   type=int, default=7,
                        help="Période saisonnière pour STL (défaut : 7)")
    parser.add_argument("--clusters", type=int, default=3,
                        help="Nombre de clusters temporels (défaut : 3)")
    parser.add_argument("--out",      default=None, help="Fichier graphique de sortie")
    args = parser.parse_args()

    chemin_out = args.out or Path(args.input).stem + "_comprehension.png"
    series = charger_series(args.input)

    serie_resultats = []
    for label, x in series.items():
        r = {
            "label":     label,
            "n":         len(x),
            "fft":       analyser_fft(x),
            "stl":       decomposer_stl(x, args.saison),
            "ruptures":  detecter_ruptures(x),
            "clustering": clustering_temporel(x, args.clusters),
        }
        serie_resultats.append(r)

    croisees = correlations_croisees(series) if len(series) > 1 else []

    afficher_rapport(serie_resultats, croisees)
    tracer(serie_resultats, series, croisees, chemin_out)


if __name__ == "__main__":
    main()
