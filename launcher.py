#!/usr/bin/env python3
"""
Interface graphique — Outils Diététique (Analyse OCR)
======================================================
Lance les 9 scripts du projet depuis une interface conviviale.

Usage :
    python launcher.py

Pipeline conseillé :
    1. Capture d'écran  → captures/capture_YYYYMMDD_HHMMSS.png
    2. Sélection zones  → zones_YYYYMMDD_HHMMSS.csv
    3. OCR zones        → resultats_ocr_YYYYMMDD_HHMMSS.csv
    4. Filtrer OCR      → {nom}_chiffres.csv
    5. Dédupliquer      → {nom}_dedup.csv
    6. Analyser patterns / cycles / prédire
"""

import os
import sys
import subprocess
import threading
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext, messagebox

SCRIPTS_DIR = Path(__file__).parent

# ── Palette ────────────────────────────────────────────────────────────────────
FOND       = "#1e1e2e"
PANEL      = "#2a2a3e"
ACCENT     = "#7c3aed"
TEXTE      = "#e2e8f0"
GRIS       = "#94a3b8"
VERT       = "#22c55e"
ROUGE      = "#ef4444"
FOND_INPUT = "#12121f"


# ── Widgets réutilisables ──────────────────────────────────────────────────────

class Console(scrolledtext.ScrolledText):
    """Zone de sortie colorée."""

    def __init__(self, parent, **kw):
        super().__init__(parent, **kw)
        self.config(state=tk.DISABLED, wrap=tk.WORD, font=("Consolas", 9),
                    bg="#0d0d1a", fg=TEXTE, insertbackground=TEXTE,
                    selectbackground=ACCENT, borderwidth=0)
        self.tag_config("info",   foreground=VERT)
        self.tag_config("erreur", foreground=ROUGE)
        self.tag_config("cmd",    foreground="#a78bfa")
        self.tag_config("normal", foreground=TEXTE)

    def ecrire(self, texte: str, tag: str = "normal"):
        self.config(state=tk.NORMAL)
        self.insert(tk.END, texte, tag)
        self.see(tk.END)
        self.config(state=tk.DISABLED)

    def effacer(self):
        self.config(state=tk.NORMAL)
        self.delete("1.0", tk.END)
        self.config(state=tk.DISABLED)


class ChampFichier(tk.Frame):
    """Champ texte + bouton Parcourir."""

    def __init__(self, parent, valeur="", mode="open", types=None, **kw):
        bg = kw.pop("bg", PANEL)
        super().__init__(parent, bg=bg, **kw)
        self.mode  = mode
        self.types = types or [("Tous", "*.*")]
        self.var   = tk.StringVar(value=valeur)

        ttk.Entry(self, textvariable=self.var).pack(
            side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(self, text="…", width=3,
                   command=self._parcourir).pack(side=tk.LEFT, padx=(3, 0))

    def _parcourir(self):
        if self.mode == "open":
            chemin = filedialog.askopenfilename(filetypes=self.types)
        elif self.mode == "save":
            chemin = filedialog.asksaveasfilename(filetypes=self.types,
                                                   defaultextension=self.types[0][1].replace("*", ""))
        elif self.mode == "dir":
            chemin = filedialog.askdirectory()
        else:
            chemin = ""
        if chemin:
            self.var.set(chemin)

    def get(self) -> str:
        return self.var.get().strip()

    def set(self, valeur: str):
        self.var.set(valeur)


def _ligne(parent, label: str, widget, note: str = ""):
    """Affiche une ligne label + widget (+ note optionnelle)."""
    row = tk.Frame(parent, bg=PANEL)
    row.pack(fill=tk.X, pady=3)
    tk.Label(row, text=label, width=24, anchor="w",
             bg=PANEL, fg=TEXTE, font=("Segoe UI", 9)).pack(side=tk.LEFT)
    widget.pack(side=tk.LEFT, fill=tk.X, expand=True)
    if note:
        tk.Label(row, text=note, bg=PANEL, fg=GRIS,
                 font=("Segoe UI", 8)).pack(side=tk.LEFT, padx=(5, 0))
    return widget


def _titre(parent, texte: str, sous: str = ""):
    tk.Label(parent, text=texte, bg=PANEL, fg=TEXTE,
             font=("Segoe UI", 13, "bold")).pack(anchor="w", pady=(0, 4))
    if sous:
        tk.Label(parent, text=sous, bg=PANEL, fg=GRIS,
                 font=("Segoe UI", 9), justify="left").pack(anchor="w", pady=(0, 12))


# ── Lanceur de script ──────────────────────────────────────────────────────────

class LanceurScript:
    """Exécute un script Python en sous-processus et redirige la sortie."""

    def __init__(self, console: Console):
        self.console = console

    def lancer(self, cmd: list):
        def _run():
            self.console.ecrire(f"\n{'─'*60}\n", "cmd")
            self.console.ecrire("$ " + " ".join(cmd) + "\n", "cmd")
            self.console.ecrire(f"{'─'*60}\n\n", "cmd")
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    cwd=str(SCRIPTS_DIR),
                    bufsize=1,
                )
                for ligne in proc.stdout:
                    mots_erreur = ("erreur", "error", "traceback", "exception",
                                   "errno", "failed")
                    tag = "erreur" if any(m in ligne.lower() for m in mots_erreur) else "normal"
                    self.console.ecrire(ligne, tag)
                code = proc.wait()
                if code == 0:
                    self.console.ecrire(f"\n✓ Terminé (code {code})\n", "info")
                else:
                    self.console.ecrire(f"\n✗ Erreur (code {code})\n", "erreur")
            except FileNotFoundError:
                self.console.ecrire(
                    f"ERREUR : commande introuvable — {cmd[0]}\n", "erreur")
            except Exception as exc:
                self.console.ecrire(f"ERREUR : {exc}\n", "erreur")

        threading.Thread(target=_run, daemon=True).start()


