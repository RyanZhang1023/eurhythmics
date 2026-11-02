from dataclasses import replace
import random
import sys

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QGridLayout,
    QGroupBox, QHBoxLayout, QLabel, QMainWindow, QMessageBox, QPushButton,
    QScrollArea, QSpinBox, QStackedWidget, QVBoxLayout, QWidget,
)

from .music import PATTERNS, Meter, fill_options, generate
from .notation import RhythmPreview, ScoreWidget
from .playback import Playback


STYLE = """
QMainWindow, QWidget#setup, QWidget#practice { background: #edf3f3; }
QWidget { color: #182b35; font-family: 'Segoe UI'; font-size: 10pt; }
QLabel#title { font-size: 26pt; font-weight: 700; }
QLabel#subtitle { color: #5d717b; font-size: 11pt; }
QLabel#eyebrow { color: #007d78; font-size: 10pt; font-weight: 700; }
QGroupBox { background: white; border: 1px solid #d3e0e2; border-radius: 10px;
            font-weight: 600; margin-top: 14px; padding: 19px 14px 12px; }
QGroupBox::title { subcontrol-origin: margin; left: 15px; padding: 0 5px; }
QPushButton { background: white; border: 1px solid #bccfd2; border-radius: 6px;
              padding: 9px 15px; font-weight: 600; }
QPushButton:hover { background: #e2f2f0; border-color: #007d78; }
QPushButton:pressed, QPushButton:checked { background: #cae8e4; }
QPushButton:disabled { color: #93a2a7; background: #f3f6f6; }
QPushButton#primary { background: #007d78; color: white; border-color: #007d78; }
QPushButton#primary:hover { background: #006b67; }
QSpinBox, QComboBox { background: white; border: 1px solid #bccfd2; border-radius: 5px;
                       padding: 6px; min-height: 20px; }
QCheckBox { spacing: 8px; font-weight: 400; }
QCheckBox::indicator { width: 17px; height: 17px; }
QScrollArea { border: none; background: transparent; }
QStatusBar { background: #dde9ea; }
"""


def label(text, name=None):
    widget = QLabel(text)
    if name:
        widget.setObjectName(name)
    widget.setWordWrap(True)
    return widget


def spin(low, high, value):
    widget = QSpinBox()
    widget.setRange(low, high)
    widget.setValue(value)
    return widget


