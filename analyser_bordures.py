"""
Analyse des bordures de zones rectangulaires
=============================================
Pour chaque zone définie dans un CSV (généré par selection_zones.py),
détermine si le bord du rectangle est BLANC (zone active) ou ROUGE (zone inactive).

Méthode :
  - Echantillonne les pixels sur le périmètre intérieur du rectangle (épaisseur configurable)
  - Calcule la moyenne R, G, B des pixels de bordure
  - Blanc  : R élevé ET G élevé ET B élevé  (tous canaux > seuil_blanc)
  - Rouge  : R élevé ET G faible ET B faible (R >> G et R >> B)

Usage :
    python analyser_bordures.py --image capture.png --zones zones.csv
    python analyser_bordures.py --image capture.png --zones zones.csv --out resultats.csv
    python analyser_bordures.py --images ./captures --zones zones.csv --out resultats.csv

Arguments :
    --image   : Image unique à analyser
    --images  : Dossier d'images à analyser en lot
    --zones   : CSV des zones (x, y, largeur, hauteur, label)   [obligatoire]
    --out     : CSV de sortie                                    [défaut : bordures_DATETIME.csv]
    --epaisseur : Épaisseur du bord à échantillonner en pixels   [défaut : 4]
    --seuil-blanc : Valeur min R,G,B pour considérer blanc       [défaut : 160]
    --debug   : Affiche une image annotée par zone
"""

import argparse
import csv
import sys
from datetime import datetime
from pathlib import Path

# Force UTF-8 sur stdout/stderr (Windows cp1252)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import cv2
import numpy as np

EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}


# ─── Chargement des zones ─────────────────────────────────────────────────────