# ── Onglets ────────────────────────────────────────────────────────────────────

class OngletCapture(tk.Frame):
    """1. Capture d'écran automatique."""

    def __init__(self, parent, lanceur: LanceurScript):
        super().__init__(parent, bg=PANEL, padx=16, pady=16)
        self.lanceur = lanceur

        _titre(self, "Capture d'écran automatique",
               "Prend une capture toutes les 10 secondes.\n"
               "Sortie : captures/capture_YYYYMMDD_HHMMSS.png")

        corps = tk.Frame(self, bg=PANEL)
        corps.pack(fill=tk.BOTH, expand=True)

        self.duree  = tk.IntVar(value=5)
        self.dossier = tk.StringVar(value="captures")
        self.delai  = tk.IntVar(value=3)
        self.ecran  = tk.IntVar(value=1)

        _ligne(corps, "Durée (minutes) :",
               ttk.Spinbox(corps, textvariable=self.duree,
                           from_=1, to=120, width=8))
        _ligne(corps, "Dossier de sortie :",
               ChampFichier(corps, valeur="captures", mode="dir", bg=PANEL))
        _ligne(corps, "Délai avant démarrage (s) :",
               ttk.Spinbox(corps, textvariable=self.delai,
                           from_=0, to=60, width=8))
        _ligne(corps, "Numéro d'écran :",
               ttk.Spinbox(corps, textvariable=self.ecran,
                           from_=1, to=4, width=8))

        self._champ_dossier = corps.winfo_children()[1]  # ChampFichier

        ttk.Button(self, text="▶  Lancer la capture",
                   command=self._lancer,
                   style="Accent.TButton").pack(anchor="w", pady=(16, 0))

    def _lancer(self):
        # Récupère le widget ChampFichier correctement
        dossier = "captures"
        for w in self.winfo_children():
            if isinstance(w, tk.Frame):
                for child in w.winfo_children():
                    if isinstance(child, tk.Frame):
                        for c in child.winfo_children():
                            if isinstance(c, ChampFichier):
                                dossier = c.get() or "captures"
                                break

        cmd = [
            sys.executable, "capture_ecran.py",
            "--duree",  str(self.duree.get()),
            "--dossier", dossier,
            "--delai",  str(self.delai.get()),
            "--ecran",  str(self.ecran.get()),
        ]
        self.lanceur.lancer(cmd)


