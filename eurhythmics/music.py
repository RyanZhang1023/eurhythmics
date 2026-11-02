"""Exact rhythm arithmetic and exercise generation, independent of Qt.

One quarter = 12 ticks; eighth triplets = 4 and sixteenths = 3.
Every unit stays intact inside a bar. Only unit boundaries may be tied.
"""
from dataclasses import dataclass, replace
import random

PPQ = 12


@dataclass(frozen=True)
class Pattern:
    id: str
    group: int
    name: str
    notes: tuple[int, ...]
    triplet: bool = False

    @property
    def ticks(self):
        return sum(self.notes)


PATTERNS = (
    Pattern("1-half", 1, "Half note", (24,)),
    Pattern("1-quarter", 1, "Quarter note", (12,)),
    Pattern("1-eighths", 1, "Two eighths", (6, 6)),
    Pattern("1-triplet", 1, "Three eighth-note triplets", (4, 4, 4), True),
    Pattern("1-sixteenths", 1, "Four sixteenths", (3, 3, 3, 3)),
    Pattern("2-dq-e", 2, "Dotted quarter + eighth", (18, 6)),
    Pattern("2-dq-ss", 2, "Dotted quarter + two sixteenths", (18, 3, 3)),
    Pattern("2-e-dq", 2, "Eighth + dotted quarter", (6, 18)),
    Pattern("2-ss-dq", 2, "Two sixteenths + dotted quarter", (3, 3, 18)),
    Pattern("2-e-q-e", 2, "Eighth + quarter + eighth", (6, 12, 6)),
    Pattern("2-ss-q-e", 2, "Two sixteenths + quarter + eighth", (3, 3, 12, 6)),
    Pattern("2-e-q-ss", 2, "Eighth + quarter + two sixteenths", (6, 12, 3, 3)),
    Pattern("2-ss-q-ss", 2, "Two sixteenths + quarter + two sixteenths", (3, 3, 12, 3, 3)),
    Pattern("3-e-ss", 3, "Eighth + two sixteenths", (6, 3, 3)),
    Pattern("3-ss-e", 3, "Two sixteenths + eighth", (3, 3, 6)),
    Pattern("3-s-e-s", 3, "Sixteenth + eighth + sixteenth", (3, 6, 3)),
    Pattern("3-de-s", 3, "Dotted eighth + sixteenth", (9, 3)),
    Pattern("3-s-de", 3, "Sixteenth + dotted eighth", (3, 9)),
)


@dataclass(frozen=True)
class Meter:
    numerator: int = 4
    denominator: int = 4

    @property
    def ticks(self):
        return self.numerator * 48 // self.denominator

    @property
    def pulse_ticks(self):
        # BPM always measures quarter notes. Compound meters click dotted quarters.
        if self.denominator == 8 and self.numerator >= 6 and self.numerator % 3 == 0:
            return 18
        return 48 // self.denominator

    def __str__(self):
        return f"{self.numerator}/{self.denominator}"


@dataclass(frozen=True)
class Key:
    name: str
    tonic: int  # MIDI pitch class
    letter: int  # C D E F G A B = 0..6
    signature: int  # sharps positive, flats negative
    minor: bool = False

    def pitches(self):
        intervals = (0, 2, 3, 5, 7, 8, 10) if self.minor else (0, 2, 4, 5, 7, 9, 11)
        # C-flat belongs just below C, rather than a major seventh above it.
        tonic = self.tonic
        if tonic - (0, 2, 4, 5, 7, 9, 11)[self.letter] > 6:
            tonic -= 12
        result = []
        for octave in range(3, 6):
            for step, interval in enumerate(intervals):
                midi = (octave + 1) * 12 + tonic + interval
                diatonic = octave * 7 + self.letter + step
                if 60 <= midi <= 81:
                    result.append((midi, diatonic))
        return result


