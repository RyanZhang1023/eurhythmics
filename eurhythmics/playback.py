"""PyQt5 audio service. Synthesis runs off the interface thread."""
from pathlib import Path
import tempfile
import uuid

from PyQt5.QtCore import QObject, QRunnable, QThreadPool, QUrl, pyqtSignal
from PyQt5.QtMultimedia import QMediaContent, QMediaPlayer, QSoundEffect

from .audio import metronome_samples, synthesize, write_wav


class RenderSignals(QObject):
    finished = pyqtSignal(str, int)
    failed = pyqtSignal(str, int)


class RenderJob(QRunnable):
    def __init__(self, exercise, path, serial, count_in, backing):
        super().__init__()
        self.exercise, self.path, self.serial = exercise, path, serial
        self.count_in, self.backing = count_in, backing
        self.signals = RenderSignals()

    def run(self):
        try:
            synthesize(self.exercise, self.path, self.count_in, self.backing)
            self.signals.finished.emit(str(self.path), self.serial)
        except Exception as error:
            self.signals.failed.emit(str(error), self.serial)


class Playback(QObject):
    message = pyqtSignal(str)
    busy_changed = pyqtSignal(bool)
    metronome_changed = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.directory = tempfile.TemporaryDirectory(prefix="eurhythmics-")
        self.player = QMediaPlayer(self)
        self.player.setVolume(85)
        self.player.error.connect(lambda *_: self.message.emit("Audio error: " + self.player.errorString()))
        self.player.mediaStatusChanged.connect(self.media_status)
        self.clicks = QSoundEffect(self)
        self.clicks.setVolume(.65)
        self.clicks.setLoopCount(QSoundEffect.Infinite)
        self.clicks.statusChanged.connect(self.click_status)
        self.metronome_on = False
        self.serial = 0
        self.jobs = {}
        self.cache = {}
        self.metro_cache = {}

    def new_path(self):
        return Path(self.directory.name) / (uuid.uuid4().hex + ".wav")

    def media_status(self, status):
        if status == QMediaPlayer.EndOfMedia:
            self.message.emit("Playback complete.")

    def click_status(self):
        if self.clicks.status() == QSoundEffect.Ready and self.metronome_on:
            self.clicks.play()
        elif self.clicks.status() == QSoundEffect.Error:
            self.stop_metronome()
            self.message.emit("Metronome audio could not be opened. Check your audio output device.")

    def play(self, exercise, count_in=True, backing=False):
        self.stop()
        self.serial += 1
        serial = self.serial
        token = (exercise, count_in, backing)
        if token in self.cache:
            self.ready(self.cache[token], serial)
            return
        self.busy_changed.emit(True)
        self.message.emit("Preparing audio…")
        job = RenderJob(exercise, self.new_path(), serial, count_in, backing)
        self.jobs[serial] = job

        def finished(path, job_serial):
            self.jobs.pop(job_serial, None)
            if job_serial != self.serial:
                Path(path).unlink(missing_ok=True)
                return
            self.cache[token] = path
            self.ready(path, job_serial)

        job.signals.finished.connect(finished)
        job.signals.failed.connect(self.failed)
        QThreadPool.globalInstance().start(job)

    def ready(self, path, serial):
        if serial != self.serial:
            return
        self.busy_changed.emit(False)
        self.player.setMedia(QMediaContent(QUrl.fromLocalFile(path)))
        self.player.play()
        self.message.emit("Playing…")

    def failed(self, error, serial):
        self.jobs.pop(serial, None)
        if serial == self.serial:
            self.busy_changed.emit(False)
            self.message.emit("Could not create audio: " + error)

    def start_metronome(self, meter, bpm):
        self.stop()
        token = (meter, bpm)
        if token not in self.metro_cache:
            path = self.new_path()
            write_wav(path, metronome_samples(meter, bpm))
            self.metro_cache[token] = str(path)
        self.metronome_on = True
        self.metronome_changed.emit(True)
        source = QUrl.fromLocalFile(self.metro_cache[token])
        self.clicks.setSource(source)
        if self.clicks.status() == QSoundEffect.Ready:
            self.clicks.play()
        self.message.emit(f"Metronome · quarter note = {bpm}")

    def stop_metronome(self):
        self.metronome_on = False
        self.clicks.stop()
        self.metronome_changed.emit(False)

    def stop(self):
        self.serial += 1  # Ignore audio that finishes rendering after stop/next/exit.
        self.player.stop()
        self.stop_metronome()
        self.busy_changed.emit(False)

    def clear_exercise_cache(self):
        # Release the current file before removing older exercise audio on Windows.
        self.stop()
        self.player.setMedia(QMediaContent())
        for path in self.cache.values():
            try:
                Path(path).unlink(missing_ok=True)
            except OSError:
                pass
        self.cache.clear()

    def close(self):
        self.stop()
        QThreadPool.globalInstance().waitForDone()
        self.player.setMedia(QMediaContent())
        self.clicks.setSource(QUrl())
        self.directory.cleanup()