class _OngletBase(tk.Frame):
    """Base commune : titre + corps + bouton Lancer."""

    def __init__(self, parent, lanceur: LanceurScript, titre: str, sous: str):
        super().__init__(parent, bg=PANEL, padx=16, pady=16)
        self.lanceur = lanceur
        _titre(self, titre, sous)
        self.corps = tk.Frame(self, bg=PANEL)
        self.corps.pack(fill=tk.BOTH, expand=True)

    def _ligne(self, label, widget, note=""):
        return _ligne(self.corps, label, widget, note)

    def _champ_fichier(self, valeur="", mode="open", types=None):
        return ChampFichier(self.corps, valeur=valeur, mode=mode,
                            types=types or [("CSV", "*.csv")], bg=PANEL)

    def _btn_lancer(self, texte: str):
        ttk.Button(self, text=f"▶  {texte}",
                   command=self._lancer,
                   style="Accent.TButton").pack(anchor="w", pady=(16, 0))

    def _lancer(self):
        raise NotImplementedError

    def _verif_input(self, champ: ChampFichier, nom: str = "CSV d'entrée") -> bool:
        if not champ.get():
            messagebox.showwarning(
                "Champ manquant",
                f"Veuillez renseigner : {nom}")
            return False
        return True


class OngletZones(_OngletBase):
    """2. Sélection de zones."""

    def __init__(self, parent, lanceur):
        super().__init__(parent, lanceur,
                         "Sélection de zones",
                         "Dessine des zones rectangulaires sur une image.\n"
                         "Sortie : zones_YYYYMMDD_HHMMSS.csv")

        self.champ_image = self._champ_fichier(
            mode="open",
            types=[("Images", "*.png *.jpg *.jpeg *.bmp *.tiff")])
        self._ligne("Image source :", self.champ_image,
                    note="(vide = capture d'écran auto)")

        self.champ_csv = self._champ_fichier(mode="save")
        self._ligne("CSV de sortie :", self.champ_csv,
                    note="(vide = zones_DATE.csv)")

        self._btn_lancer("Lancer la sélection")

    def _lancer(self):
        cmd = [sys.executable, "selection_zones.py"]
        if self.champ_image.get():
            cmd += ["--image", self.champ_image.get()]
        if self.champ_csv.get():
            cmd += ["--csv", self.champ_csv.get()]
        self.lanceur.lancer(cmd)


class OngletOCR(_OngletBase):
    """3. OCR zones."""

    def __init__(self, parent, lanceur):
        super().__init__(parent, lanceur,
                         "OCR sur zones",
                         "Extrait le texte des zones sur toutes les images d'un dossier.\n"
                         "Sortie : resultats_ocr_YYYYMMDD_HHMMSS.csv")

        self.champ_zones  = self._champ_fichier(valeur="zones.csv")
        self._ligne("Zones (CSV) :", self.champ_zones)

        self.champ_images = ChampFichier(self.corps, valeur="captures",
                                         mode="dir", bg=PANEL)
        self._ligne("Dossier images :", self.champ_images)

        self.champ_out = self._champ_fichier(mode="save")
        self._ligne("CSV de sortie :", self.champ_out,
                    note="(vide = resultats_ocr_DATE.csv)")

        self.engine = tk.StringVar(value="tesseract")
        self._ligne("Moteur OCR :",
                    ttk.Combobox(self.corps, textvariable=self.engine,
                                 values=["tesseract", "easyocr"],
                                 width=16, state="readonly"))

        self.preprocess = tk.StringVar(value="auto")
        self._ligne("Prétraitement :",
                    ttk.Combobox(self.corps, textvariable=self.preprocess,
                                 values=["auto", "neon", "aucun"],
                                 width=16, state="readonly"))

        self.debug = tk.BooleanVar(value=False)
        row = tk.Frame(self.corps, bg=PANEL)
        row.pack(fill=tk.X, pady=3)
        ttk.Checkbutton(row, text="Mode debug (sauvegarde les zones découpées)",
                        variable=self.debug).pack(side=tk.LEFT)

        self._btn_lancer("Lancer l'OCR")

    def _lancer(self):
        if not self._verif_input(self.champ_zones, "Zones (CSV)"):
            return
        cmd = [
            sys.executable, "ocr_zones.py",
            "--zones",      self.champ_zones.get(),
            "--images",     self.champ_images.get() or "captures",
            "--engine",     self.engine.get(),
            "--preprocess", self.preprocess.get(),
        ]
        if self.champ_out.get():
            cmd += ["--out", self.champ_out.get()]
        if self.debug.get():
            cmd.append("--debug")
        self.lanceur.lancer(cmd)


