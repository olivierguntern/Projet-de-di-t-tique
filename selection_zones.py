"""
Script de sélection de zones rectangulaires avec OpenCV
=========================================================
Permet de sélectionner des zones rectangulaires sur une image (ou capture d'écran)
en cliquant-glissant la souris. Les coordonnées sont enregistrées dans un fichier CSV.

Usage :
    python selection_zones.py                          # ouvre une capture d'écran
    python selection_zones.py --image mon_image.png    # ouvre une image existante
    python selection_zones.py --csv mes_zones.csv      # fichier CSV de sortie

Contrôles :
    - Clic gauche + glisser : Dessiner un rectangle
    - Entrée / Espace       : Valider et sauvegarder la zone
    - Z                     : Annuler la dernière zone
    - C                     : Effacer toutes les zones
    - Q / Echap             : Quitter et sauvegarder le CSV
"""

import argparse
import csv
import os
from datetime import datetime
from typing import Optional

import cv2
import numpy as np
import mss
import mss.tools


# ─── Variables globales pour le callback souris ───────────────────────────────

drawing = False          # True pendant le clic-glissé
pt_debut = (-1, -1)      # Point de départ du rectangle
pt_fin = (-1, -1)        # Point de fin du rectangle
rect_courant = None      # Rectangle en cours de dessin
zones = []               # Liste des zones validées : [(x, y, w, h, label)]


def faire_capture() -> np.ndarray:
    """Prend une capture d'écran et retourne un tableau numpy (BGR)."""
    with mss.mss() as sct:
        monitor = sct.monitors[0]
        sct_img = sct.grab(monitor)
        # mss retourne BGRA, on enlève le canal alpha
        img = np.array(sct_img)[:, :, :3]
    return img


def callback_souris(event, x, y, flags, param):
    """Callback OpenCV pour la gestion des événements souris."""
    global drawing, pt_debut, pt_fin, rect_courant

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        pt_debut = (x, y)
        pt_fin = (x, y)
        rect_courant = None

    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            pt_fin = (x, y)

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        pt_fin = (x, y)
        # Normaliser pour garantir x1 < x2 et y1 < y2
        x1 = min(pt_debut[0], pt_fin[0])
        y1 = min(pt_debut[1], pt_fin[1])
        x2 = max(pt_debut[0], pt_fin[0])
        y2 = max(pt_debut[1], pt_fin[1])
        if (x2 - x1) > 2 and (y2 - y1) > 2:
            rect_courant = (x1, y1, x2 - x1, y2 - y1)


def dessiner_zones(image: np.ndarray, zones: list, rect_temp=None) -> np.ndarray:
    """
    Dessine toutes les zones validées et le rectangle en cours sur l'image.

    Args:
        image: Image de fond (non modifiée)
        zones: Liste des zones [(x, y, w, h, label)]
        rect_temp: Rectangle temporaire en cours de dessin (x1,y1,x2,y2) ou None

    Returns:
        Image avec les rectangles dessinés
    """
    affichage = image.copy()

    # Zones validées (vert)
    for idx, (x, y, w, h, label) in enumerate(zones):
        cv2.rectangle(affichage, (x, y), (x + w, y + h), (0, 200, 0), 2)
        texte = f"#{idx + 1} {label}" if label else f"#{idx + 1}"
        cv2.putText(
            affichage, texte, (x + 4, y + 18),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 200, 0), 2
        )

    # Rectangle temporaire en cours (bleu)
    if rect_temp is not None:
        x1, y1, x2, y2 = rect_temp
        cv2.rectangle(affichage, (x1, y1), (x2, y2), (255, 100, 0), 2)

    # Légende
    h_img = affichage.shape[0]
    lignes = [
        "Clic+glisser : Dessiner  |  Entree : Valider  |  Z : Annuler derniere",
        "C : Tout effacer  |  Q/Echap : Quitter et sauvegarder",
    ]
    for i, ligne in enumerate(lignes):
        cv2.putText(
            affichage, ligne, (10, h_img - 30 + i * 20),
            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 50, 255), 1
        )

    return affichage


def demander_label() -> str:
    """Demande un label pour la zone dans le terminal."""
    label = input("  Label pour cette zone (laisser vide pour ignorer) : ").strip()
    return label


