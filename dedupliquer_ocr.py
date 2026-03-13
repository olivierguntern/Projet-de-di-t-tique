"""
Suppression des doublons consécutifs dans un CSV post-OCR filtré
================================================================
Lit le CSV produit par filtrer_ocr.py et supprime les lignes dont la valeur
'texte_ocr' est identique à la ligne précédente.

Ex : 1.2, 1.2, 1.2, 1.5, 1.5, 1.8  →  1.2, 1.5, 1.8

Usage :
    python dedupliquer_ocr.py --input resultats_ocr_chiffres.csv
    python dedupliquer_ocr.py --input resultats_ocr_chiffres.csv --out sans_doublons.csv
"""

import argparse
import csv
import sys
from pathlib import Path


def dedupliquer(chemin_in: str, chemin_out: str) -> tuple[int, int, int]:
    chemin_in = Path(chemin_in)
    if not chemin_in.is_file():
        print(f"ERREUR : fichier introuvable : {chemin_in}")
        sys.exit(1)

    with open(chemin_in, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            print("ERREUR : CSV vide ou sans en-tête.")
            sys.exit(1)
        if "texte_ocr" not in reader.fieldnames:
            print("ERREUR : colonne 'texte_ocr' introuvable.")
            sys.exit(1)
        fieldnames = reader.fieldnames
        lignes_entree = list(reader)

    total = len(lignes_entree)
    lignes_gardees = []
    precedente = None

    for row in lignes_entree:
        valeur = row["texte_ocr"].strip()
        if valeur != precedente:
            lignes_gardees.append(row)
            precedente = valeur

    gardees = len(lignes_gardees)

    with open(chemin_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(lignes_gardees)

    return total, gardees, total - gardees


def main():
    parser = argparse.ArgumentParser(
        description="Supprime les doublons consécutifs d'un CSV post-OCR filtré."
    )
    parser.add_argument("--input", required=True,
                        help="CSV filtré (produit par filtrer_ocr.py)")
    parser.add_argument("--out", default=None,
                        help="CSV de sortie (défaut : <input>_dedup.csv)")
    args = parser.parse_args()

    chemin_out = args.out or (Path(args.input).stem + "_dedup.csv")

    print(f"Entrée : {args.input}")
    print(f"Sortie : {chemin_out}")

    total, gardees, supprimes = dedupliquer(args.input, chemin_out)

    print(f"\nRésultat :")
    print(f"  Lignes lues      : {total}")
    print(f"  Doublons retirés : {supprimes}  ({supprimes/total*100:.1f}%)")
    print(f"  Lignes gardées   : {gardees}  ({gardees/total*100:.1f}%)")
    print(f"\n✓ CSV écrit → {chemin_out}")


if __name__ == "__main__":
    main()
