"""
Prévisibilité des valeurs sous un seuil
========================================
Répond à la question : les valeurs < SEUIL arrivent-elles aléatoirement
ou peut-on les prévoir à partir des mesures précédentes ?

Analyses effectuées par zone :
  1. Taux et distribution temporelle  → les événements sont-ils groupés ?
  2. Intervalles inter-événements      → Poisson (aléatoire) ou non ?
  3. Matrice de transition             → après un événement, que suit-il ?
  4. Corrélations laggées              → les valeurs précédentes prédisent-elles ?
  5. Régression logistique             → score de prédictibilité formel
  6. Fenêtre glissante de probabilité  → y a-t-il des phases à risque élevé ?

Usage :
    python predire_seuil.py --input resultats_ocr_chiffres.csv --seuil 1.2
    python predire_seuil.py --input f.csv --seuil 1.2 --lags 5 --out rapport.png
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
# 1. Distribution temporelle
# ─────────────────────────────────────────────

def distribution_temporelle(evenements: np.ndarray, n: int) -> dict:
    """
    evenements : indices où x < seuil.
    Mesure si les événements sont groupés (burstiness) ou réguliers.
    """
    taux = len(evenements) / n if n > 0 else 0
    if len(evenements) < 2:
        return {"taux": taux, "burstiness": None, "groupement": "indéterminé"}

    intervalles = np.diff(evenements).astype(float)
    mu  = intervalles.mean()
    std = intervalles.std()
    # Burstiness B ∈ [-1, 1] : 0=Poisson, >0=groupé, <0=régulier
    B = (std - mu) / (std + mu) if (std + mu) > 0 else 0
    if B > 0.2:
        groupement = "GROUPÉ (bursts)"
    elif B < -0.2:
        groupement = "RÉGULIER (trop ordonné)"
    else:
        groupement = "POISSON (aléatoire)"
    return {
        "taux": round(taux, 4),
        "n_evenements": len(evenements),
        "intervalle_moyen": round(float(mu), 2),
        "intervalle_std":   round(float(std), 2),
        "burstiness": round(float(B), 4),
        "groupement": groupement,
    }


# ─────────────────────────────────────────────
# 2. Test de Kolmogorov-Smirnov sur les intervalles
# ─────────────────────────────────────────────

def test_poisson(evenements: np.ndarray) -> dict:
    """
    Compare la distribution des intervalles à une loi exponentielle
    (attendue si les événements sont un processus de Poisson = aléatoire).
    p > 0.05 → compatible avec Poisson (aléatoire).
    """
    if len(evenements) < 4:
        return {"ks_stat": None, "ks_p": None, "verdict": "indéterminé"}
    try:
        from scipy.stats import kstest, expon
        intervalles = np.diff(evenements).astype(float)
        if intervalles.mean() == 0:
            return {"ks_stat": None, "ks_p": None, "verdict": "indéterminé"}
        stat, p = kstest(intervalles, "expon",
                         args=(0, intervalles.mean()))
        verdict = "aléatoire (Poisson)" if p > 0.05 else "NON aléatoire"
        return {"ks_stat": round(float(stat), 4),
                "ks_p":    round(float(p), 5),
                "verdict": verdict}
    except ImportError:
        return {"ks_stat": None, "ks_p": None, "verdict": "scipy absent"}


# ─────────────────────────────────────────────
# 3. Matrice de transition (binaire)
# ─────────────────────────────────────────────

def matrice_transition(y: np.ndarray) -> np.ndarray:
    """
    y : série binaire (1 = événement, 0 = normal).
    Retourne matrice 2×2 des probabilités de transition.
    mat[i, j] = P(y_t+1=j | y_t=i)
    """
    mat = np.zeros((2, 2))
    for t in range(len(y) - 1):
        mat[y[t], y[t+1]] += 1
    row_sums = mat.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1
    return mat / row_sums


# ─────────────────────────────────────────────
# 4. Corrélations laggées (point-biserial)
# ─────────────────────────────────────────────

def correlations_laggees(x: np.ndarray, y: np.ndarray, n_lags: int) -> list[dict]:
    """
    Corrélation entre x[t-lag] et y[t] (événement).
    Mesure si une valeur élevée/basse à t-lag prédit l'événement à t.
    """
    try:
        from scipy.stats import pointbiserialr
    except ImportError:
        return []
    resultats = []
    for lag in range(1, n_lags + 1):
        if lag >= len(x):
            break
        xi = x[:-lag]
        yi = y[lag:]
        if len(xi) < 4:
            break
        r, p = pointbiserialr(yi, xi)
        resultats.append({
            "lag": lag,
            "r":   round(float(r), 4),
            "p":   round(float(p), 5),
            "significatif": bool(p < 0.05),
        })
    return resultats


# ─────────────────────────────────────────────
# 5. Régression logistique
# ─────────────────────────────────────────────

def regression_logistique(x: np.ndarray, y: np.ndarray, n_lags: int) -> dict:
    """
    Prédit y[t] à partir de x[t-1], …, x[t-n_lags].
    Retourne l'AUC-ROC et les coefficients.
    """
    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.metrics import roc_auc_score
        from sklearn.preprocessing import StandardScaler
    except ImportError:
        return {"erreur": "sklearn absent  →  pip install scikit-learn"}

    n = len(x)
    if n <= n_lags + 5:
        return {"erreur": "série trop courte pour la régression"}

    # Construire la matrice de features : [x(t-1), x(t-2), ..., x(t-n_lags)]
    X_feat = np.column_stack([x[n_lags - lag: n - lag] for lag in range(1, n_lags + 1)])
    Y_tgt  = y[n_lags:]

    if Y_tgt.sum() < 3 or (len(Y_tgt) - Y_tgt.sum()) < 3:
        return {"erreur": "trop peu d'événements pour entraîner le modèle"}

    X_feat = StandardScaler().fit_transform(X_feat)
    clf = LogisticRegression(max_iter=500, class_weight="balanced")
    clf.fit(X_feat, Y_tgt)
    proba = clf.predict_proba(X_feat)[:, 1]
    auc   = roc_auc_score(Y_tgt, proba)

    coefs = {f"lag{i+1}": round(float(c), 4) for i, c in enumerate(clf.coef_[0])}
    verdict = ("PRÉVISIBLE (AUC>{:.2f})".format(auc) if auc > 0.65
               else "difficilement prévisible" if auc > 0.55
               else "aléatoire (AUC≈0.5)")
    return {
        "auc":     round(float(auc), 4),
        "coefs":   coefs,
        "verdict": verdict,
        "proba":   proba,
    }


# ─────────────────────────────────────────────
# 6. Probabilité glissante
# ─────────────────────────────────────────────

def proba_glissante(y: np.ndarray, fenetre: int = 50) -> np.ndarray:
    """Taux d'événements dans une fenêtre glissante."""
    if len(y) < fenetre:
        return np.full(len(y), y.mean())
    return np.array([y[max(0, i-fenetre):i].mean() for i in range(1, len(y)+1)])


