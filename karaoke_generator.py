#!/usr/bin/env python3
"""
🎤 Karaoke Video Generator
==========================
Transforme une chanson audio en vidéo karaoké avec :
- Transcription automatique des paroles (OpenAI Whisper)
- Support des fichiers LRC (paroles synchronisées)
- Surlignage mot par mot
- Suppression optionnelle de la voix (Demucs)
- Export MP4

Compatible Kaggle :
  - Fichiers audio attendus dans /kaggle/input/
  - Fichiers de sortie générés dans /kaggle/working/

Installation des dépendances :
  pip install openai-whisper moviepy pillow numpy demucs torch torchaudio

Usage local :
  python karaoke_generator.py ma_chanson.mp3
  python karaoke_generator.py ma_chanson.mp3 --lrc paroles.lrc
  python karaoke_generator.py ma_chanson.mp3 --no-vocals
  python karaoke_generator.py ma_chanson.mp3 --lrc paroles.lrc --no-vocals --output video_karaoke.mp4

Usage Kaggle (notebook) :
  !python karaoke_generator.py /kaggle/input/<dataset>/<fichier>.mp3
  # La sortie sera automatiquement placée dans /kaggle/working/
"""

import argparse
import os
import re
import sys
import textwrap
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

# ─────────────────────────────────────────────
# Détection de l'environnement Kaggle
# ─────────────────────────────────────────────

def is_kaggle() -> bool:
    """Détecte si le script tourne dans un environnement Kaggle."""
    return os.path.exists("/kaggle/input") and os.path.exists("/kaggle/working")

KAGGLE_INPUT_DIR = Path("/kaggle/input")
KAGGLE_OUTPUT_DIR = Path("/kaggle/working")


# ─────────────────────────────────────────────
# Structures de données
# ─────────────────────────────────────────────

@dataclass
class Word:
    text: str
    start: float
    end: float

@dataclass
class Line:
    words: list[Word] = field(default_factory=list)
    start: float = 0.0
    end: float = 0.0

    @property
    def text(self):
        return " ".join(w.text for w in self.words)


# ─────────────────────────────────────────────
# Transcription Whisper
# ─────────────────────────────────────────────

def transcribe_with_whisper(audio_path: str, model_size: str = "base") -> list[Line]:
    """Transcrit l'audio avec Whisper et retourne les lignes avec horodatage mot par mot."""
    print(f"⏳ Transcription avec Whisper (modèle '{model_size}')...")
    try:
        import whisper
    except ImportError:
        sys.exit("❌ Whisper non installé. Lancez : pip install openai-whisper")

    model = whisper.load_model(model_size)
    result = model.transcribe(audio_path, word_timestamps=True)

    lines = []
    for segment in result["segments"]:
        words_data = segment.get("words", [])
        if not words_data:
            # Pas de timestamps mot par mot : on crée un seul "mot" pour le segment
            words_data = [{"word": segment["text"].strip(),
                           "start": segment["start"],
                           "end": segment["end"]}]

        words = [Word(text=w["word"].strip(), start=w["start"], end=w["end"])
                 for w in words_data if w["word"].strip()]

        if words:
            line = Line(words=words, start=words[0].start, end=words[-1].end)
            lines.append(line)

    print(f"✅ {len(lines)} lignes transcrites.")
    return lines


# ─────────────────────────────────────────────
# Parsing LRC
# ─────────────────────────────────────────────

def parse_lrc(lrc_path: str) -> list[Line]:
    """Parse un fichier LRC et retourne les lignes avec horodatage."""
    print(f"📄 Lecture du fichier LRC : {lrc_path}")
    lines = []
    pattern = re.compile(r"\[(\d+):(\d+\.\d+)\](.*)")

    with open(lrc_path, encoding="utf-8") as f:
        raw_lines = f.readlines()

    timed = []
    for raw in raw_lines:
        m = pattern.match(raw.strip())
        if m:
            minutes, seconds, text = int(m.group(1)), float(m.group(2)), m.group(3).strip()
            if text:
                timed.append((minutes * 60 + seconds, text))

    for i, (start, text) in enumerate(timed):
        end = timed[i + 1][0] if i + 1 < len(timed) else start + 5.0
        # Découpe en mots avec horodatage linéaire approximatif
        tokens = text.split()
        if not tokens:
            continue
        duration = (end - start) / len(tokens)
        words = [Word(text=tok, start=start + j * duration, end=start + (j + 1) * duration)
                 for j, tok in enumerate(tokens)]
        lines.append(Line(words=words, start=start, end=end))

    print(f"✅ {len(lines)} lignes chargées depuis le LRC.")
    return lines


# ─────────────────────────────────────────────
# Suppression de la voix (Demucs)
# ─────────────────────────────────────────────

