from array import array
from pathlib import Path
import random
import tempfile
import unittest
import wave

from eurhythmics.audio import RATE, metronome_samples, synthesize
from eurhythmics.music import PATTERNS, Meter, generate


class AudioTests(unittest.TestCase):
    def test_audio_duration_countin_and_backing(self):
        ex = generate(PATTERNS, Meter(3, 4), 2, 120, ties=True,
                      melodic=True, rng=random.Random(7))
        with tempfile.TemporaryDirectory() as directory:
            for count_in, backing in ((False, False), (True, False), (True, True)):
                path = Path(directory) / "test.wav"
                synthesize(ex, path, count_in, backing)
                with wave.open(str(path), "rb") as handle:
                    self.assertEqual(handle.getframerate(), RATE)
                    self.assertEqual(handle.getnchannels(), 1)
                    expected = (ex.ticks + (ex.meter.ticks if count_in else 0)) / 12 * 60 / ex.bpm + .12
                    self.assertAlmostEqual(handle.getnframes() / RATE, expected, places=3)
                    samples = array("h", handle.readframes(handle.getnframes()))
                    self.assertGreater(max(samples), 1000)
                    self.assertLess(max(samples), 32767)

    def test_metronome_duration_and_accents(self):
        for meter in (Meter(4, 4), Meter(6, 8), Meter(2, 2)):
            data = metronome_samples(meter, 120)
            self.assertEqual(len(data), round(meter.ticks / 12 * .5 * RATE) * 2)
            samples = array("h", data)
            # Silence between short clicks; nonzero samples at the next pulse.
            self.assertTrue(all(value == 0 for value in samples[int(.06 * RATE):int(.1 * RATE)]))
            next_pulse = round(meter.pulse_ticks / 12 * .5 * RATE)
            self.assertTrue(any(samples[next_pulse:next_pulse + 100]))


if __name__ == "__main__":
    unittest.main()
