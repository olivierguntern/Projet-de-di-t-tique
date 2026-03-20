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
    --engine        : Moteur OCR : tesseract | easyocr                  [défaut : tesseract]
    --lang          : Langue(s) OCR                                     [défaut : fra+eng (tesseract) / fr,en (easyocr)]
    --tesseract-path: Chemin complet vers tesseract.exe si non dans PATH
    --preprocess    : Mode de prétraitement : auto | neon | aucun        [défaut : auto]
                      auto  = binarisation adaptative (documents, texte sombre sur fond clair)
                      neon  = texte lumineux/coloré sur fond sombre (interface jeu, HUD…)
                      aucun = image brute sans prétraitement
    --debug         : Enregistre les vignettes prétraitées dans ./debug_zones/

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

# Force UTF-8 sur stdout/stderr (Windows cp1252 ne supporte pas les caractères Unicode)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

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

def trouver_tesseract() -> str | None:
    """Cherche l'exécutable tesseract dans les emplacements courants (Windows)."""
    import glob
    candidates = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        r"C:\Users\*\AppData\Local\Programs\Tesseract-OCR\tesseract.exe",
        r"C:\tools\Tesseract-OCR\tesseract.exe",
    ]
    for pattern in candidates:
        matches = glob.glob(pattern)
        if matches:
            return matches[0]
    return None


def init_tesseract(lang: str, chemin_exe: str | None = None):
    try:
        import pytesseract
        if chemin_exe:
            # Chemin fourni explicitement
            if not os.path.isfile(chemin_exe):
                print(f"ERREUR : tesseract introuvable à : {chemin_exe}")
                sys.exit(1)
            pytesseract.pytesseract.tesseract_cmd = chemin_exe
            print(f"Tesseract : {chemin_exe}")
        elif sys.platform == "win32":
            trouve = trouver_tesseract()
            if trouve:
                pytesseract.pytesseract.tesseract_cmd = trouve
                print(f"Tesseract détecté : {trouve}")
            else:
                print(
                    "ERREUR : tesseract.exe introuvable.\n"
                    "  Solutions :\n"
                    "  1) Ajoutez Tesseract-OCR au PATH Windows, OU\n"
                    "  2) Utilisez : --tesseract-path \"C:\\chemin\\vers\\tesseract.exe\"\n"
                    "  Téléchargement : https://github.com/UB-Mannheim/tesseract/wiki"
                )
                sys.exit(1)
        return pytesseract, lang
    except ImportError:
        print("ERREUR : pytesseract non installé.\n  pip install pytesseract")
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

def pretraiter(crop: np.ndarray, mode: str = "auto") -> np.ndarray:
    """
    Prépare la zone pour l'OCR selon le mode choisi.

    auto  : binarisation adaptative — documents, texte sombre sur fond clair
    neon  : texte lumineux/coloré sur fond sombre (HUD, interface jeu…)
    aucun : image brute
    """
    if mode == "aucun":
        return crop

    if mode == "neon":
        # 1) Agrandissement 3× (Tesseract préfère les grandes images)
        h, w = crop.shape[:2]
        grand = cv2.resize(crop, (w * 3, h * 3), interpolation=cv2.INTER_CUBIC)

        # 2) Passage en HSV pour extraire la luminosité (canal V)
        #    Le texte néon est très lumineux même si coloré
        hsv = cv2.cvtColor(grand, cv2.COLOR_BGR2HSV)
        _, _, v = cv2.split(hsv)

        # 3) Légère réduction du halo (flou médian)
        v = cv2.medianBlur(v, 3)

        # 4) Seuillage OTSU : sépare automatiquement le texte brillant du fond sombre
        _, binaire = cv2.threshold(v, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

        # 5) Inversion → texte noir sur fond blanc (attendu par Tesseract)
        binaire = cv2.bitwise_not(binaire)

        # 6) Dilatation légère pour combler les trous dans les lettres
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2, 2))
        binaire = cv2.morphologyEx(binaire, cv2.MORPH_CLOSE, kernel)

        return cv2.cvtColor(binaire, cv2.COLOR_GRAY2BGR)

    # mode == "auto" : binarisation adaptative (défaut)
    gris = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    binaire = cv2.adaptiveThreshold(
        gris, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        blockSize=31, C=10
    )
    return cv2.cvtColor(binaire, cv2.COLOR_GRAY2BGR)


# ─── Traitement principal ─────────────────────────────────────────────────────

def traiter(images_dir: str, zones: list[dict], engine: str, lang: str,
            chemin_out: str, debug: bool, tesseract_path: str | None = None,
            preprocess: str = "auto"):

    # Initialiser le moteur OCR
    if engine == "tesseract":
        ctx = init_tesseract(lang or "fra+eng", tesseract_path)
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
        debug_dir = Path(images_dir) / "debug_zones"
        debug_dir.mkdir(exist_ok=True)

    # Écriture CSV de sortie
    with open(chemin_out, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["image", "zone_id", "label", "x", "y", "largeur", "hauteur", "texte_ocr"])

        for img_path in images:
            print(f"→ {img_path.name}")
            image = cv2.imdecode(np.fromfile(str(img_path), dtype=np.uint8), cv2.IMREAD_COLOR)
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
                crop_traite = pretraiter(crop, preprocess)

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
                    nom = str(debug_dir / f"{img_path.stem}_z{zone['id']}.png")
                    cv2.imencode(".png", crop_traite)[1].tofile(nom)

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
    parser.add_argument("--tesseract-path", default=None,
                        help=r'Chemin vers tesseract.exe, ex: "C:\Program Files\Tesseract-OCR\tesseract.exe"')
    parser.add_argument("--preprocess", default="auto",
                        choices=["auto", "neon", "aucun"],
                        help="Mode de prétraitement : auto | neon | aucun [défaut: auto]")
    parser.add_argument("--debug",  action="store_true",
                        help="Enregistre les vignettes prétraitées dans ./debug_zones/")
    args = parser.parse_args()

    if not os.path.isfile(args.zones):
        print(f"ERREUR : fichier de zones introuvable : {args.zones}")
        sys.exit(1)

    if not os.path.isdir(args.images):
        print(f"ERREUR : répertoire d'images introuvable : {args.images}")
        sys.exit(1)

    chemin_out = args.out or str(Path(args.images) / f"resultats_ocr_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    zones = charger_zones(args.zones)
    print(f"{len(zones)} zone(s) chargée(s) depuis {args.zones}")

    traiter(args.images, zones, args.engine, args.lang, chemin_out, args.debug,
            args.tesseract_path, args.preprocess)


if __name__ == "__main__":
    main()
