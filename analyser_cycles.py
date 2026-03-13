"""
Analyse des cycles de la zone 'temps'
======================================
Détecte les resets (retour à < seuil_reset après avoir dépassé seuil_haut)
et calcule la durée de chaque cycle pour estimer quand la prochaine
phase basse (<1.1 / <1.2) va survenir.

Usage :
    python analyser_cycles.py --input propre.csv
    python analyser_cycles.py --input propre.csv --seuil-reset 1.2 --seuil-haut 2.0
    python analyser_cycles.py --input propre.csv --detail
"""

import argparse
import csv
import statistics
from datetime import datetime
from pathlib import Path


def parse_timestamp(nom_image: str) -> datetime:
    base = nom_image.replace("capture_", "").replace(".png", "")
    return datetime.strptime(base, "%Y%m%d_%H%M%S")


def analyser(chemin: str, seuil_reset: float, seuil_haut: float, detail: bool):
    chemin = Path(chemin)
    if not chemin.is_file():
        print(f"ERREUR : fichier introuvable : {chemin}")
        return

    with open(chemin, newline="", encoding="utf-8") as f:
        lignes = list(csv.DictReader(f))

    # --- Extraction des cycles ---
    cycles = []
    debut_cycle = None
    ts_debut = None
    pic_atteint = False
    val_max = 0.0

    for row in lignes:
        try:
            val = float(row["texte_ocr"])
        except ValueError:
            continue
        try:
            ts = parse_timestamp(row["image"])
        except ValueError:
            continue

        if val <= seuil_reset:
            if ts_debut is not None and pic_atteint:
                duree = (ts - ts_debut).total_seconds()
                cycles.append({
                    "debut":   ts_debut,
                    "fin":     ts,
                    "duree_s": duree,
                    "pic":     val_max,
                })
            ts_debut = ts
            debut_cycle = val
            pic_atteint = False
            val_max = val
        else:
            if val > val_max:
                val_max = val
            if val >= seuil_haut:
                pic_atteint = True

    if not cycles:
        print("Aucun cycle détecté. Essayez d'abaisser --seuil-haut.")
        return

    durees = [c["duree_s"] for c in cycles]
    pics   = [c["pic"]     for c in cycles]

    moy_duree = statistics.mean(durees)
    std_duree = statistics.stdev(durees) if len(durees) > 1 else 0.0
    moy_pic   = statistics.mean(pics)

    # --- Affichage ---
    print("=" * 60)
    print(f"  Analyse des cycles  (seuil reset ≤ {seuil_reset}  |  pic ≥ {seuil_haut})")
    print("=" * 60)
    print(f"  Cycles détectés     : {len(cycles)}")
    print()
    print("  Durée des cycles (secondes) :")
    print(f"    minimum     : {min(durees):.0f} s")
    print(f"    maximum     : {max(durees):.0f} s")
    print(f"    moyenne     : {moy_duree:.1f} s")
    print(f"    écart-type  : {std_duree:.1f} s  ({std_duree/moy_duree*100:.0f}% de la moyenne)")
    print()
    print("  Pic max avant reset :")
    print(f"    minimum     : {min(pics):.2f}")
    print(f"    maximum     : {max(pics):.2f}")
    print(f"    moyenne     : {moy_pic:.2f}")
    print()

    # Interprétation
    cv = std_duree / moy_duree  # coefficient de variation
    print("  Prédictibilité :")
    if cv < 0.2:
        qualite = "BONNE  — cycles réguliers"
    elif cv < 0.4:
        qualite = "MOYENNE — cycles assez réguliers"
    else:
        qualite = "FAIBLE  — cycles irréguliers"
    print(f"    Coefficient de variation : {cv:.2f}  → {qualite}")
    print()
    print(f"  Estimation prochaine phase basse :")
    print(f"    Dans environ {moy_duree:.0f}s après le dernier reset")
    print(f"    Fourchette probable : [{moy_duree - std_duree:.0f}s  –  {moy_duree + std_duree:.0f}s]")
    print()

    # Répartition des durées par tranches
    tranches = [(0,15),(15,30),(30,45),(45,60),(60,90),(90,120),(120,9999)]
    print("  Répartition des durées :")
    for a, b in tranches:
        n = sum(1 for d in durees if a <= d < b)
        if n == 0:
            continue
        label = f"{a}-{b}s" if b < 9999 else f">{a}s"
        barre = "█" * n
        print(f"    {label:10s} : {barre} ({n})")
    print()

    if detail:
        print("  Détail de chaque cycle :")
        print(f"  {'N°':>3}  {'Début':8}  {'Fin':8}  {'Durée':>7}  {'Pic':>7}")
        print("  " + "-" * 42)
        for i, c in enumerate(cycles, 1):
            print(f"  {i:3d}  "
                  f"{c['debut'].strftime('%H:%M:%S')}  "
                  f"{c['fin'].strftime('%H:%M:%S')}  "
                  f"{c['duree_s']:6.0f}s  "
                  f"{c['pic']:7.2f}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyse les cycles de reset dans un CSV post-OCR."
    )
    parser.add_argument("--input", required=True,
                        help="CSV filtré (ex: propre.csv)")
    parser.add_argument("--seuil-reset", type=float, default=1.2,
                        help="Valeur max pour détecter un reset (défaut: 1.2)")
    parser.add_argument("--seuil-haut", type=float, default=2.0,
                        help="Valeur min du pic avant reset (défaut: 2.0)")
    parser.add_argument("--detail", action="store_true",
                        help="Afficher le détail de chaque cycle")
    args = parser.parse_args()

    analyser(args.input, args.seuil_reset, args.seuil_haut, args.detail)


if __name__ == "__main__":
    main()
