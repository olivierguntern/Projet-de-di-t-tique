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
    - Entrée / Espace       : Valider la zone en cours
    - Z                     : Annuler la dernière zone validée
    - C                     : Effacer toutes les zones
    - Q / Echap             : Quitter (les labels sont demandés ensuite dans le terminal)
"""

import argparse
import csv
import os
from datetime import datetime

import cv2
import numpy as np
import mss
import mss.tools


# ─── Variables globales pour le callback souris ───────────────────────────────

drawing = False
pt_debut = (-1, -1)
pt_fin = (-1, -1)
rect_courant = None   # Rectangle terminé en attente de validation : (x, y, w, h)
zones = []            # Zones validées : [(x, y, w, h)]


def faire_capture() -> np.ndarray:
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        sct_img = sct.grab(monitor)
        img = np.array(sct_img)[:, :, :3]
    return img


def callback_souris(event, x, y, flags, param):
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
        x1 = min(pt_debut[0], pt_fin[0])
        y1 = min(pt_debut[1], pt_fin[1])
        x2 = max(pt_debut[0], pt_fin[0])
        y2 = max(pt_debut[1], pt_fin[1])
        if (x2 - x1) > 2 and (y2 - y1) > 2:
            rect_courant = (x1, y1, x2 - x1, y2 - y1)


def dessiner_zones(image: np.ndarray, zones: list, rect_temp=None, rect_valide=None) -> np.ndarray:
    affichage = image.copy()

    # Zones validées (vert)
    for idx, (x, y, w, h) in enumerate(zones):
        cv2.rectangle(affichage, (x, y), (x + w, y + h), (0, 200, 0), 2)
        cv2.putText(affichage, f"#{idx + 1}", (x + 4, y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 200, 0), 2)

    # Rectangle en cours de dessin (bleu clair)
    if rect_temp is not None:
        x1, y1, x2, y2 = rect_temp
        cv2.rectangle(affichage, (x1, y1), (x2, y2), (255, 150, 0), 2)

    # Rectangle terminé, en attente de validation (orange)
    if rect_valide is not None:
        x, y, w, h = rect_valide
        cv2.rectangle(affichage, (x, y), (x + w, y + h), (0, 165, 255), 2)
        cv2.putText(affichage, "ENTREE=valider  Z=annuler", (x + 4, y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 165, 255), 2)

    # Légende en bas
    h_img = affichage.shape[0]
    cv2.rectangle(affichage, (0, h_img - 42), (affichage.shape[1], h_img), (30, 30, 30), -1)
    cv2.putText(affichage,
                "Dessiner: clic+glisser  |  Valider: Entree/Espace  |  Annuler derniere: Z  |  Tout effacer: C  |  Quitter: Q",
                (8, h_img - 24), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (200, 200, 200), 1)
    cv2.putText(affichage, f"Zones enregistrees : {len(zones)}",
                (8, h_img - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 220, 0), 1)

    return affichage


def sauvegarder_csv(zones: list, labels: list, chemin_csv: str):
    with open(chemin_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "label", "x", "y", "largeur", "hauteur", "x2", "y2"])
        for idx, ((x, y, w, h), label) in enumerate(zip(zones, labels), start=1):
            writer.writerow([idx, label, x, y, w, h, x + w, y + h])
    print(f"\n{len(zones)} zone(s) sauvegardée(s) dans : {os.path.abspath(chemin_csv)}")


def selectionner_zones(image: np.ndarray, chemin_csv: str):
    global drawing, pt_debut, pt_fin, rect_courant, zones

    fenetre = "Selection de zones  -  Q pour quitter"
    cv2.namedWindow(fenetre, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(fenetre, min(image.shape[1], 1400), min(image.shape[0], 900))
    cv2.setMouseCallback(fenetre, callback_souris)

    print("Fenetre ouverte.")
    print("  Dessinez des rectangles, puis Entree pour valider, Q pour quitter.\n")

    while True:
        # Rectangle temporaire (pendant le glisser)
        rect_temp = None
        if drawing:
            x1 = min(pt_debut[0], pt_fin[0])
            y1 = min(pt_debut[1], pt_fin[1])
            x2 = max(pt_debut[0], pt_fin[0])
            y2 = max(pt_debut[1], pt_fin[1])
            rect_temp = (x1, y1, x2, y2)

        affichage = dessiner_zones(image, zones, rect_temp, rect_courant)
        cv2.imshow(fenetre, affichage)

        touche = cv2.waitKey(30) & 0xFF

        # Valider la zone en attente
        if touche in (13, 32):  # Entrée ou Espace
            if rect_courant is not None:
                zones.append(rect_courant)
                print(f"Zone #{len(zones)} validee : x={rect_courant[0]}, y={rect_courant[1]}, "
                      f"largeur={rect_courant[2]}, hauteur={rect_courant[3]}")
                rect_courant = None

        # Annuler la dernière zone
        elif touche in (ord('z'), ord('Z')):
            if rect_courant is not None:
                rect_courant = None
                print("Rectangle annule.")
            elif zones:
                zones.pop()
                print(f"Derniere zone supprimee. Zones restantes : {len(zones)}")

        # Effacer tout
        elif touche in (ord('c'), ord('C')):
            zones.clear()
            rect_courant = None
            print("Toutes les zones effacees.")

        # Quitter
        elif touche in (27, ord('q'), ord('Q')):
            break

        # Fermeture via la croix de la fenêtre
        if cv2.getWindowProperty(fenetre, cv2.WND_PROP_VISIBLE) < 1:
            break

    cv2.destroyAllWindows()

    if not zones:
        print("Aucune zone enregistree.")
        return

    # Demander les labels via popup tkinter (fonctionne depuis le launcher)
    print(f"\n{len(zones)} zone(s) selectionnee(s).")
    print("Saisie des labels via popup...")
    labels = []
    try:
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        for idx, (x, y, w, h) in enumerate(zones, start=1):
            label = simpledialog.askstring(
                title=f"Zone #{idx}",
                prompt=f"Zone #{idx}  (x={x}, y={y}, w={w}, h={h})\nLabel :",
                parent=root,
            ) or ""
            label = label.strip()
            labels.append(label)
            print(f"  Zone #{idx} -> label : '{label}'")
        root.destroy()
    except Exception:
        # Fallback terminal si tkinter indisponible
        for idx, (x, y, w, h) in enumerate(zones, start=1):
            label = input(f"  Zone #{idx} (x={x}, y={y}, w={w}, h={h}) - Label : ").strip()
            labels.append(label)

    sauvegarder_csv(zones, labels, chemin_csv)


def main():
    parser = argparse.ArgumentParser(
        description="Selection de zones rectangulaires sur image avec OpenCV -> CSV"
    )
    parser.add_argument(
        "--image", type=str, default=None,
        help="Chemin vers une image. Si absent, capture d'ecran automatique."
    )
    parser.add_argument(
        "--csv", type=str, default=None,
        help="Fichier CSV de sortie (defaut: zones_YYYYMMDD_HHMMSS.csv)"
    )
    args = parser.parse_args()

    chemin_csv = args.csv or f"zones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    if args.image:
        image = cv2.imread(args.image)
        if image is None:
            print(f"Erreur : impossible d'ouvrir '{args.image}'.")
            return
        print(f"Image chargee : {args.image}")
    else:
        print("Prise d'une capture d'ecran...")
        image = faire_capture()
        print("Capture prete.")

    selectionner_zones(image, chemin_csv)


if __name__ == "__main__":
    main()
