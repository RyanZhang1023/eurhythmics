"""Optional offscreen PyQt5 smoke check, run explicitly, not in unittest discover."""
import os
from pathlib import Path
import random
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtGui import QFontDatabase
from eurhythmics.app import MainWindow, STYLE
from eurhythmics.music import KEYS, PATTERNS, Meter, generate


def main():
    app = QApplication.instance() or QApplication([])
    # Windows' offscreen plugin does not always enumerate system fonts.
    if sys.platform == "win32":
        font_dir = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for name in ("segoeui.ttf", "segoeuib.ttf", "seguisym.ttf"):
            QFontDatabase.addApplicationFont(str(font_dir / name))
    print("Available font families:", len(QFontDatabase().families()))
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    played = []
    # Exercise real controls and real painting, without using the audio device.
    window.audio.play = lambda *args, **kwargs: played.append((args, kwargs))
    window.audio.start_metronome = lambda meter, bpm: None
    app.processEvents()
    output = Path(__file__).resolve().parents[1] / "test-output"
    output.mkdir(exist_ok=True)
    window.grab().save(str(output / "setup.png"))
    window.start_session()
    app.processEvents()
    assert window.stack.currentIndex() == 1
    assert not window.score.hidden_answer
    assert window.exercise.bars == 4
    window.play_button.click()
    assert len(played) == 1
    window.live_tempo.setValue(125)
    assert window.exercise.bpm == 125
    window.next_button.click()
    assert window.question == 2
    app.processEvents()
    window.grab().save(str(output / "sight-reading.png"))
    window.exit_session()
    assert window.stack.currentIndex() == 0
    window.mode.setCurrentIndex(1)
    window.start_session()
    app.processEvents()
    assert window.score.hidden_answer
    assert window.low.value() <= window.exercise.bpm <= window.high.value()
    question = window.exercise
    window.play_button.click()
    assert window.exercise is question
    window.grab().save(str(output / "dictation-hidden.png"))
    window.reveal_button.click()
    assert not window.score.hidden_answer
    assert not window.reveal_button.isEnabled()
    app.processEvents()
    window.grab().save(str(output / "dictation-revealed.png"))
    window.next_button.click()
    app.processEvents()
    assert window.score.hidden_answer
    assert window.question == 2
    # Dense notation, all key signatures, cross-system ties, and resizing.
    for index, key in enumerate(KEYS):
        from dataclasses import replace
        ex = generate(PATTERNS, Meter(4, 4), 8, 100, True, True, random.Random(index))
        pitches = key.pitches()
        # Keep every note pitch representable in the requested test signature.
        ex = replace(ex, key=key, notes=tuple(replace(n, midi=pitches[4][0], diatonic=pitches[4][1]) for n in ex.notes))
        window.score.set_exercise(ex)
        app.processEvents()
        window.score.grab().save(str(output / f"key-{index:02}.png"))
    for pattern in PATTERNS:
        ex = generate([pattern], Meter(4, 4), 4, 80, True, rng=random.Random(5))
        window.score.set_exercise(ex)
        app.processEvents()
        window.score.grab().save(str(output / f"pattern-{pattern.id}.png"))
    for width in (850, 1200, 1600):
        window.resize(width, 800)
        app.processEvents()
        window.grab().save(str(output / f"width-{width}.png"))
    window.exit_session()
    window.close()
    print(f"PyQt5 interface checks passed. Previews: {output}")


if __name__ == "__main__":
    main()