class OngletFiltrer(_OngletBase):
    """4. Filtrer OCR."""

    def __init__(self, parent, lanceur):
        super().__init__(parent, lanceur,
                         "Filtrer OCR — extraire les chiffres",
                         "Conserve uniquement les lignes avec des valeurs décimales.\n"
                         "Sortie : {nom_entrée}_chiffres.csv")

        self.champ_input = self._champ_fichier()
        self._ligne("CSV d'entrée :", self.champ_input)
        self.champ_input.var.trace_add("write", self._maj_sortie)

        self.champ_out = self._champ_fichier(mode="save")
        self._ligne("CSV de sortie :", self.champ_out,
                    note="(auto : _chiffres.csv)")

        self.champ_graph = self._champ_fichier(
            mode="save", types=[("PNG", "*.png")])
        self._ligne("Graphique (optionnel) :", self.champ_graph)

        self._btn_lancer("Filtrer")

    def _maj_sortie(self, *_):
        inp = self.champ_input.get()
        if inp and not self.champ_out.get():
            self.champ_out.set(Path(inp).stem + "_chiffres.csv")

    def _lancer(self):
        if not self._verif_input(self.champ_input):
            return
        cmd = [sys.executable, "filtrer_ocr.py",
               "--input", self.champ_input.get()]
        if self.champ_out.get():
            cmd += ["--out", self.champ_out.get()]
        if self.champ_graph.get():
            cmd += ["--graph", self.champ_graph.get()]
        self.lanceur.lancer(cmd)


class OngletDedup(_OngletBase):
    """5. Dédupliquer."""

    def __init__(self, parent, lanceur):
        super().__init__(parent, lanceur,
                         "Dédupliquer — supprimer doublons consécutifs",
                         "Supprime les valeurs identiques consécutives.\n"
                         "Ex : 1.2, 1.2, 1.2, 1.5  →  1.2, 1.5\n"
                         "Sortie : {nom_entrée}_dedup.csv")

        self.champ_input = self._champ_fichier()
        self._ligne("CSV d'entrée :", self.champ_input)
        self.champ_input.var.trace_add("write", self._maj_sortie)

        self.champ_out = self._champ_fichier(mode="save")
        self._ligne("CSV de sortie :", self.champ_out,
                    note="(auto : _dedup.csv)")

        self._btn_lancer("Dédupliquer")

    def _maj_sortie(self, *_):
        inp = self.champ_input.get()
        if inp and not self.champ_out.get():
            self.champ_out.set(Path(inp).stem + "_dedup.csv")

    def _lancer(self):
        if not self._verif_input(self.champ_input):
            return
        cmd = [sys.executable, "dedupliquer_ocr.py",
               "--input", self.champ_input.get()]
        if self.champ_out.get():
            cmd += ["--out", self.champ_out.get()]
        self.lanceur.lancer(cmd)


class OngletPatterns(_OngletBase):
    """6. Analyser patterns."""

    def __init__(self, parent, lanceur):
        super().__init__(parent, lanceur,
                         "Analyser patterns",
                         "Tests statistiques : autocorrélation, ADF, runs, régression linéaire.\n"
                         "Entrée conseillée : *_chiffres.csv ou *_dedup.csv")

        self.champ_input = self._champ_fichier()
        self._ligne("CSV d'entrée :", self.champ_input)

        self.alpha = tk.DoubleVar(value=0.05)
        self._ligne("Seuil alpha :",
                    ttk.Spinbox(self.corps, textvariable=self.alpha,
                                from_=0.01, to=0.20, increment=0.01, width=8))

        self.champ_graph = self._champ_fichier(
            mode="save", types=[("PNG", "*.png")])
        self._ligne("Graphique (optionnel) :", self.champ_graph)

        self._btn_lancer("Analyser")

    def _lancer(self):
        if not self._verif_input(self.champ_input):
            return
        cmd = [sys.executable, "analyser_patterns.py",
               "--input", self.champ_input.get(),
               "--alpha", str(round(self.alpha.get(), 3))]
        if self.champ_graph.get():
            cmd += ["--graph", self.champ_graph.get()]
        self.lanceur.lancer(cmd)


