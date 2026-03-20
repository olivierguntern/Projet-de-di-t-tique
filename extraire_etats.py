"""
Extraction des états de zones (bord blanc=1, autre=0)
======================================================
Pour chaque image d'un dossier, analyse la couleur du bord de chaque zone
définie dans un CSV (selection_zones.py) et produit un CSV avec une ligne
par image : les états 0/1 des zones, triées de gauche à droite et de haut en bas.

Exemple de sortie CSV :
    image,timestamp,z1,z2,z3,z4,z5,z6,z7,z8
    capture_001.png,2026-03-13 15:24:12,1,1,0,1,0,1,0,0

Usage :
    python extraire_etats.py --images ./captures --zones zones.csv
    python extraire_etats.py --image capture.png  --zones zones.csv
    python extraire_etats.py --images ./captures  --zones zones.csv --out etats.csv

Arguments :
    --image      : Image unique
    --images     : Dossier d'images
    --zones      : CSV des zones (x, y, largeur, hauteur, label)   [obligatoire]
    --out        : CSV de sortie                [defaut : etats_DATETIME.csv]
    --epaisseur  : Epaisseur du bord a scanner  [defaut : 4]
    --seuil-blanc: Seuil min R,G,B pour blanc   [defaut : 160]
    --tolerance-rangee : Ecart max en Y pour grouper une rangee [defaut : 20]
    --debug      : Affiche l'image annotee (image unique seulement)
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import cv2
import numpy as np

EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}


# ─── Chargement zones ─────────────────────────────────────────────────────────

def charger_zones(chemin_csv: str) -> list[dict]:
    zones = []
    with open(chemin_csv, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            zones.append({
                "id":    int(row["id"]),
                "label": row.get("label", "").strip(),
                "x":     int(row["x"]),
                "y":     int(row["y"]),
                "w":     int(row["largeur"]),
                "h":     int(row["hauteur"]),
            })
    return zones


# ─── Tri des zones : rangées haut→bas, gauche→droite ─────────────────────────

def trier_zones(zones: list[dict], tolerance: int = 20) -> list[dict]:
    """
    Groupe les zones par rangée (y proches) puis trie chaque rangée par x.
    Retourne la liste à plat dans l'ordre haut→bas, gauche→droite.
    """
    if not zones:
        return zones

    tries = sorted(zones, key=lambda z: (z["y"], z["x"]))
    rangees = []
    rangee_courante = [tries[0]]

    for z in tries[1:]:
        # Même rangée si le centre Y est proche du centre Y de la rangée courante
        y_ref = sum(r["y"] + r["h"] // 2 for r in rangee_courante) / len(rangee_courante)
        y_z = z["y"] + z["h"] // 2
        if abs(y_z - y_ref) <= tolerance:
            rangee_courante.append(z)
        else:
            rangees.append(sorted(rangee_courante, key=lambda r: r["x"]))
            rangee_courante = [z]

    rangees.append(sorted(rangee_courante, key=lambda r: r["x"]))

    return [z for rangee in rangees for z in rangee]


# ─── Analyse bordure d'une zone ───────────────────────────────────────────────

def etat_bordure(img: np.ndarray, z: dict, epaisseur: int, seuil_blanc: int) -> int:
    """Retourne 1 si le bord de la zone est blanc, 0 sinon."""
    ih, iw = img.shape[:2]
    x1, y1 = max(z["x"], 0), max(z["y"], 0)
    x2, y2 = min(z["x"] + z["w"], iw), min(z["y"] + z["h"], ih)
    ep = min(epaisseur, (x2 - x1) // 2, (y2 - y1) // 2)
    if ep <= 0:
        return 0

    pixels = np.concatenate([
        img[y1:y1+ep,   x1:x2        ].reshape(-1, 3),   # haut
        img[y2-ep:y2,   x1:x2        ].reshape(-1, 3),   # bas
        img[y1+ep:y2-ep, x1:x1+ep   ].reshape(-1, 3),   # gauche
        img[y1+ep:y2-ep, x2-ep:x2   ].reshape(-1, 3),   # droite
    ]).astype(np.float32)

    b_moy = np.mean(pixels[:, 0])
    g_moy = np.mean(pixels[:, 1])
    r_moy = np.mean(pixels[:, 2])

    # Blanc = tous les canaux élevés
    return 1 if min(r_moy, g_moy, b_moy) >= seuil_blanc else 0


# ─── Traitement d'une image ───────────────────────────────────────────────────

def traiter_image(img_path: Path, zones_triees: list[dict],
                  epaisseur: int, seuil_blanc: int,
                  debug: bool = False) -> list[int] | None:
    img = cv2.imdecode(np.fromfile(str(img_path), dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        print(f"  [ERREUR] Impossible de lire : {img_path.name}")
        return None

    etats = [etat_bordure(img, z, epaisseur, seuil_blanc) for z in zones_triees]

    print(f"  {img_path.name}  ->  {','.join(map(str, etats))}")

    if debug:
        img_dbg = img.copy()
        for z, etat in zip(zones_triees, etats):
            col = (255, 255, 255) if etat == 1 else (0, 0, 180)
            cv2.rectangle(img_dbg, (z["x"], z["y"]), (z["x"]+z["w"], z["y"]+z["h"]), col, 2)
            cv2.putText(img_dbg, str(etat), (z["x"]+4, z["y"]+20),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
        cv2.imshow(img_path.name, img_dbg)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return etats


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Extrait les etats 0/1 des bordures de zones")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--image",  help="Image unique")
    group.add_argument("--images", help="Dossier d'images")
    parser.add_argument("--zones",          required=True)
    parser.add_argument("--out",            default=None)
    parser.add_argument("--epaisseur",      type=int, default=4)
    parser.add_argument("--seuil-blanc",    type=int, default=160)
    parser.add_argument("--tolerance-rangee", type=int, default=20)
    parser.add_argument("--debug",          action="store_true")
    args = parser.parse_args()

    zones = charger_zones(args.zones)
    print(f"{len(zones)} zone(s) chargee(s).")

    zones_triees = trier_zones(zones, tolerance=args.tolerance_rangee)
    print("Ordre de lecture :", " | ".join(
        f"#{z['id']} {z['label'] or '?'}" for z in zones_triees
    ))

    if args.image:
        images = [Path(args.image)]
    else:
        images = sorted(p for p in Path(args.images).iterdir()
                        if p.suffix.lower() in EXTENSIONS)
    print(f"{len(images)} image(s) a traiter.\n")

    if args.out is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = Path(args.images) if args.images else Path(args.image).parent
        args.out = str(base / f"etats_{ts}.csv")

    # En-têtes : image, timestamp, puis une colonne par zone
    entetes = ["image", "timestamp"] + [
        z["label"] if z["label"] else f"z{z['id']}" for z in zones_triees
    ]

    seuil_blanc = getattr(args, "seuil_blanc", 160)

    with open(args.out, "w", newline="", encoding="utf-8") as f_out:
        writer = csv.writer(f_out)
        writer.writerow(entetes)

        for img_path in images:
            # Timestamp depuis le nom de fichier si possible, sinon maintenant
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                nom = img_path.stem  # ex: capture_20260313_152412
                parties = nom.split("_")
                if len(parties) >= 3:
                    ts = datetime.strptime(
                        f"{parties[-2]}_{parties[-1]}", "%Y%m%d_%H%M%S"
                    ).strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                pass

            etats = traiter_image(img_path, zones_triees, args.epaisseur,
                                  seuil_blanc, debug=args.debug)
            if etats is not None:
                writer.writerow([img_path.name, ts] + etats)

    print(f"\nCSV sauvegarde : {args.out}")


if __name__ == "__main__":
    main()