def button(text, slot, primary=False):
    widget = QPushButton(text)
    if primary:
        widget.setObjectName("primary")
    widget.clicked.connect(slot)
    return widget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Eurhythmics · Rhythm Studio")
        self.resize(1200, 880)
        self.setMinimumSize(850, 650)
        self.audio = Playback(self)
        self.audio.message.connect(self.statusBar().showMessage)
        self.audio.busy_changed.connect(self.audio_busy)
        self.audio.metronome_changed.connect(self.metronome_state)
        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)
        self.exercise = None
        self.session = None
        self.question = 0
        self.revealed = False
        self.make_setup()
        self.make_practice()
        self.statusBar().showMessage("Select rhythms from the three binary lists to begin.")

    def make_setup(self):
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        page = QWidget()
        page.setObjectName("setup")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 24, 28, 28)
        layout.setSpacing(12)
        layout.addWidget(label("EURHYTHMICS / PRACTICE", "eyebrow"))
        layout.addWidget(label("Rhythm Studio", "title"))
        layout.addWidget(label("Build fluency, one phrase at a time. Choose your mode and your rhythm vocabulary.", "subtitle"))
        settings = QGroupBox("Practice settings")
        grid = QGridLayout(settings)
        self.mode = QComboBox()
        self.mode.addItems(["Sight reading", "Melodic dictation"])
        self.mode.currentIndexChanged.connect(self.change_mode)
        self.numerator = spin(1, 12, 4)
        self.denominator = QComboBox()
        self.denominator.addItems(["2", "4", "8"])
        self.denominator.setCurrentText("4")
        meter = QHBoxLayout()
        meter.addWidget(self.numerator)
        meter.addWidget(QLabel("/"))
        meter.addWidget(self.denominator)
        self.bars = spin(1, 32, 4)
        self.tempo = spin(30, 240, 80)
        self.low = spin(30, 240, 65)
        self.high = spin(30, 240, 100)
        self.low.valueChanged.connect(lambda value: self.high.setMinimum(value))
        self.high.valueChanged.connect(lambda value: self.low.setMaximum(value))
        self.speed_box = QWidget()
        speed_layout = QHBoxLayout(self.speed_box)
        speed_layout.setContentsMargins(0, 0, 0, 0)
        speed_layout.addWidget(self.low)
        speed_layout.addWidget(QLabel("to"))
        speed_layout.addWidget(self.high)
        self.speed_box.hide()
        self.tempo_label = QLabel("Tempo · ♩ per minute")
        grid.addWidget(QLabel("Mode"), 0, 0)
        grid.addWidget(self.mode, 1, 0)
        grid.addWidget(QLabel("Time signature"), 0, 1)
        grid.addLayout(meter, 1, 1)
        grid.addWidget(QLabel("Bars"), 0, 2)
        grid.addWidget(self.bars, 1, 2)
        grid.addWidget(self.tempo_label, 0, 3)
        grid.addWidget(self.tempo, 1, 3)
        grid.addWidget(self.speed_box, 1, 3)
        self.ties = QCheckBox("Include ties between rhythm units (including across barlines)")
        self.count_in = QCheckBox("One-bar count-in before playback")
        self.count_in.setChecked(True)
        grid.addWidget(self.ties, 2, 0, 1, 4)
        grid.addWidget(self.count_in, 3, 0, 1, 4)
        grid.addWidget(label("Tempo always means quarter notes per minute. In compound meters, the metronome clicks dotted quarters.", "subtitle"), 4, 0, 1, 4)
        layout.addWidget(settings)
        row = QHBoxLayout()
        row.addWidget(label("Choose your rhythms", "eyebrow"))
        row.addStretch()
        row.addWidget(button("Select all", lambda: self.select_all(True)))
        row.addWidget(button("Clear all", lambda: self.select_all(False)))
        layout.addLayout(row)
        columns = QHBoxLayout()
        self.checks = {}
        for group in (1, 2, 3):
            patterns = [p for p in PATTERNS if p.group == group]
            box = QGroupBox(f"Binary List {group} · {len(patterns)} patterns")
            box_layout = QVBoxLayout(box)
            select = QCheckBox("Include this whole list")
            select.setChecked(True)
            select.clicked.connect(lambda checked, g=group: self.select_group(g, checked))
            box_layout.addWidget(select)
            for pattern in patterns:
                check = QCheckBox(pattern.name)
                check.setChecked(True)
                check.setToolTip(pattern.name)
                # Preview makes the textual names unambiguous, including triplets.
                box_layout.addWidget(check)
                box_layout.addWidget(RhythmPreview(pattern))
                self.checks[pattern.id] = check
            box_layout.addStretch()
            select.setTristate(True)
            for pattern in patterns:
                self.checks[pattern.id].stateChanged.connect(
                    lambda _, g=group, s=select: self.sync_group(g, s))
            columns.addWidget(box, 1)
        layout.addLayout(columns)
        layout.addWidget(label("Each unit stays intact inside a bar. Incompatible patterns are skipped; if none can fill the bar, you’ll be prompted to adjust your selection.", "subtitle"))
        self.start_button = button("Start sight reading →", self.start_session, True)
        self.start_button.setMinimumHeight(48)
        layout.addWidget(self.start_button)
        scroll.setWidget(page)
        self.stack.addWidget(scroll)

    def sync_group(self, group, select):
        states = [self.checks[p.id].isChecked() for p in PATTERNS if p.group == group]
        select.setCheckState(Qt.Checked if all(states) else Qt.Unchecked if not any(states) else Qt.PartiallyChecked)

    def select_all(self, checked):
        for check in self.checks.values():
            check.setChecked(checked)

    def select_group(self, group, checked):
        for pattern in PATTERNS:
            if pattern.group == group:
                self.checks[pattern.id].setChecked(checked)

    def change_mode(self, index):
        if not hasattr(self, "speed_box"):
            return
        self.tempo.setVisible(index == 0)
        self.speed_box.setVisible(index == 1)
        self.tempo_label.setText("Tempo range · ♩ per minute" if index else "Tempo · ♩ per minute")
        self.start_button.setText("Start dictation →" if index else "Start sight reading →")

    def make_practice(self):
        page = QWidget()
        page.setObjectName("practice")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(25, 22, 25, 22)
        layout.setSpacing(13)
        header = QHBoxLayout()
        text = QVBoxLayout()
        self.practice_title = label("Sight reading", "title")
        self.practice_meta = label("", "subtitle")
        text.addWidget(self.practice_title)
        text.addWidget(self.practice_meta)
        header.addLayout(text, 1)
        header.addWidget(button("Exit to setup", self.exit_session))
        layout.addLayout(header)
        self.practice_hint = label("", "subtitle")
        layout.addWidget(self.practice_hint)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        self.score = ScoreWidget()
        scroll.setWidget(self.score)
        layout.addWidget(scroll, 1)
        self.sight_controls = QWidget()
        sight = QHBoxLayout(self.sight_controls)
        sight.setContentsMargins(0, 0, 0, 0)
        sight.addWidget(QLabel("Tempo · ♩ ="))
        self.live_tempo = spin(30, 240, 80)
        self.live_tempo.valueChanged.connect(self.change_tempo)
        sight.addWidget(self.live_tempo)
        self.metronome_button = button("Start metronome", self.toggle_metronome)
        self.metronome_button.setCheckable(True)
        sight.addWidget(self.metronome_button)
        self.backing = QCheckBox("Metronome with answer")
        self.backing.setChecked(True)
        sight.addWidget(self.backing)
        sight.addStretch()
        layout.addWidget(self.sight_controls)
        controls = QHBoxLayout()
        self.play_button = button("Play right answer", self.play_exercise, True)
        controls.addWidget(self.play_button)
        controls.addWidget(button("Stop audio", self.stop_audio))
        self.reveal_button = button("Reveal answer", self.reveal)
        controls.addWidget(self.reveal_button)
        controls.addStretch()
        self.next_button = button("Randomize again →", self.next_question)
        controls.addWidget(self.next_button)
        layout.addLayout(controls)
        self.stack.addWidget(page)

    def start_session(self):
        patterns = tuple(p for p in PATTERNS if self.checks[p.id].isChecked())
        meter = Meter(self.numerator.value(), int(self.denominator.currentText()))
        try:
            fill_options(patterns, meter)
        except ValueError as error:
            QMessageBox.information(self, "Adjust practice settings", str(error))
            return
        self.session = dict(patterns=patterns, meter=meter, bars=self.bars.value(),
                            ties=self.ties.isChecked(), melodic=self.mode.currentIndex() == 1)
        self.question = 0
        self.stack.setCurrentIndex(1)
        self.sight_controls.setVisible(not self.session["melodic"])
        self.reveal_button.setVisible(self.session["melodic"])
        self.live_tempo.blockSignals(True)
        self.live_tempo.setValue(self.tempo.value())
        self.live_tempo.blockSignals(False)
        self.next_question()

    def next_question(self):
        if not self.session:
            return
        self.audio.clear_exercise_cache()
        melodic = self.session["melodic"]
        bpm = random.randint(self.low.value(), self.high.value()) if melodic else self.live_tempo.value()
        self.exercise = generate(**self.session, bpm=bpm)
        self.question += 1
        self.revealed = False
        self.score.set_exercise(self.exercise, hidden=melodic)
        self.practice_title.setText(f"Dictation · question {self.question}" if melodic else "Sight reading")
        self.practice_meta.setText(f"{self.exercise.meter} time  ·  {self.exercise.bars} bars" +
                                   ("  ·  key and tempo revealed with the answer" if melodic else ""))
        self.practice_hint.setText("Listen to the melody and write it on paper. Replay preserves the exact melody and tempo."
                                   if melodic else "Read the rhythm on a single pitch. Teal curves mark ties; hold through them without a new attack.")
        self.play_button.setText("Replay melody" if melodic else "Play right answer")
        self.next_button.setText("Next question →" if melodic else "Randomize again →")
        self.reveal_button.setEnabled(True)
        if melodic:
            # Defer autoplay until the practice screen has painted.
            QTimer.singleShot(0, self.autoplay)
        else:
            self.statusBar().showMessage("Ready. Start the metronome or play the right answer.")

    def autoplay(self):
        if self.stack.currentIndex() == 1 and self.session and self.session["melodic"]:
            self.play_exercise()

    def play_exercise(self):
        if self.exercise:
            self.audio.play(self.exercise, self.count_in.isChecked(),
                            self.backing.isChecked() and not self.session["melodic"])

    def stop_audio(self):
        self.audio.stop()
        self.statusBar().showMessage("Audio stopped.")

    def reveal(self):
        if self.exercise:
            self.revealed = True
            self.score.set_exercise(self.exercise)
            self.reveal_button.setEnabled(False)
            self.practice_meta.setText(f"{self.exercise.key.name}  ·  {self.exercise.meter} time  ·  "
                                       f"{self.exercise.bars} bars  ·  ♩ = {self.exercise.bpm}")
            self.statusBar().showMessage("Answer revealed. Compare with your transcription, or replay while reading.")

    def change_tempo(self, value):
        if self.exercise and self.session and not self.session["melodic"]:
            running = self.audio.metronome_on
            self.audio.stop()
            self.exercise = replace(self.exercise, bpm=value)
            self.score.set_exercise(self.exercise)
            if running:
                self.audio.start_metronome(self.exercise.meter, value)

    def toggle_metronome(self, checked):
        if checked and self.exercise:
            self.audio.start_metronome(self.exercise.meter, self.live_tempo.value())
        else:
            self.audio.stop_metronome()

    def metronome_state(self, running):
        if hasattr(self, "metronome_button"):
            self.metronome_button.setChecked(running)
            self.metronome_button.setText("Stop metronome" if running else "Start metronome")

    def audio_busy(self, busy):
        if hasattr(self, "play_button"):
            self.play_button.setEnabled(not busy)

    def exit_session(self):
        self.audio.clear_exercise_cache()
        self.stack.setCurrentIndex(0)
        self.session = None
        self.exercise = None
        self.statusBar().showMessage("Adjust your settings for the next practice session.")

    def closeEvent(self, event):
        self.audio.close()
        event.accept()


def main():
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app = QApplication(sys.argv)
    app.setApplicationName("Eurhythmics Rhythm Studio")
    app.setStyle("Fusion")
    app.setStyleSheet(STYLE)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