# ─────────────────────────────────────────────
# Analyse complète
# ─────────────────────────────────────────────

def analyser(label: str, x: np.ndarray, seuil: float, n_lags: int) -> dict:
    y = (x < seuil).astype(int)
    evenements = np.where(y == 1)[0]

    dist   = distribution_temporelle(evenements, len(x))
    ks     = test_poisson(evenements)
    trans  = matrice_transition(y)
    lags   = correlations_laggees(x, y, n_lags)
    logit  = regression_logistique(x, y, n_lags)
    prob_g = proba_glissante(y)

    return {
        "label":    label,
        "n":        len(x),
        "seuil":    seuil,
        "y":        y,
        "x":        x,
        "evenements": evenements,
        "distribution": dist,
        "test_poisson": ks,
        "transition":   trans,
        "lags":         lags,
        "logit":        logit,
        "proba_glissante": prob_g,
    }


# ─────────────────────────────────────────────
# Rapport texte
# ─────────────────────────────────────────────

def afficher_rapport(resultats: list[dict]):
    sep = "═" * 65
    for r in resultats:
        d  = r["distribution"]
        ks = r["test_poisson"]
        lg = r["logit"]
        t  = r["transition"]

        print(f"\n{sep}")
        print(f"  ZONE : {r['label']}   (n={r['n']}, seuil={r['seuil']})")
        print(sep)
        print(f"  Événements (< {r['seuil']}) : {d['n_evenements']} "
              f"({d['taux']*100:.1f}% des mesures)")
        print()

        # Groupement
        print(f"  ① Distribution temporelle")
        print(f"     Intervalle moyen entre événements : {d.get('intervalle_moyen','?')} captures")
        print(f"     Burstiness B = {d.get('burstiness','?')}  →  {d['groupement']}")
        if ks["ks_p"] is not None:
            print(f"     Test Poisson (KS) : stat={ks['ks_stat']}  p={ks['ks_p']}  →  {ks['verdict']}")

        # Transition
        print(f"\n  ② Matrice de transition")
        print(f"     Après un NON-événement : {t[0,0]*100:.1f}% reste normal, "
              f"{t[0,1]*100:.1f}% → événement")
        print(f"     Après un événement     : {t[1,1]*100:.1f}% reste < seuil, "
              f"{t[1,0]*100:.1f}% → normal")
        persistance = t[1,1]
        if persistance > 0.5:
            print(f"     ↳ Les événements ont tendance à se PERSISTER ({persistance*100:.0f}%)")
        else:
            print(f"     ↳ Les événements sont souvent ISOLÉS ({(1-persistance)*100:.0f}% retour immédiat)")

        # Lags
        sig = [l for l in r["lags"] if l["significatif"]]
        print(f"\n  ③ Corrélations laggées (point-biserial)")
        if sig:
            for l in sig:
                sens = "valeur BASSE" if l["r"] < 0 else "valeur HAUTE"
                print(f"     lag {l['lag']:2d} : r={l['r']:+.3f}  p={l['p']:.4f}  "
                      f"→ {sens} à t-{l['lag']} prédit l'événement")
        else:
            print("     Aucun lag significatif détecté")

        # Régression logistique
        print(f"\n  ④ Régression logistique (prédiction formelle)")
        if "erreur" in lg:
            print(f"     {lg['erreur']}")
        else:
            print(f"     AUC-ROC = {lg['auc']}  →  {lg['verdict']}")
            best_lag = max(lg["coefs"].items(), key=lambda kv: abs(kv[1]))
            print(f"     Prédicteur le plus fort : {best_lag[0]} (coef={best_lag[1]:+.4f})")

        # Verdict global
        print(f"\n  ══ VERDICT ══════════════════════════════════════════")
        auc_ok  = isinstance(lg.get("auc"), float) and lg["auc"] > 0.65
        lag_ok  = len(sig) > 0
        bursty  = d.get("burstiness") is not None and d["burstiness"] > 0.2
        poisson = "aléatoire" in ks.get("verdict", "").lower()

        if auc_ok or lag_ok:
            print(f"  → LES ÉVÉNEMENTS SONT PRÉVISIBLES")
            if lag_ok:
                print(f"     Les valeurs à t-{sig[0]['lag']} annoncent l'événement")
            if auc_ok:
                print(f"     Modèle de prédiction : AUC={lg['auc']:.3f}")
        elif poisson and not bursty:
            print(f"  → LES ÉVÉNEMENTS SEMBLENT ALÉATOIRES")
            print(f"     Aucun prédicteur significatif trouvé")
        else:
            print(f"  → RÉSULTAT AMBIGU — plus de données ou d'outils nécessaires")
    print()