class OngletComprendre(_OngletBase):
    """7. Comprendre patterns (avancé)."""

    def __init__(self, parent, lanceur):
        super().__init__(parent, lanceur,
                         "Comprendre patterns (avancé)",
                         "FFT, décomposition STL, ruptures, clustering, corrélations croisées.\n"
                         "Entrée conseillée : *_chiffres.csv ou *_dedup.csv")

        self.champ_input = self._champ_fichier()
        self._ligne("CSV d'entrée :", self.champ_input)

        self.saison = tk.IntVar(value=7)
        self._ligne("Période saisonnière :",
                    ttk.Spinbox(self.corps, textvariable=self.saison,
                                from_=2, to=200, width=8))

        self.clusters = tk.IntVar(value=3)
        self._ligne("Nombre de clusters :",
                    ttk.Spinbox(self.corps, textvariable=self.clusters,
                                from_=2, to=10, width=8))

        self.champ_out = self._champ_fichier(
            mode="save", types=[("PNG", "*.png")])
        self._ligne("Graphique (optionnel) :", self.champ_out)

        self._btn_lancer("Analyser")

    def _lancer(self):
        if not self._verif_input(self.champ_input):
            return
        cmd = [sys.executable, "comprendre_patterns.py",
               "--input",    self.champ_input.get(),
               "--saison",   str(self.saison.get()),
               "--clusters", str(self.clusters.get())]
        if self.champ_out.get():
            cmd += ["--out", self.champ_out.get()]
        self.lanceur.lancer(cmd)


class OngletCycles(_OngletBase):
    """8. Analyser cycles."""

    def __init__(self, parent, lanceur):
        super().__init__(parent, lanceur,
                         "Analyser cycles",
                         "Détecte les resets et calcule la durée de chaque cycle.\n"
                         "Entrée conseillée : *_dedup.csv ou *_chiffres.csv")

        self.champ_input = self._champ_fichier()
        self._ligne("CSV d'entrée :", self.champ_input)

        self.seuil_reset = tk.DoubleVar(value=1.2)
        self._ligne("Seuil reset (≤) :",
                    ttk.Spinbox(self.corps, textvariable=self.seuil_reset,
                                from_=0.1, to=10.0, increment=0.1, width=8))

        self.seuil_haut = tk.DoubleVar(value=2.0)
        self._ligne("Seuil pic (≥) :",
                    ttk.Spinbox(self.corps, textvariable=self.seuil_haut,
                                from_=0.1, to=100.0, increment=0.1, width=8))

        self.detail = tk.BooleanVar(value=False)
        row = tk.Frame(self.corps, bg=PANEL)
        row.pack(fill=tk.X, pady=3)
        ttk.Checkbutton(row, text="Afficher le détail de chaque cycle",
                        variable=self.detail).pack(side=tk.LEFT)

        self._btn_lancer("Analyser les cycles")

    def _lancer(self):
        if not self._verif_input(self.champ_input):
            return
        cmd = [sys.executable, "analyser_cycles.py",
               "--input",       self.champ_input.get(),
               "--seuil-reset", str(round(self.seuil_reset.get(), 2)),
               "--seuil-haut",  str(round(self.seuil_haut.get(), 2))]
        if self.detail.get():
            cmd.append("--detail")
        self.lanceur.lancer(cmd)


class OngletPredire(_OngletBase):
    """9. Prédire seuil."""

    def __init__(self, parent, lanceur):
        super().__init__(parent, lanceur,
                         "Prédire seuil",
                         "Évalue si les valeurs sous un seuil sont prévisibles.\n"
                         "Entrée conseillée : *_chiffres.csv ou *_dedup.csv")

        self.champ_input = self._champ_fichier()
        self._ligne("CSV d'entrée :", self.champ_input)

        self.seuil = tk.DoubleVar(value=1.2)
        self._ligne("Seuil :",
                    ttk.Spinbox(self.corps, textvariable=self.seuil,
                                from_=0.1, to=100.0, increment=0.1, width=8))

        self.lags = tk.IntVar(value=10)
        self._ligne("Nombre de lags :",
                    ttk.Spinbox(self.corps, textvariable=self.lags,
                                from_=1, to=50, width=8))

        self.champ_out = self._champ_fichier(
            mode="save", types=[("PNG", "*.png")])
        self._ligne("Graphique (optionnel) :", self.champ_out)

        self._btn_lancer("Prédire")

    def _lancer(self):
        if not self._verif_input(self.champ_input):
            return
        cmd = [sys.executable, "predire_seuil.py",
               "--input", self.champ_input.get(),
               "--seuil", str(round(self.seuil.get(), 2)),
               "--lags",  str(self.lags.get())]
        if self.champ_out.get():
            cmd += ["--out", self.champ_out.get()]
        self.lanceur.lancer(cmd)


# ── Application principale ─────────────────────────────────────────────────────

