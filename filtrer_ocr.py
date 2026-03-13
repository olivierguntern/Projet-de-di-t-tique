"""
Filtre un CSV post-OCR — ne garde que les lignes avec des valeurs décimales
===========================================================================
Lit le CSV produit par ocr_zones.py, conserve uniquement les lignes dont
'texte_ocr' contient une valeur décimale valide (ex: 72.5), puis trace
une courbe par zone (label).

Usage :
    python filtrer_ocr.py --input resultats_ocr.csv
    python filtrer_ocr.py --input resultats_ocr.csv --out filtre.csv --graph courbe.png
"""

import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path


def extraire_chiffres(texte: str) -> str:
    return re.sub(r"[^\d.]", "", texte)


def filtrer(chemin_in: str, chemin_out: str) -> list[dict]:
    chemin_in = Path(chemin_in)
    if not chemin_in.is_file():
        print(f"ERREUR : fichier introuvable : {chemin_in}")
        sys.exit(1)

    lignes_gardees = []

    with open(chemin_in, newline="", encoding="utf-8") as f_in, \
         open(chemin_out, "w", newline="", encoding="utf-8") as f_out:

        reader = csv.DictReader(f_in)
        if "texte_ocr" not in (reader.fieldnames or []):
            print("ERREUR : colonne 'texte_ocr' introuvable dans le CSV.")
            sys.exit(1)

        writer = csv.DictWriter(f_out, fieldnames=reader.fieldnames)
        writer.writeheader()

        total = 0
        gardees = 0
        for row in reader:
            total += 1
            chiffres = extraire_chiffres(row["texte_ocr"])
            if re.search(r"\d\.\d", chiffres):
                row["texte_ocr"] = chiffres
                writer.writerow(row)
                lignes_gardees.append(row)
                gardees += 1

    print(f"{gardees}/{total} lignes conservées → {chemin_out}")
    return lignes_gardees


def tracer_courbe(lignes: list[dict], chemin_graph: str):
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("ERREUR : matplotlib non installé.\n  pip install matplotlib")
        sys.exit(1)

    # Regrouper les valeurs par label (zone)
    series = defaultdict(list)
    for row in lignes:
        label = row.get("label") or f"zone_{row.get('zone_id', '?')}"
        try:
            valeur = float(row["texte_ocr"])
            series[label].append((row["image"], valeur))
        except ValueError:
            pass

    if not series:
        print("Aucune donnée à tracer.")
        return

    fig, ax = plt.subplots(figsize=(12, 5))

    for label, points in series.items():
        images, valeurs = zip(*points)
        x = range(len(valeurs))
        ax.plot(x, valeurs, marker="o", markersize=3, label=label)

    ax.set_xlabel("Capture (index)")
    ax.set_ylabel("Valeur")
    ax.set_title("Évolution des valeurs OCR par zone")
    ax.legend()
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(chemin_graph, dpi=150)
    print(f"Graphique sauvegardé → {chemin_graph}")
    plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Filtre les lignes OCR avec valeurs décimales et trace une courbe."
    )
    parser.add_argument("--input",  required=True, help="CSV post-OCR (ocr_zones.py)")
    parser.add_argument("--out",    default=None,  help="CSV filtré de sortie")
    parser.add_argument("--graph",  default=None,  help="Fichier image du graphique (ex: courbe.png)")
    args = parser.parse_args()

    chemin_out   = args.out   or Path(args.input).stem + "_chiffres.csv"
    chemin_graph = args.graph or Path(args.input).stem + "_courbe.png"

    lignes = filtrer(args.input, chemin_out)
    tracer_courbe(lignes, chemin_graph)


if __name__ == "__main__":
    main()