def charger_zones(chemin_csv: str) -> list[dict]:
    zones = []
    with open(chemin_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            zones.append({
                "id":    int(row["id"]),
                "label": row.get("label", "").strip(),
                "x":     int(row["x"]),
                "y":     int(row["y"]),
                "w":     int(row["largeur"]),
                "h":     int(row["hauteur"]),
            })
    return zones


# ─── Analyse d'une zone ───────────────────────────────────────────────────────

def extraire_pixels_bord(img: np.ndarray, x: int, y: int, w: int, h: int, epaisseur: int) -> np.ndarray:
    """Retourne les pixels situés sur le bord intérieur du rectangle."""
    # Clamp aux dimensions de l'image
    ih, iw = img.shape[:2]
    x1, y1 = max(x, 0), max(y, 0)
    x2, y2 = min(x + w, iw), min(y + h, ih)
    ep = min(epaisseur, (x2 - x1) // 2, (y2 - y1) // 2)
    if ep <= 0:
        return img[y1:y2, x1:x2].reshape(-1, 3)

    pixels = []
    # Bord haut
    pixels.append(img[y1:y1+ep, x1:x2].reshape(-1, 3))
    # Bord bas
    pixels.append(img[y2-ep:y2, x1:x2].reshape(-1, 3))
    # Bord gauche (sans les coins déjà pris)
    pixels.append(img[y1+ep:y2-ep, x1:x1+ep].reshape(-1, 3))
    # Bord droit
    pixels.append(img[y1+ep:y2-ep, x2-ep:x2].reshape(-1, 3))

    return np.concatenate(pixels, axis=0).astype(np.float32)


def classifier_couleur(pixels: np.ndarray, seuil_blanc: int) -> dict:
    """
    Classe les pixels en blanc ou rouge.
    Retourne un dict avec : couleur, score_blanc, score_rouge, r_moy, g_moy, b_moy
    """
    if len(pixels) == 0:
        return {"couleur": "inconnu", "score_blanc": 0, "score_rouge": 0,
                "r_moy": 0, "g_moy": 0, "b_moy": 0}

    # OpenCV : ordre BGR
    b_moy = float(np.mean(pixels[:, 0]))
    g_moy = float(np.mean(pixels[:, 1]))
    r_moy = float(np.mean(pixels[:, 2]))

    # Score blanc : tous les canaux élevés
    # Score rouge : R >> G et R >> B
    score_blanc = min(r_moy, g_moy, b_moy)          # plus c'est élevé, plus c'est blanc
    score_rouge = r_moy - max(g_moy, b_moy)          # plus c'est élevé, plus c'est rouge

    if score_blanc >= seuil_blanc:
        couleur = "blanc"
    elif score_rouge > 40 and r_moy > 120:
        couleur = "rouge"
    else:
        couleur = "inconnu"

    return {
        "couleur":     couleur,
        "score_blanc": round(score_blanc, 1),
        "score_rouge": round(score_rouge, 1),
        "r_moy":       round(r_moy, 1),
        "g_moy":       round(g_moy, 1),
        "b_moy":       round(b_moy, 1),
    }


def analyser_zones(img: np.ndarray, zones: list[dict], epaisseur: int, seuil_blanc: int,
                   debug: bool = False, nom_image: str = "") -> list[dict]:
    resultats = []
    img_debug = img.copy() if debug else None

    for z in zones:
        pixels = extraire_pixels_bord(img, z["x"], z["y"], z["w"], z["h"], epaisseur)
        info = classifier_couleur(pixels, seuil_blanc)

        resultat = {
            "image":       nom_image,
            "id":          z["id"],
            "label":       z["label"],
            "x":           z["x"],
            "y":           z["y"],
            "largeur":     z["w"],
            "hauteur":     z["h"],
            **info,
        }
        resultats.append(resultat)

        couleur_label = info["couleur"]
        print(f"  Zone #{z['id']} '{z['label']}' -> {couleur_label.upper()}"
              f"  (R={info['r_moy']:.0f} G={info['g_moy']:.0f} B={info['b_moy']:.0f})")

        if debug and img_debug is not None:
            col_rect = (255, 255, 255) if couleur_label == "blanc" else (0, 0, 220)
            cv2.rectangle(img_debug, (z["x"], z["y"]),
                          (z["x"]+z["w"], z["y"]+z["h"]), col_rect, 2)
            cv2.putText(img_debug, couleur_label, (z["x"]+4, z["y"]+18),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, col_rect, 2)

    if debug and img_debug is not None:
        cv2.imshow("Bordures detectees", img_debug)
        cv2.waitKey(0)
        cv2.destroyAllWindows()

    return resultats


# ─── Écriture CSV ─────────────────────────────────────────────────────────────

CHAMPS_CSV = ["image", "id", "label", "x", "y", "largeur", "hauteur",
              "couleur", "score_blanc", "score_rouge", "r_moy", "g_moy", "b_moy"]


def ecrire_csv(resultats: list[dict], chemin: str):
    with open(chemin, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CHAMPS_CSV)
        writer.writeheader()
        writer.writerows(resultats)
    print(f"\nResultats sauvegardes : {chemin}")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Analyse couleur des bordures de zones rectangulaires")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--image",  help="Image unique a analyser")
    group.add_argument("--images", help="Dossier d'images a analyser")
    parser.add_argument("--zones",         required=True, help="CSV des zones")
    parser.add_argument("--out",           default=None,  help="CSV de sortie")
    parser.add_argument("--epaisseur",     type=int, default=4,   help="Epaisseur du bord en pixels (defaut: 4)")
    parser.add_argument("--seuil-blanc",   type=int, default=160, help="Seuil min pour blanc (defaut: 160)")
    parser.add_argument("--debug",         action="store_true",   help="Affiche l'image annotee")
    args = parser.parse_args()

    # Zones
    zones = charger_zones(args.zones)
    print(f"{len(zones)} zone(s) chargee(s) depuis {args.zones}")

    # Liste d'images
    if args.image:
        images = [Path(args.image)]
    else:
        dossier = Path(args.images)
        images = sorted(p for p in dossier.iterdir() if p.suffix.lower() in EXTENSIONS)
    print(f"{len(images)} image(s) a analyser.")

    # CSV de sortie
    if args.out is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        args.out = f"bordures_{ts}.csv"

    seuil_blanc = getattr(args, "seuil_blanc", 160)

    tous_resultats = []
    for img_path in images:
        print(f"\n-> {img_path.name}")
        img = cv2.imdecode(np.fromfile(str(img_path), dtype=np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            print(f"   [ERREUR] Impossible de lire l'image.")
            continue
        r = analyser_zones(img, zones, args.epaisseur, seuil_blanc,
                           debug=args.debug, nom_image=img_path.name)
        tous_resultats.extend(r)

    if tous_resultats:
        ecrire_csv(tous_resultats, args.out)

    # Résumé
    blancs = sum(1 for r in tous_resultats if r["couleur"] == "blanc")
    rouges = sum(1 for r in tous_resultats if r["couleur"] == "rouge")
    print(f"\nResume : {blancs} blanc(s), {rouges} rouge(s) sur {len(tous_resultats)} zone(s).")


if __name__ == "__main__":
    main()