def sauvegarder_csv(zones: list, chemin_csv: str):
    """
    Sauvegarde les zones dans un fichier CSV.

    Colonnes : id, label, x, y, largeur, hauteur, x2, y2
    """
    with open(chemin_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "label", "x", "y", "largeur", "hauteur", "x2", "y2"])
        for idx, (x, y, w, h, label) in enumerate(zones, start=1):
            writer.writerow([idx, label, x, y, w, h, x + w, y + h])

    print(f"\n{len(zones)} zone(s) sauvegardée(s) dans : {os.path.abspath(chemin_csv)}")


def selectionner_zones(image: np.ndarray, chemin_csv: str):
    """
    Lance l'interface interactive de sélection de zones.

    Args:
        image: Image sur laquelle sélectionner les zones
        chemin_csv: Chemin du fichier CSV de sortie
    """
    global drawing, pt_debut, pt_fin, rect_courant, zones

    fenetre = "Selection de zones - Q pour quitter"
    cv2.namedWindow(fenetre, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(fenetre, min(image.shape[1], 1400), min(image.shape[0], 900))
    cv2.setMouseCallback(fenetre, callback_souris)

    print("\nFenêtre OpenCV ouverte.")
    print("Dessinez des rectangles avec la souris, puis :")
    print("  Entree/Espace : valider la zone sélectionnée")
    print("  Z             : annuler la dernière zone")
    print("  C             : effacer tout")
    print("  Q / Echap     : quitter et sauvegarder\n")

    while True:
        # Construire le rectangle temporaire pour l'affichage live
        rect_temp = None
        if drawing and pt_debut != (-1, -1):
            x1 = min(pt_debut[0], pt_fin[0])
            y1 = min(pt_debut[1], pt_fin[1])
            x2 = max(pt_debut[0], pt_fin[0])
            y2 = max(pt_debut[1], pt_fin[1])
            rect_temp = (x1, y1, x2, y2)

        affichage = dessiner_zones(image, zones, rect_temp)
        cv2.imshow(fenetre, affichage)

        touche = cv2.waitKey(30) & 0xFF

        # Valider la zone courante
        if touche in (13, 32) and rect_courant is not None:  # Entrée ou Espace
            x, y, w, h = rect_courant
            print(f"\nZone {len(zones) + 1} : x={x}, y={y}, largeur={w}, hauteur={h}")
            label = demander_label()
            zones.append((x, y, w, h, label))
            rect_courant = None
            print(f"  -> Zone #{len(zones)} enregistrée.")

        # Annuler la dernière zone
        elif touche == ord('z') or touche == ord('Z'):
            if zones:
                supprimee = zones.pop()
                print(f"Zone #{len(zones) + 1} annulée.")
            else:
                print("Aucune zone à annuler.")

        # Effacer toutes les zones
        elif touche == ord('c') or touche == ord('C'):
            zones.clear()
            rect_courant = None
            print("Toutes les zones ont été effacées.")

        # Quitter
        elif touche in (27, ord('q'), ord('Q')):  # Echap ou Q
            break

    cv2.destroyAllWindows()

    if zones:
        sauvegarder_csv(zones, chemin_csv)
    else:
        print("Aucune zone enregistrée.")


def main():
    parser = argparse.ArgumentParser(
        description="Sélection de zones rectangulaires sur image avec OpenCV → CSV"
    )
    parser.add_argument(
        "--image",
        type=str,
        default=None,
        help="Chemin vers une image existante. Si absent, une capture d'écran est prise."
    )
    parser.add_argument(
        "--csv",
        type=str,
        default=None,
        help="Chemin du fichier CSV de sortie (défaut: zones_YYYYMMDD_HHMMSS.csv)"
    )
    args = parser.parse_args()

    # Fichier CSV de sortie
    if args.csv:
        chemin_csv = args.csv
    else:
        horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
        chemin_csv = f"zones_{horodatage}.csv"

    # Chargement de l'image
    if args.image:
        image = cv2.imread(args.image)
        if image is None:
            print(f"Erreur : impossible d'ouvrir '{args.image}'.")
            return
        print(f"Image chargée : {args.image}")
    else:
        print("Prise d'une capture d'écran...")
        image = faire_capture()
        print("Capture prête.")

    selectionner_zones(image, chemin_csv)


if __name__ == "__main__":
    main()
