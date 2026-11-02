"""Optional real Qt Multimedia check; all device output is muted."""
import os
from pathlib import Path
import random
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PyQt5.QtMultimedia import QMediaPlayer
from PyQt5.QtWidgets import QApplication
from eurhythmics.music import PATTERNS, Meter, generate
from eurhythmics.playback import Playback


def main():
    app = QApplication([])
    audio = Playback()
    audio.player.setVolume(0)
    audio.clicks.setVolume(0)
    messages = []
    audio.message.connect(messages.append)

    def wait_for(predicate, timeout=12):
        deadline = time.monotonic() + timeout
        while not predicate() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        assert predicate(), messages

    try:
        ex = generate(PATTERNS, Meter(2, 4), 2, 240, True, True, random.Random(15))
        audio.play(ex, count_in=False, backing=True)
        wait_for(lambda: audio.player.state() == QMediaPlayer.PlayingState)
        wait_for(lambda: audio.player.mediaStatus() == QMediaPlayer.EndOfMedia)
        assert len(audio.cache) == 1
        audio.play(ex, count_in=False, backing=True)
        wait_for(lambda: audio.player.state() == QMediaPlayer.PlayingState)
        assert len(audio.cache) == 1
        audio.stop()
        audio.start_metronome(Meter(6, 8), 120)
        wait_for(lambda: audio.clicks.isPlaying())
        audio.stop_metronome()
        assert not audio.clicks.isPlaying()
        # Cancelling a pending render must not cause a delayed playback.
        pending = generate(PATTERNS, Meter(4, 4), 5, 120, True, True, random.Random(98))
        audio.play(pending)
        audio.stop()
        wait_for(lambda: not audio.jobs)
        assert audio.player.state() != QMediaPlayer.PlayingState
        audio.clear_exercise_cache()
        assert not audio.cache
        assert not any("error" in message.lower() for message in messages), messages
        print("Muted PyQt5 playback checks passed: render, decode, replay, metronome, cancellation.")
    finally:
        audio.close()


if __name__ == "__main__":
    main()