def remove_vocals(audio_path: str, output_dir: Path) -> str:
    """Sépare les instruments de la voix avec Demucs. Retourne le chemin de l'instrumental."""
    print("🎛️  Suppression de la voix avec Demucs (peut prendre quelques minutes)...")
    try:
        import subprocess
        result = subprocess.run(
            ["python", "-m", "demucs", "--two-stems=vocals",
             "--out", str(output_dir), audio_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            print(f"⚠️  Demucs a retourné une erreur :\n{result.stderr}")
            print("→ La chanson originale sera utilisée à la place.")
            return audio_path
    except FileNotFoundError:
        print("⚠️  Demucs non trouvé. Installez-le : pip install demucs")
        print("→ La chanson originale sera utilisée.")
        return audio_path

    # Demucs place les fichiers dans <output_dir>/htdemucs/<nom_fichier>/
    stem = Path(audio_path).stem
    instrumental = output_dir / "htdemucs" / stem / "no_vocals.wav"
    if instrumental.exists():
        print(f"✅ Instrumental extrait : {instrumental}")
        return str(instrumental)
    else:
        print("⚠️  Fichier instrumental introuvable. Utilisation de l'audio original.")
        return audio_path


# ─────────────────────────────────────────────
# Rendu vidéo
# ─────────────────────────────────────────────

def wrap_lines(lines: list[Line], max_chars: int = 50) -> list[Line]:
    """Coupe les longues lignes pour qu'elles tiennent à l'écran."""
    result = []
    for line in lines:
        if len(line.text) <= max_chars:
            result.append(line)
        else:
            # Regroupe les mots en sous-lignes
            current_words = []
            for word in line.words:
                current_words.append(word)
                if len(" ".join(w.text for w in current_words)) > max_chars:
                    if len(current_words) > 1:
                        sub = current_words[:-1]
                        result.append(Line(words=sub, start=sub[0].start, end=sub[-1].end))
                        current_words = [word]
            if current_words:
                result.append(Line(words=current_words,
                                   start=current_words[0].start,
                                   end=current_words[-1].end))
    return result


def make_frame(line: Optional[Line], t: float,
               width: int, height: int,
               bg_color=(10, 10, 40),
               text_color=(200, 200, 255),
               highlight_color=(255, 220, 0),
               font_size: int = 60) -> "np.ndarray":
    """Génère une frame PIL/numpy pour l'instant t."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (width, height), bg_color)
    draw = ImageDraw.Draw(img)

    # Fond dégradé subtil
    for y in range(height):
        factor = y / height
        r = int(bg_color[0] + (30 - bg_color[0]) * factor)
        g = int(bg_color[1] + (10 - bg_color[1]) * factor)
        b = int(bg_color[2] + (60 - bg_color[2]) * factor)
        draw.line([(0, y), (width, y)], fill=(r, g, b))

    if line is None:
        return np.array(img)

    # Chargement de la police
    font = None
    for font_path in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Linux standard
        "/kaggle/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",  # Kaggle fallback
        "/usr/local/share/fonts/DejaVuSans-Bold.ttf",
    ]:
        try:
            font = ImageFont.truetype(font_path, font_size)
            break
        except Exception:
            continue
    if font is None:
        font = ImageFont.load_default()

    # Calcul de la largeur totale pour centrer
    words_render = []
    x_cursor = 0
    space_w = draw.textlength(" ", font=font)

    for i, word in enumerate(line.words):
        w = draw.textlength(word.text, font=font)
        highlighted = word.start <= t < word.end
        words_render.append((word.text, w, highlighted))
        x_cursor += w + (space_w if i < len(line.words) - 1 else 0)

    total_width = x_cursor
    x = (width - total_width) / 2
    y = (height - font_size) / 2

    # Ombre portée
    shadow_offset = 3
    x_draw = x
    for i, (text, w, highlighted) in enumerate(words_render):
        draw.text((x_draw + shadow_offset, y + shadow_offset), text,
                  font=font, fill=(0, 0, 0, 128))
        color = highlight_color if highlighted else text_color
        draw.text((x_draw, y), text, font=font, fill=color)
        x_draw += w + space_w

    # Barre de progression
    bar_h = 6
    bar_y = height - 30
    progress = (t - line.start) / max(line.end - line.start, 0.001)
    draw.rectangle([(0, bar_y), (width, bar_y + bar_h)], fill=(40, 40, 80))
    draw.rectangle([(0, bar_y), (int(width * progress), bar_y + bar_h)],
                   fill=highlight_color)

    return np.array(img)


def render_video(lines: list[Line], audio_path: str,
                 output_path: str, width: int = 1280, height: int = 720,
                 fps: int = 24, font_size: int = 60):
    """Génère la vidéo MP4 karaoké."""
    print("🎬 Rendu de la vidéo...")
    try:
        import numpy as np
        from moviepy.editor import AudioFileClip, VideoClip
    except ImportError:
        sys.exit("❌ moviepy ou numpy non installé. Lancez : pip install moviepy numpy")

    audio = AudioFileClip(audio_path)
    duration = audio.duration

    # Fichier audio temporaire dans le répertoire de sortie (compatible Kaggle)
    output_dir = Path(output_path).parent
    temp_audio = str(output_dir / "temp_audio.m4a")

    # Index rapide : pour chaque instant t, quelle ligne afficher ?
    def get_line_at(t: float) -> Optional[Line]:
        for line in lines:
            if line.start <= t < line.end:
                return line
        # Afficher la prochaine ligne jusqu'à 2s avant qu'elle commence
        for line in lines:
            if t < line.start and line.start - t <= 2.0:
                return line
        return None

    def make_frame_at(t):
        line = get_line_at(t)
        return make_frame(line, t, width, height, font_size=font_size)

    video = VideoClip(make_frame_at, duration=duration)
    video = video.set_audio(audio)

    print(f"💾 Export vers {output_path}...")
    video.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        temp_audiofile=temp_audio,
        remove_temp=True,
        logger="bar"
    )
    print(f"✅ Vidéo générée : {output_path}")


# ─────────────────────────────────────────────
# Point d'entrée
# ─────────────────────────────────────────────

def main():
    on_kaggle = is_kaggle()
    if on_kaggle:
        print("🖥️  Environnement Kaggle détecté.")
        print(f"   Entrée  : {KAGGLE_INPUT_DIR}")
        print(f"   Sortie  : {KAGGLE_OUTPUT_DIR}")

    parser = argparse.ArgumentParser(
        description="🎤 Génère une vidéo karaoké à partir d'une chanson.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""
        Exemples locaux :
          python karaoke_generator.py chanson.mp3
          python karaoke_generator.py chanson.mp3 --lrc paroles.lrc
          python karaoke_generator.py chanson.mp3 --no-vocals --model medium
          python karaoke_generator.py chanson.mp3 --output karaoke.mp4 --width 1920 --height 1080

        Exemples Kaggle (notebook) :
          !python karaoke_generator.py /kaggle/input/<dataset>/chanson.mp3
          !python karaoke_generator.py /kaggle/input/<dataset>/chanson.mp3 --lrc /kaggle/input/<dataset>/paroles.lrc
        """)
    )
    parser.add_argument("audio",
                        help="Fichier audio d'entrée (mp3, wav, flac, m4a...). "
                             "Sur Kaggle : /kaggle/input/<dataset>/<fichier>")
    parser.add_argument("--lrc",
                        help="Fichier LRC de paroles synchronisées (optionnel)")
    parser.add_argument("--no-vocals", action="store_true",
                        help="Supprimer la voix avec Demucs (karaoké instrumental)")
    parser.add_argument("--model", default="base",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Modèle Whisper (défaut: base). 'medium' ou 'large' = meilleure précision")
    parser.add_argument("--output",
                        help="Fichier de sortie MP4. "
                             "Défaut local : <chanson>_karaoke.mp4 ; "
                             "Défaut Kaggle : /kaggle/working/<chanson>_karaoke.mp4")
    parser.add_argument("--width", type=int, default=1280, help="Largeur vidéo (défaut: 1280)")
    parser.add_argument("--height", type=int, default=720, help="Hauteur vidéo (défaut: 720)")
    parser.add_argument("--fps", type=int, default=24, help="Images par seconde (défaut: 24)")
    parser.add_argument("--font-size", type=int, default=60, help="Taille de police (défaut: 60)")
    args, _ = parser.parse_known_args()

    audio_path = args.audio
    if not os.path.exists(audio_path):
        sys.exit(f"❌ Fichier audio introuvable : {audio_path}")

    # 1. Chargement des paroles
    if args.lrc:
        if not os.path.exists(args.lrc):
            sys.exit(f"❌ Fichier LRC introuvable : {args.lrc}")
        lines = parse_lrc(args.lrc)
    else:
        lines = transcribe_with_whisper(audio_path, model_size=args.model)

    if not lines:
        sys.exit("❌ Aucune ligne de paroles trouvée.")

    lines = wrap_lines(lines)

    # 2. Répertoire de sortie
    if on_kaggle:
        out_dir = KAGGLE_OUTPUT_DIR
    else:
        out_dir = Path(audio_path).parent

    # 3. Suppression de la voix
    if args.no_vocals:
        audio_path = remove_vocals(audio_path, out_dir)

    # 4. Nom de sortie
    if args.output:
        output_path = args.output
    else:
        stem = Path(args.audio).stem
        output_path = str(out_dir / f"{stem}_karaoke.mp4")

    # 5. Rendu vidéo
    render_video(
        lines=lines,
        audio_path=audio_path,
        output_path=output_path,
        width=args.width,
        height=args.height,
        fps=args.fps,
        font_size=args.font_size
    )

    print("\n🎉 Terminé ! Votre vidéo karaoké est prête :")
    print(f"   📁 {os.path.abspath(output_path)}")
    if on_kaggle:
        print("   ℹ️  Retrouvez le fichier dans l'onglet 'Output' de votre notebook Kaggle.")


if __name__ == "__main__":
    main()
