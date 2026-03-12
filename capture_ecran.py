"""
Script de capture d'écran automatique
======================================
Prend une capture d'écran toutes les 10 secondes pendant N minutes.
Les captures sont sauvegardées dans le dossier 'captures/'.

Usage :
    python capture_ecran.py --duree 5          # capture pendant 5 minutes
    python capture_ecran.py --duree 10 --dossier mes_captures
"""

import argparse
import os
import time
from datetime import datetime
import mss
import mss.tools


def capturer_ecran(dossier: str, duree_minutes: float, intervalle: int = 10):
    """
    Capture l'écran toutes les `intervalle` secondes pendant `duree_minutes` minutes.

    Args:
        dossier: Dossier de destination des captures
        duree_minutes: Durée totale de la capture en minutes
        intervalle: Intervalle entre chaque capture en secondes (défaut: 10)
    """
    os.makedirs(dossier, exist_ok=True)

    duree_secondes = duree_minutes * 60
    nb_captures = int(duree_secondes / intervalle)

    print(f"Démarrage de la capture :")
    print(f"  - Durée    : {duree_minutes} minute(s)")
    print(f"  - Intervalle : {intervalle} secondes")
    print(f"  - Captures prévues : {nb_captures}")
    print(f"  - Dossier  : {os.path.abspath(dossier)}")
    print(f"  - Appuyez sur Ctrl+C pour arrêter\n")

    with mss.mss() as sct:
        monitor = sct.monitors[0]  # Écran entier (tous les moniteurs)

        for i in range(1, nb_captures + 1):
            horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
            nom_fichier = os.path.join(dossier, f"capture_{horodatage}.png")

            sct_img = sct.grab(monitor)
            mss.tools.to_png(sct_img.rgb, sct_img.size, output=nom_fichier)

            print(f"[{i:03d}/{nb_captures}] {nom_fichier}")

            if i < nb_captures:
                time.sleep(intervalle)

    print(f"\nCapture terminée. {nb_captures} image(s) sauvegardée(s) dans '{dossier}'.")


def main():
    parser = argparse.ArgumentParser(
        description="Capture d'écran automatique toutes les 10 secondes."
    )
    parser.add_argument(
        "--duree",
        type=float,
        required=True,
        help="Durée de la capture en minutes (ex: 5 pour 5 minutes)"
    )
    parser.add_argument(
        "--dossier",
        type=str,
        default="captures",
        help="Dossier de sauvegarde des captures (défaut: 'captures')"
    )
    parser.add_argument(
        "--intervalle",
        type=int,
        default=10,
        help="Intervalle entre les captures en secondes (défaut: 10)"
    )

    args = parser.parse_args()

    if args.duree <= 0:
        print("Erreur : la durée doit être supérieure à 0.")
        return
    if args.intervalle <= 0:
        print("Erreur : l'intervalle doit être supérieur à 0.")
        return

    try:
        capturer_ecran(args.dossier, args.duree, args.intervalle)
    except KeyboardInterrupt:
        print("\nCapture interrompue par l'utilisateur.")


if __name__ == "__main__":
    main()
