"""
Filtre un CSV post-OCR — ne garde que les lignes avec des chiffres
==================================================================
Lit le CSV produit par ocr_zones.py et conserve uniquement les lignes
dont la colonne 'texte_ocr' contient au moins un chiffre (0-9).

Usage :
    python filtrer_ocr.py --input resultats_ocr.csv
    python filtrer_ocr.py --input resultats_ocr.csv --out filtre.csv
"""

import argparse
import csv
import re
import sys
from pathlib import Path


def extraire_chiffres(texte: str) -> str:
    return re.sub(r"\D", "", texte)


def filtrer(chemin_in: str, chemin_out: str):
    chemin_in = Path(chemin_in)
    if not chemin_in.is_file():
        print(f"ERREUR : fichier introuvable : {chemin_in}")
        sys.exit(1)

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
            if chiffres:
                row["texte_ocr"] = chiffres
                writer.writerow(row)
                gardees += 1

    print(f"{gardees}/{total} lignes conservées → {chemin_out}")


def main():
    parser = argparse.ArgumentParser(
        description="Filtre les lignes OCR contenant au moins un chiffre."
    )
    parser.add_argument("--input", required=True, help="CSV post-OCR (ocr_zones.py)")
    parser.add_argument("--out", default=None, help="CSV filtré de sortie")
    args = parser.parse_args()

    chemin_out = args.out or Path(args.input).stem + "_chiffres.csv"
    filtrer(args.input, chemin_out)


if __name__ == "__main__":
    main()
