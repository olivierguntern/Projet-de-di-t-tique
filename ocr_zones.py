"""
OCR sur zones sélectionnées pour un répertoire d'images
=========================================================
Lit un fichier CSV de zones (généré par selection_zones.py), applique
l'OCR sur chaque zone de chaque image d'un répertoire, et enregistre
les résultats dans un CSV.

Usage :
    python ocr_zones.py --zones zones.csv --images ./captures --out resultats.csv
    python ocr_zones.py --zones zones.csv --images ./captures --engine easyocr --lang fr

Arguments :
    --zones   : CSV des zones (x, y, largeur, hauteur, label)          [obligatoire]
    --images  : Répertoire contenant les images à analyser              [défaut : .]
    --out     : Fichier CSV de sortie                                   [défaut : resultats_ocr_DATETIME.csv]
    --engine  : Moteur OCR : tesseract | easyocr                        [défaut : tesseract]
    --lang    : Langue(s) OCR                                           [défaut : fra+eng (tesseract) / fr,en (easyocr)]
    --debug   : Enregistre les vignettes de chaque zone dans ./debug_zones/

Installation :
    pip install pytesseract pillow          # + Tesseract-OCR : https://github.com/UB-Mannheim/tesseract/wiki
    pip install easyocr                     # alternative sans binaire externe
"""

import argparse
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

