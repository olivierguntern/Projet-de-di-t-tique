"""
Suppression des doublons consécutifs dans un CSV post-OCR filtré
================================================================
Lit le CSV produit par filtrer_ocr.py et supprime les lignes dont la valeur
'texte_ocr' est identique à la ligne précédente, **par zone (label)**.

Un doublon consécutif = même chiffre qui apparaît plusieurs fois de suite
dans la même zone. Ex : 1.2, 1.2, 1.2, 1.5 → 1.2, 1.5

Usage :
    python dedupliquer_ocr.py --input resultats_ocr_chiffres.csv
    python dedupliquer_ocr.py --input resultats_ocr_chiffres.csv --out sans_doublons.csv
    python dedupliquer_ocr.py --input resultats_ocr_chiffres.csv --global
"""

import argparse
import csv
import sys
from pathlib import Path


def dedupliquer(chemin_in: str, chemin_out: str, mode_global: bool) -> tuple[int, int]:
    """
    Supprime les doublons consécutifs.

    mode_global=False  : compare au précédent de la MÊME zone (label)
    mode_global=True   : compare au précédent toutes zones confondues
    """
    chemin_in = Path(chemin_in)
    if not chemin_in.is_file():
        print(f"ERREUR : fichier introuvable : {chemin_in}")
        sys.exit(1)

    lignes_entree = []
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

    if mode_global:
        # Comparaison sur l'ensemble des lignes, sans tenir compte du label
        precedente_valeur = None
        for row in lignes_entree:
            valeur = row["texte_ocr"].strip()
            if valeur != precedente_valeur:
                lignes_gardees.append(row)
                precedente_valeur = valeur
    else:
        # Comparaison par zone (label) — comportement par défaut
        precedente_par_zone: dict[str, str] = {}
        for row in lignes_entree:
            label = row.get("label") or f"zone_{row.get('zone_id', '?')}"
            valeur = row["texte_ocr"].strip()
            if valeur != precedente_par_zone.get(label):
                lignes_gardees.append(row)
                precedente_par_zone[label] = valeur

    gardees = len(lignes_gardees)
    supprimes = total - gardees

    with open(chemin_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(lignes_gardees)

    return total, gardees, supprimes


def main():
    parser = argparse.ArgumentParser(
        description="Supprime les doublons consécutifs d'un CSV post-OCR filtré."
    )
    parser.add_argument("--input",  required=True,
                        help="CSV filtré (produit par filtrer_ocr.py)")
    parser.add_argument("--out",    default=None,
                        help="CSV de sortie (défaut : <input>_dedup.csv)")
    parser.add_argument("--global", dest="mode_global", action="store_true",
                        help="Comparer toutes zones confondues (défaut : par zone)")
    args = parser.parse_args()

    chemin_out = args.out or (Path(args.input).stem + "_dedup.csv")

    mode = "global" if args.mode_global else "par zone"
    print(f"Mode : suppression des doublons consécutifs {mode}")
    print(f"Entrée  : {args.input}")
    print(f"Sortie  : {chemin_out}")

    total, gardees, supprimes = dedupliquer(args.input, chemin_out, args.mode_global)

    print(f"\nRésultat :")
    print(f"  Lignes lues     : {total}")
    print(f"  Doublons retirés: {supprimes}  ({supprimes/total*100:.1f}%)")
    print(f"  Lignes gardées  : {gardees}  ({gardees/total*100:.1f}%)")
    print(f"\n✓ CSV écrit → {chemin_out}")


if __name__ == "__main__":
    main()
