"""Portable WAV synthesis: no MIDI service, samples, or soundfont required."""
from array import array
import math
from pathlib import Path
import sys
import wave

from .music import PPQ, sounding_notes

RATE = 22050


def pcm(samples):
    values = array("h", samples)
    if sys.byteorder != "little":
        values.byteswap()
    return values.tobytes()


def click(accent=False):
    frequency = 1500 if accent else 1000
    return pcm(int(11000 * math.exp(-i / (RATE * .008)) *
                   math.sin(2 * math.pi * frequency * i / RATE)) for i in range(int(RATE * .045)))


def metronome_samples(meter, bpm):
    frames = round(meter.ticks / PPQ * 60 / bpm * RATE)
    output = bytearray(frames * 2)
    for tick in range(0, meter.ticks, meter.pulse_ticks):
        start = round(tick / PPQ * 60 / bpm * RATE) * 2
        sample = click(tick == 0)
        size = min(len(sample), len(output) - start)
        output[start:start + size] = sample[:size]
    return bytes(output)


def write_wav(path, data):
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        handle.writeframes(data)


def synthesize(exercise, path, count_in=True, backing=False):
    """Stream one note at a time so long exercises do not allocate huge buffers."""
    seconds_per_tick = 60 / exercise.bpm / PPQ
    cache = {}
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(RATE)
        if count_in:
            handle.writeframes(metronome_samples(exercise.meter, exercise.bpm))
        for start, duration, midi in sounding_notes(exercise):
            first = round(start * seconds_per_tick * RATE)
            last = round((start + duration) * seconds_per_tick * RATE)
            frames = last - first
            token = (frames, midi)
            if token not in cache:
                frequency = 440 * 2 ** ((midi - 69) / 12)
                attack, release = RATE * .008, min(RATE * .035, frames / 5)
                omega = 2 * math.pi * frequency / RATE
                cache[token] = pcm(int(8500 * min(1, i / attack, (frames - 1 - i) / release) *
                                       (.78 * math.sin(omega * i) + .16 * math.sin(2 * omega * i) +
                                        .06 * math.sin(3 * omega * i))) for i in range(frames))
            data = cache[token]
            if backing:
                mixed = array("h")
                mixed.frombytes(data)
                if sys.byteorder != "little":
                    mixed.byteswap()
                pulse = exercise.meter.pulse_ticks
                next_tick = ((start + pulse - 1) // pulse) * pulse
                for tick in range(next_tick, start + duration, pulse):
                    offset = round(tick * seconds_per_tick * RATE) - first
                    sample = array("h")
                    sample.frombytes(click(tick % exercise.meter.ticks == 0))
                    if sys.byteorder != "little":
                        sample.byteswap()
                    for j in range(min(len(sample), frames - offset)):
                        mixed[offset + j] = max(-32768, min(32767, mixed[offset + j] + sample[j]))
                data = pcm(mixed)
            handle.writeframes(data)
        handle.writeframes(bytes(int(RATE * .12) * 2))
    return Path(path)