KEYS = (
    Key("C major", 0, 0, 0), Key("G major", 7, 4, 1),
    Key("D major", 2, 1, 2), Key("A major", 9, 5, 3),
    Key("E major", 4, 2, 4), Key("B major", 11, 6, 5),
    Key("F♯ major", 6, 3, 6), Key("C♯ major", 1, 0, 7),
    Key("F major", 5, 3, -1), Key("B♭ major", 10, 6, -2),
    Key("E♭ major", 3, 2, -3), Key("A♭ major", 8, 5, -4),
    Key("D♭ major", 1, 1, -5), Key("G♭ major", 6, 4, -6),
    Key("C♭ major", 11, 0, -7),
    Key("A minor", 9, 5, 0, True), Key("E minor", 4, 2, 1, True),
    Key("B minor", 11, 6, 2, True), Key("F♯ minor", 6, 3, 3, True),
    Key("C♯ minor", 1, 0, 4, True), Key("G♯ minor", 8, 4, 5, True),
    Key("D♯ minor", 3, 1, 6, True), Key("A♯ minor", 10, 5, 7, True),
    Key("D minor", 2, 1, -1, True), Key("G minor", 7, 4, -2, True),
    Key("C minor", 0, 0, -3, True), Key("F minor", 5, 3, -4, True),
    Key("B♭ minor", 10, 6, -5, True), Key("E♭ minor", 3, 2, -6, True),
    Key("A♭ minor", 8, 5, -7, True),
)


@dataclass(frozen=True)
class Note:
    start: int
    ticks: int
    bar: int
    unit: int
    midi: int = 71
    diatonic: int = 34  # B4
    triplet: bool = False
    tie_next: bool = False


@dataclass(frozen=True)
class Exercise:
    meter: Meter
    bars: int
    notes: tuple[Note, ...]
    bpm: int
    key: Key | None = None

    @property
    def ticks(self):
        return self.meter.ticks * self.bars


def fill_options(patterns, meter):
    """Return a reachability table, avoiding greedy dead ends and recursion."""
    if not patterns:
        raise ValueError("Choose at least one rhythm before starting.")
    reachable = [False] * (meter.ticks + 1)
    reachable[0] = True
    for total in range(1, meter.ticks + 1):
        reachable[total] = any(p.ticks <= total and reachable[total - p.ticks] for p in patterns)
    if not reachable[-1]:
        raise ValueError(f"These rhythms cannot fill a bar of {meter} exactly. "
                         "Choose another meter or add shorter rhythm units.")
    return reachable


def generate(patterns, meter, bars, bpm, ties=False, melodic=False, rng=None):
    rng = rng or random.Random()
    if meter.numerator < 1 or meter.denominator not in (2, 4, 8):
        raise ValueError("Use a positive meter with denominator 2, 4, or 8.")
    if not 1 <= bars <= 32 or not 30 <= bpm <= 240:
        raise ValueError("Use 1–32 bars and 30–240 quarter notes per minute.")
    reachable = fill_options(patterns, meter)
    key = rng.choice(KEYS) if melodic else None
    pitches = key.pitches() if key else [(71, 34)]
    pitch_index = min(range(len(pitches)), key=lambda i: abs(pitches[i][0] - 67))
    notes, boundaries = [], []
    unit = 0
    for bar in range(bars):
        remaining = meter.ticks
        while remaining:
            choices = [p for p in patterns if p.ticks <= remaining and reachable[remaining - p.ticks]]
            pattern = rng.choice(choices)
            if notes:
                boundaries.append(len(notes) - 1)
            for duration in pattern.notes:
                pitch_index = max(0, min(len(pitches) - 1, pitch_index + rng.choice((-2, -1, 0, 1, 2))))
                midi, diatonic = pitches[pitch_index]
                notes.append(Note(bar * meter.ticks + meter.ticks - remaining,
                                  duration, bar, unit, midi, diatonic, pattern.triplet))
                remaining -= duration
            unit += 1
    if ties and boundaries:
        chosen = [i for i in boundaries if rng.random() < .28]
        if not chosen:
            chosen = [rng.choice(boundaries)]
        for i in chosen:
            notes[i] = replace(notes[i], tie_next=True)
            notes[i + 1] = replace(notes[i + 1], midi=notes[i].midi, diatonic=notes[i].diatonic)
    return Exercise(meter, bars, tuple(notes), bpm, key)


def sounding_notes(exercise):
    """Coalesce tie chains into sustained notes, including across barlines."""
    result = []
    for i, note in enumerate(exercise.notes):
        if i and exercise.notes[i - 1].tie_next:
            start, ticks, midi = result[-1]
            result[-1] = (start, ticks + note.ticks, midi)
        else:
            result.append((note.start, note.ticks, note.midi))
    return result
