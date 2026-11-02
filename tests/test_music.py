from collections import Counter
import random
import unittest

from eurhythmics.music import KEYS, PATTERNS, Exercise, Meter, Note, generate, sounding_notes


class RhythmTests(unittest.TestCase):
    def test_exact_vocabulary(self):
        self.assertEqual(Counter(p.group for p in PATTERNS), {1: 5, 2: 8, 3: 5})
        self.assertEqual(len(set(p.notes for p in PATTERNS)), 18)
        self.assertTrue(all(p.ticks == 24 for p in PATTERNS if p.group == 2))
        self.assertTrue(all(p.ticks == 12 for p in PATTERNS if p.group == 3))
        self.assertEqual([p.notes for p in PATTERNS if p.triplet], [(4, 4, 4)])
        list2 = {p.notes for p in PATTERNS if p.group == 2}
        expected = {(18, 6), (18, 3, 3), (6, 18), (3, 3, 18),
                    (6, 12, 6), (6, 12, 3, 3), (3, 3, 12, 6), (3, 3, 12, 3, 3)}
        self.assertEqual(list2, expected)

    def test_randomized_invariants(self):
        cross_bar_ties = 0
        for seed in range(140):
            rng = random.Random(seed)
            meter = Meter(rng.choice((2, 3, 4, 5, 6, 9, 12)), 4)
            selected = rng.sample(list(PATTERNS), rng.randint(2, 18))
            # Ensure randomized selections can tile odd-numbered quarter bars.
            if not any(p.ticks == 12 for p in selected):
                selected.append(PATTERNS[1])
            ex = generate(selected, meter, rng.randint(1, 10), rng.randint(30, 240),
                          ties=True, melodic=True, rng=rng)
            self.assertEqual(sum(n.ticks for n in ex.notes), meter.ticks * ex.bars)
            self.assertEqual(ex.notes[-1].start + ex.notes[-1].ticks, ex.ticks)
            self.assertFalse(ex.notes[-1].tie_next)
            for bar in range(ex.bars):
                self.assertEqual(sum(n.ticks for n in ex.notes if n.bar == bar), meter.ticks)
            for unit in {n.unit for n in ex.notes}:
                notes = [n for n in ex.notes if n.unit == unit]
                self.assertIn(tuple(n.ticks for n in notes), {p.notes for p in selected})
                self.assertEqual(len({n.bar for n in notes}), 1)
            for i, note in enumerate(ex.notes[:-1]):
                following = ex.notes[i + 1]
                self.assertEqual(note.start + note.ticks, following.start)
                if note.tie_next:
                    self.assertNotEqual(note.unit, following.unit)
                    self.assertEqual((note.midi, note.diatonic), (following.midi, following.diatonic))
                    cross_bar_ties += note.bar != following.bar
            self.assertEqual(sum(duration for _, duration, _ in sounding_notes(ex)), ex.ticks)
        self.assertGreater(cross_bar_ties, 0)

    def test_invalid_and_short_meters(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            generate([], Meter(), 4, 80)
        with self.assertRaisesRegex(ValueError, "cannot fill"):
            generate([PATTERNS[0]], Meter(3, 4), 4, 80)
        with self.assertRaisesRegex(ValueError, "cannot fill"):
            generate(PATTERNS, Meter(3, 8), 4, 80)
        ex = generate(PATTERNS, Meter(6, 8), 4, 80)
        self.assertEqual(ex.ticks, 144)

    def test_half_only_and_no_ties(self):
        ex = generate([PATTERNS[0]], Meter(4, 4), 3, 80, rng=random.Random(4))
        self.assertEqual(len(ex.notes), 6)
        self.assertTrue(all(not n.tie_next for n in ex.notes))

    def test_sustain_chain(self):
        notes = (Note(0, 12, 0, 0, 60, 28, tie_next=True),
                 Note(12, 12, 0, 1, 60, 28, tie_next=True),
                 Note(24, 12, 1, 2, 60, 28))
        ex = Exercise(Meter(2, 4), 2, notes, 80)
        self.assertEqual(sounding_notes(ex), [(0, 36, 60)])

    def test_all_keys_spelled_in_signature(self):
        # Compare written pitches with the actual pitch after applying the key signature.
        natural = (0, 2, 4, 5, 7, 9, 11)
        sharps, flats = (3, 0, 4, 1, 5, 2, 6), (6, 2, 5, 1, 4, 0, 3)
        self.assertEqual(len(KEYS), 30)
        for key in KEYS:
            changed = (sharps if key.signature > 0 else flats)[:abs(key.signature)]
            for midi, diatonic in key.pitches():
                octave, letter = divmod(diatonic, 7)
                adjustment = (1 if key.signature > 0 else -1) if letter in changed else 0
                self.assertEqual(midi, (octave + 1) * 12 + natural[letter] + adjustment, key.name)

    def test_meter_pulses(self):
        self.assertEqual(Meter(6, 8).pulse_ticks, 18)
        self.assertEqual(Meter(9, 8).pulse_ticks, 18)
        self.assertEqual(Meter(4, 4).pulse_ticks, 12)
        self.assertEqual(Meter(2, 2).pulse_ticks, 24)


if __name__ == "__main__":
    unittest.main()