class Application(tk.Tk):

    ONGLETS = [
        ("1. Capture",     OngletCapture),
        ("2. Zones",       OngletZones),
        ("3. OCR",         OngletOCR),
        ("4. Filtrer",     OngletFiltrer),
        ("5. Dédupliquer", OngletDedup),
        ("6. Patterns",    OngletPatterns),
        ("7. Comprendre",  OngletComprendre),
        ("8. Cycles",      OngletCycles),
        ("9. Prédire",     OngletPredire),
    ]

    def __init__(self):
        super().__init__()
        self.title("Outils Diététique — Analyse OCR")
        self.geometry("960x720")
        self.minsize(800, 580)
        self.configure(bg=FOND)
        self._styles()
        self._ui()

    # ── Styles ttk ────────────────────────────────────────────────────────────

    def _styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")

        s.configure("TNotebook",
                    background=FOND, borderwidth=0, tabmargins=[0, 0, 0, 0])
        s.configure("TNotebook.Tab",
                    background=FOND, foreground=GRIS,
                    padding=[14, 6], font=("Segoe UI", 9))
        s.map("TNotebook.Tab",
              background=[("selected", PANEL)],
              foreground=[("selected", TEXTE)])

        s.configure("TButton",
                    background=PANEL, foreground=TEXTE,
                    padding=[8, 4], font=("Segoe UI", 9))
        s.map("TButton", background=[("active", "#3a3a5e")])

        s.configure("Accent.TButton",
                    background=ACCENT, foreground="white",
                    padding=[14, 7], font=("Segoe UI", 10, "bold"))
        s.map("Accent.TButton",
              background=[("active", "#6d28d9"), ("pressed", "#5b21b6")])

        s.configure("TEntry",
                    fieldbackground=FOND_INPUT, foreground=TEXTE,
                    insertcolor=TEXTE, borderwidth=1)
        s.configure("TCombobox",
                    fieldbackground=FOND_INPUT, foreground=TEXTE,
                    selectbackground=ACCENT)
        s.configure("TSpinbox",
                    fieldbackground=FOND_INPUT, foreground=TEXTE)
        s.configure("TCheckbutton",
                    background=PANEL, foreground=TEXTE)

    # ── Construction ──────────────────────────────────────────────────────────

    def _ui(self):
        # ── En-tête
        header = tk.Frame(self, bg=ACCENT, padx=20, pady=10)
        header.pack(fill=tk.X)
        tk.Label(header,
                 text="Outils Diététique — Analyse OCR",
                 bg=ACCENT, fg="white",
                 font=("Segoe UI", 14, "bold")).pack(side=tk.LEFT)
        tk.Label(header,
                 text="Capture → Zones → OCR → Filtrer → Dédupliquer → Analyser",
                 bg=ACCENT, fg="#d8b4fe",
                 font=("Segoe UI", 9)).pack(side=tk.RIGHT)

        # ── Zone principale (notebook + console séparés par un sash)
        paned = tk.PanedWindow(self, orient=tk.VERTICAL,
                               bg=FOND, sashwidth=5, sashrelief="flat")
        paned.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        notebook = ttk.Notebook(paned)
        console_frame = tk.Frame(paned, bg=FOND)

        paned.add(notebook,      minsize=360, stretch="always")
        paned.add(console_frame, minsize=140, stretch="never")

        # ── Console
        barre = tk.Frame(console_frame, bg=FOND)
        barre.pack(fill=tk.X, padx=4, pady=(4, 0))
        tk.Label(barre, text="Console de sortie",
                 bg=FOND, fg=GRIS,
                 font=("Segoe UI", 9, "bold")).pack(side=tk.LEFT)
        ttk.Button(barre, text="Effacer",
                   command=lambda: self.console.effacer()).pack(side=tk.RIGHT)

        self.console = Console(console_frame, height=10)
        self.console.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        lanceur = LanceurScript(self.console)

        # ── Onglets
        for titre, Classe in self.ONGLETS:
            notebook.add(Classe(notebook, lanceur), text=titre)

        # ── Message d'accueil
        self.console.ecrire("Bienvenue dans les outils Diététique.\n", "info")
        self.console.ecrire(
            "Sélectionnez un onglet, configurez les paramètres, "
            "puis cliquez sur ▶ Lancer.\n", "normal")
        self.console.ecrire(
            f"Répertoire de travail : {SCRIPTS_DIR}\n\n", "cmd")


# ── Point d'entrée ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = Application()
    app.mainloop()
