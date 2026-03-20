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
import random
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


def capturer_ecran(dossier: str, duree_minutes: float,
                   intervalle_min: int = 10, intervalle_max: int = 10,
                   delai: int = 3, ecran: int = 1, hotkey: bool = False):
    """
    Capture l'écran à intervalles aléatoires entre intervalle_min et intervalle_max secondes.

    Args:
        dossier: Dossier de destination des captures
        duree_minutes: Durée totale de la capture en minutes
        intervalle_min: Intervalle minimum en secondes (défaut: 10)
        intervalle_max: Intervalle maximum en secondes (défaut: = intervalle_min)
        delai: Secondes d'attente avant la première capture (défaut: 3)
        ecran: Numéro de l'écran à capturer (1 = principal, 2 = second écran)
        hotkey: Si True, attend Ctrl+Espace au lieu du compte à rebours
    """
    os.makedirs(dossier, exist_ok=True)

    duree_secondes = duree_minutes * 60
    intervalle_moy = (intervalle_min + intervalle_max) / 2
    nb_captures = int(duree_secondes / intervalle_moy)

    with mss.mss() as sct:
        nb_ecrans = len(sct.monitors) - 1
        if ecran < 1 or ecran > nb_ecrans:
            print(f"Erreur : écran {ecran} introuvable. Écrans disponibles : 1 à {nb_ecrans}.")
            return
        monitor = sct.monitors[ecran]

    print(f"Démarrage de la capture :")
    print(f"  - Durée      : {duree_minutes} minute(s)")
    if intervalle_min == intervalle_max:
        print(f"  - Intervalle : {intervalle_min} secondes")
    else:
        print(f"  - Intervalle : {intervalle_min}–{intervalle_max} secondes (aléatoire)")
    print(f"  - Captures   : ~{nb_captures}")
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
        debut = time.time()
        i = 0

        while time.time() - debut < duree_secondes:
            i += 1
            horodatage = datetime.now().strftime("%Y%m%d_%H%M%S")
            nom_fichier = os.path.join(dossier, f"capture_{horodatage}.png")

            sct_img = sct.grab(monitor)
            mss.tools.to_png(sct_img.rgb, sct_img.size, output=nom_fichier)

            attente = random.randint(intervalle_min, intervalle_max)
            restant = duree_secondes - (time.time() - debut)
            print(f"[{i:03d}] {nom_fichier}  (prochain dans {attente}s)")

            if restant > attente:
                time.sleep(attente)
            else:
                break

    print(f"\nCapture terminée. {i} image(s) sauvegardée(s) dans '{dossier}'.")


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
        default="D:\\roulette",
        help="Dossier de sauvegarde des captures (défaut: 'D:\\roulette')"
    )
    parser.add_argument(
        "--intervalle",
        type=int,
        default=10,
        help="Intervalle fixe entre les captures en secondes (défaut: 10)"
    )
    parser.add_argument(
        "--intervalle-min",
        type=int,
        default=None,
        help="Intervalle minimum (secondes) pour le mode aléatoire"
    )
    parser.add_argument(
        "--intervalle-max",
        type=int,
        default=None,
        help="Intervalle maximum (secondes) pour le mode aléatoire"
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

    # Résolution intervalle_min / intervalle_max
    i_min = args.intervalle_min if args.intervalle_min is not None else args.intervalle
    i_max = args.intervalle_max if args.intervalle_max is not None else i_min
    if i_min <= 0 or i_max <= 0:
        print("Erreur : les intervalles doivent être supérieurs à 0.")
        return
    if i_min > i_max:
        print("Erreur : intervalle-min doit être <= intervalle-max.")
        return

    try:
        capturer_ecran(args.dossier, args.duree, i_min, i_max,
                       args.delai, args.ecran, args.hotkey)
    except KeyboardInterrupt:
        print("\nCapture interrompue par l'utilisateur.")


if __name__ == "__main__":
    main()