# ─── Extensions d'images acceptées ────────────────────────────────────────────
EXTENSIONS = {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"}


# ─── Chargement des zones ─────────────────────────────────────────────────────

def charger_zones(chemin_csv: str) -> list[dict]:
    """Retourne la liste des zones depuis le CSV de selection_zones.py."""
    zones = []
    with open(chemin_csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            zones.append({
                "id":     int(row["id"]),
                "label":  row.get("label", "").strip(),
                "x":      int(row["x"]),
                "y":      int(row["y"]),
                "w":      int(row["largeur"]),
                "h":      int(row["hauteur"]),
            })
    return zones


# ─── Moteur Tesseract ─────────────────────────────────────────────────────────

def init_tesseract(lang: str):
    try:
        import pytesseract
        # Cherche l'exécutable Tesseract sur Windows si non dans le PATH
        if sys.platform == "win32":
            candidates = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
            ]
            for c in candidates:
                if os.path.isfile(c):
                    pytesseract.pytesseract.tesseract_cmd = c
                    break
        return pytesseract, lang
    except ImportError:
        print("ERREUR : pytesseract non installé.\n"
              "  pip install pytesseract\n"
              "  + installer Tesseract-OCR : https://github.com/UB-Mannheim/tesseract/wiki")
        sys.exit(1)


def ocr_tesseract(engine_ctx, crop: np.ndarray) -> str:
    pytesseract, lang = engine_ctx
    from PIL import Image
    img_pil = Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
    texte = pytesseract.image_to_string(img_pil, lang=lang, config="--psm 6")
    return texte.strip()


# ─── Moteur EasyOCR ───────────────────────────────────────────────────────────

def init_easyocr(lang: str):
    try:
        import easyocr
        # lang ex: "fr,en" -> ["fr", "en"]
        langues = [l.strip() for l in lang.split(",")]
        print(f"Chargement du modèle EasyOCR ({langues})…")
        reader = easyocr.Reader(langues, gpu=False)
        return reader
    except ImportError:
        print("ERREUR : easyocr non installé.\n  pip install easyocr")
        sys.exit(1)


def ocr_easyocr(reader, crop: np.ndarray) -> str:
    resultats = reader.readtext(crop, detail=0, paragraph=True)
    return " ".join(resultats).strip()


# ─── Prétraitement image ──────────────────────────────────────────────────────

def pretraiter(crop: np.ndarray) -> np.ndarray:
    """Améliore le contraste pour l'OCR (niveaux de gris + binarisation adaptative)."""
    gris = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # Binarisation adaptative (utile pour les fonds non uniformes)
    binaire = cv2.adaptiveThreshold(
        gris, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31, C=10
    )
    # Repasse en BGR pour compatibilité avec les deux moteurs
    return cv2.cvtColor(binaire, cv2.COLOR_GRAY2BGR)


# ─── Traitement principal ─────────────────────────────────────────────────────

def traiter(images_dir: str, zones: list[dict], engine: str, lang: str,
            chemin_out: str, debug: bool):

    # Initialiser le moteur OCR
    if engine == "tesseract":
        ctx = init_tesseract(lang or "fra+eng")
        fn_ocr = ocr_tesseract
    else:
        ctx = init_easyocr(lang or "fr,en")
        fn_ocr = ocr_easyocr

    # Lister les images
    images = sorted([
        p for p in Path(images_dir).iterdir()
        if p.suffix.lower() in EXTENSIONS
    ])
    if not images:
        print(f"Aucune image trouvée dans : {images_dir}")
        return

    print(f"\n{len(images)} image(s) trouvée(s), {len(zones)} zone(s) à analyser.\n")

    # Répertoire debug
    if debug:
        Path("debug_zones").mkdir(exist_ok=True)

    # Écriture CSV de sortie
    with open(chemin_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["image", "zone_id", "label", "x", "y", "largeur", "hauteur", "texte_ocr"])

        for img_path in images:
            print(f"→ {img_path.name}")
            image = cv2.imread(str(img_path))
            if image is None:
                print(f"   ERREUR : impossible de charger l'image, ignorée.")
                continue

            h_img, w_img = image.shape[:2]

            for zone in zones:
                x, y, w, h = zone["x"], zone["y"], zone["w"], zone["h"]

                # Clamp aux dimensions de l'image
                x  = max(0, min(x,  w_img - 1))
                y  = max(0, min(y,  h_img - 1))
                w  = max(1, min(w,  w_img - x))
                h  = max(1, min(h,  h_img - y))

                crop = image[y:y + h, x:x + w]
                crop_traite = pretraiter(crop)

                try:
                    texte = fn_ocr(ctx, crop_traite)
                except Exception as e:
                    texte = f"[ERREUR OCR : {e}]"

                # Texte sur une seule ligne pour le CSV
                texte_csv = texte.replace("\n", " ").replace("\r", "")

                writer.writerow([
                    img_path.name,
                    zone["id"],
                    zone["label"],
                    x, y, w, h,
                    texte_csv,
                ])

                print(f"   Zone #{zone['id']} ({zone['label'] or '-'}) : {texte_csv[:80]}")

                if debug:
                    nom = f"debug_zones/{img_path.stem}_z{zone['id']}.png"
                    cv2.imwrite(nom, crop)

        print(f"\nRésultats sauvegardés dans : {os.path.abspath(chemin_out)}")


# ─── CLI ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="OCR sur zones sélectionnées — répertoire d'images → CSV"
    )
    parser.add_argument("--zones",  required=True, help="CSV des zones (selection_zones.py)")
    parser.add_argument("--images", default=".",   help="Répertoire d'images [défaut: .]")
    parser.add_argument("--out",    default=None,  help="CSV de sortie")
    parser.add_argument("--engine", default="tesseract", choices=["tesseract", "easyocr"],
                        help="Moteur OCR [défaut: tesseract]")
    parser.add_argument("--lang",   default=None,
                        help="Langue(s) : fra+eng (tesseract) ou fr,en (easyocr)")
    parser.add_argument("--debug",  action="store_true",
                        help="Enregistre les vignettes de zones dans ./debug_zones/")
    args = parser.parse_args()

    if not os.path.isfile(args.zones):
        print(f"ERREUR : fichier de zones introuvable : {args.zones}")
        sys.exit(1)

    if not os.path.isdir(args.images):
        print(f"ERREUR : répertoire d'images introuvable : {args.images}")
        sys.exit(1)

    chemin_out = args.out or f"resultats_ocr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    zones = charger_zones(args.zones)
    print(f"{len(zones)} zone(s) chargée(s) depuis {args.zones}")

    traiter(args.images, zones, args.engine, args.lang, chemin_out, args.debug)


if __name__ == "__main__":
    main()