# ─────────────────────────────────────────────
# Graphiques
# ─────────────────────────────────────────────

def tracer(resultats: list[dict], chemin: str):
    try:
        import matplotlib.pyplot as plt
        import matplotlib.gridspec as mgrid
    except ImportError:
        print("matplotlib absent, graphique ignoré.")
        return

    n_zones = len(resultats)
    fig = plt.figure(figsize=(18, 5 * n_zones))
    outer = mgrid.GridSpec(n_zones, 1, hspace=0.7, figure=fig)

    for i, r in enumerate(resultats):
        inner = mgrid.GridSpecFromSubplotSpec(2, 3, subplot_spec=outer[i],
                                              wspace=0.4, hspace=0.5)
        x   = r["x"]
        y   = r["y"]
        ev  = r["evenements"]
        t   = np.arange(len(x))
        s   = r["seuil"]
        lbl = r["label"]

        # ── col 0 row 0 : série + événements marqués ──────────────
        ax = fig.add_subplot(inner[0, 0])
        ax.plot(t, x, lw=0.6, color="steelblue", alpha=0.7)
        ax.axhline(s, color="red", lw=1, linestyle="--", label=f"seuil {s}")
        ax.scatter(ev, x[ev], s=8, color="red", zorder=3, label="< seuil")
        ax.set_title(f"{lbl} — événements (rouge)", fontsize=9)
        ax.legend(fontsize=7); ax.grid(True, alpha=0.2)

        # ── col 1 row 0 : probabilité glissante ───────────────────
        ax2 = fig.add_subplot(inner[0, 1])
        pg = r["proba_glissante"]
        ax2.fill_between(t, pg, alpha=0.4, color="orange")
        ax2.plot(t, pg, lw=0.8, color="darkorange")
        ax2.axhline(y.mean(), color="gray", lw=0.8, linestyle="--",
                    label=f"moyenne {y.mean()*100:.1f}%")
        ax2.set_ylim(0, 1)
        ax2.set_title("Probabilité glissante\n(fenêtre=50)", fontsize=9)
        ax2.set_ylabel("P(< seuil)"); ax2.legend(fontsize=7); ax2.grid(True, alpha=0.2)

        # ── col 2 row 0 : distribution des intervalles ─────────────
        ax3 = fig.add_subplot(inner[0, 2])
        if len(ev) >= 2:
            intervalles = np.diff(ev)
            ax3.hist(intervalles, bins=min(30, len(intervalles)//2 + 1),
                     color="teal", edgecolor="white", alpha=0.8, density=True)
            # Courbe exponentielle théorique (Poisson)
            mu = intervalles.mean()
            xi = np.linspace(0, intervalles.max(), 200)
            ax3.plot(xi, (1/mu) * np.exp(-xi/mu), "r--", lw=1.5,
                     label="Poisson théorique")
            ax3.legend(fontsize=7)
        ax3.set_title("Intervalles entre événements\n(rouge=Poisson=aléatoire)", fontsize=9)
        ax3.set_xlabel("durée"); ax3.grid(True, alpha=0.2)

        # ── col 0 row 1 : corrélations laggées ────────────────────
        ax4 = fig.add_subplot(inner[1, 0])
        lags_data = r["lags"]
        if lags_data:
            lags_x = [l["lag"] for l in lags_data]
            lags_r = [l["r"]   for l in lags_data]
            colors = ["red" if l["significatif"] else "steelblue" for l in lags_data]
            ax4.bar(lags_x, lags_r, color=colors)
            ax4.axhline(0, color="black", lw=0.5)
            ax4.set_title("Corrélation laggée\n(rouge=significatif)", fontsize=9)
            ax4.set_xlabel("lag"); ax4.set_ylabel("r")
        else:
            ax4.text(0.5, 0.5, "scipy absent", ha="center",
                     transform=ax4.transAxes, color="gray")
        ax4.grid(True, alpha=0.2)

        # ── col 1 row 1 : matrice de transition ───────────────────
        ax5 = fig.add_subplot(inner[1, 1])
        trans = r["transition"]
        im = ax5.imshow(trans, vmin=0, vmax=1, cmap="Blues", aspect="auto")
        for ii in range(2):
            for jj in range(2):
                ax5.text(jj, ii, f"{trans[ii,jj]:.2f}", ha="center",
                         va="center", fontsize=10,
                         color="white" if trans[ii,jj] > 0.6 else "black")
        ax5.set_xticks([0,1]); ax5.set_xticklabels(["normal","< seuil"])
        ax5.set_yticks([0,1]); ax5.set_yticklabels(["normal","< seuil"])
        ax5.set_title("Transition t → t+1", fontsize=9)
        plt.colorbar(im, ax=ax5, fraction=0.04)

        # ── col 2 row 1 : proba prédite vs réelle (si logit) ──────
        ax6 = fig.add_subplot(inner[1, 2])
        lg = r["logit"]
        if "proba" in lg:
            n_lags_used = len(lg["coefs"])
            t_pred = t[n_lags_used:]
            ax6.plot(t_pred, lg["proba"], lw=0.8, color="purple", alpha=0.7,
                     label=f"P prédite (AUC={lg['auc']:.2f})")
            ax6.scatter(ev[ev >= n_lags_used],
                        np.ones(np.sum(ev >= n_lags_used)) * 0.95,
                        s=5, color="red", alpha=0.5, label="réel < seuil")
            ax6.axhline(0.5, color="gray", lw=0.5, linestyle="--")
            ax6.set_ylim(0, 1); ax6.legend(fontsize=7)
            ax6.set_title(f"Probabilité prédite\n{lg['verdict']}", fontsize=9)
        else:
            raison = lg.get("erreur", "sklearn absent")
            ax6.text(0.5, 0.5, raison, ha="center", va="center",
                     transform=ax6.transAxes, fontsize=8, color="gray",
                     wrap=True)
            ax6.set_title("Probabilité prédite", fontsize=9)
        ax6.grid(True, alpha=0.2)

    plt.suptitle(f"Prévisibilité des valeurs < seuil", fontsize=13, y=1.01)
    plt.savefig(chemin, dpi=150, bbox_inches="tight")
    print(f"Graphique sauvegardé → {chemin}")
    plt.show()


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Analyse si les valeurs < seuil sont aléatoires ou prévisibles."
    )
    parser.add_argument("--input",  required=True, help="CSV filtré (_chiffres.csv)")
    parser.add_argument("--seuil",  type=float, default=1.2, help="Seuil (défaut : 1.2)")
    parser.add_argument("--lags",   type=int,   default=10,  help="Nombre de lags à tester (défaut : 10)")
    parser.add_argument("--out",    default=None, help="Fichier graphique de sortie")
    args = parser.parse_args()

    chemin_out = args.out or Path(args.input).stem + f"_seuil{args.seuil}.png"
    series = charger_series(args.input)

    resultats = [analyser(label, x, args.seuil, args.lags)
                 for label, x in series.items()]

    afficher_rapport(resultats)
    tracer(resultats, chemin_out)


if __name__ == "__main__":
    main()
