"""
Script de capture d'écran automatique
======================================
Prend une capture d'écran toutes les 10 secondes pendant N minutes.
Les captures sont sauvegardées dans le dossier 'captures/'.

Usage :
    python capture_ecran.py --duree 5               # capture pendant 5 minutes
    python capture_ecran.py --duree 10 --dossier mes_captures
    python capture_ecran.py --duree 5 --delai 5     # attend 5s avant de démarrer
    python capture_ecran.py --duree 5 --ecran 2     # capture l'écran n°2
    python capture_ecran.py --duree 5 --hotkey      # attend Ctrl+Espace pour démarrer
"""

import argparse
import os
import sys
import time
from datetime import datetime
import mss
import mss.tools

# Force UTF-8 sur stdout/stderr (Windows cp1252)
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _attendre_hotkey():
    """Bloque jusqu'à ce que Ctrl+Espace soit pressé."""
    try:
        import keyboard
        print("En attente de Ctrl+Espace pour demarrer la capture...")
        print("(installez 'keyboard' avec : pip install keyboard)")
        keyboard.wait("ctrl+space")
        print("Ctrl+Espace detecte — capture en cours !\n")
    except ImportError:
        print("ERREUR : la librairie 'keyboard' est requise pour --hotkey.")
        print("Installez-la avec : pip install keyboard")
        sys.exit(1)


def capturer_ecran(dossier: str, duree_minutes: float, intervalle: int = 10,
                   delai: int = 3, ecran: int = 1, hotkey: bool = False):
    """
    Capture l'écran toutes les `intervalle` secondes pendant `duree_minutes` minutes.

    Args:
        dossier: Dossier de destination des captures
        duree_minutes: Durée totale de la capture en minutes
        intervalle: Intervalle entre chaque capture en secondes (défaut: 10)
        delai: Secondes d'attente avant la première capture (défaut: 3)
        ecran: Numéro de l'écran à capturer (1 = principal, 2 = second écran)
        hotkey: Si True, attend Ctrl+Espace au lieu du compte à rebours
    """
    os.makedirs(dossier, exist_ok=True)

    duree_secondes = duree_minutes * 60
    nb_captures = int(duree_secondes / intervalle)

    with mss.mss() as sct:
        nb_ecrans = len(sct.monitors) - 1  # monitors[0] = tous les écrans combinés
        if ecran < 1 or ecran > nb_ecrans:
            print(f"Erreur : écran {ecran} introuvable. Écrans disponibles : 1 à {nb_ecrans}.")
            return
        monitor = sct.monitors[ecran]

    print(f"Démarrage de la capture :")
    print(f"  - Durée      : {duree_minutes} minute(s)")
    print(f"  - Intervalle : {intervalle} secondes")
    print(f"  - Captures   : {nb_captures}")
    print(f"  - Ecran      : {ecran} ({monitor['width']}x{monitor['height']})")
    print(f"  - Dossier    : {os.path.abspath(dossier)}")
    if hotkey:
        print(f"  - Démarrage  : Ctrl+Espace")
    print(f"  - Arrêt      : Ctrl+C\n")

    # Démarrage : hotkey ou compte à rebours
    if hotkey:
        _attendre_hotkey()
    elif delai > 0:
        print(f"Début dans {delai} secondes... Minimisez cette fenêtre !")
        for i in range(delai, 0, -1):
            print(f"  {i}...")
            time.sleep(1)
        print("Capture en cours !\n")

    with mss.mss() as sct:
        monitor = sct.monitors[ecran]

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
    parser.add_argument(
        "--delai",
        type=int,
        default=3,
        help="Secondes d'attente avant la première capture pour minimiser le terminal (défaut: 3)"
    )
    parser.add_argument(
        "--ecran",
        type=int,
        default=1,
        help="Numéro de l'écran à capturer : 1 = écran principal, 2 = second écran (défaut: 1)"
    )
    parser.add_argument(
        "--hotkey",
        action="store_true",
        help="Attendre Ctrl+Espace pour démarrer au lieu du compte à rebours (nécessite : pip install keyboard)"
    )

    args = parser.parse_args()

    if args.duree <= 0:
        print("Erreur : la durée doit être supérieure à 0.")
        return
    if args.intervalle <= 0:
        print("Erreur : l'intervalle doit être supérieur à 0.")
        return

    try:
        capturer_ecran(args.dossier, args.duree, args.intervalle,
                       args.delai, args.ecran, args.hotkey)
    except KeyboardInterrupt:
        print("\nCapture interrompue par l'utilisateur.")


if __name__ == "__main__":
    main()
