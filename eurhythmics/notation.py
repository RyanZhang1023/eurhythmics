"""Font-independent noteheads, stems, beams, triplets and system-spanning ties."""
import math
from PyQt5.QtCore import QPointF, QRectF, QSize, Qt
from PyQt5.QtGui import QColor, QFont, QPainter, QPainterPath, QPen
from PyQt5.QtWidgets import QWidget

INK = QColor("#182b35")
TEAL = QColor("#007d78")
SPACE = 10


def note_y(note, top):
    # Top treble line is F5 (diatonic 38).
    return top + (38 - note.diatonic) * SPACE / 2


def draw_head(painter, x, y, hollow=False):
    painter.save()
    painter.translate(x, y)
    painter.rotate(-22)
    painter.setBrush(QColor("white") if hollow else INK)
    painter.setPen(QPen(INK, 1.6))
    painter.drawEllipse(QRectF(-5.4, -3.6, 10.8, 7.2))
    painter.restore()


def draw_accidental(painter, x, y, sharp):
    painter.setPen(QPen(INK, 1.2))
    if sharp:
        for dx in (-2, 2):
            painter.drawLine(QPointF(x + dx, y - 9), QPointF(x + dx, y + 9))
        painter.setPen(QPen(INK, 2.1))
        for dy in (-3, 3):
            painter.drawLine(QPointF(x - 5, y + dy + 1), QPointF(x + 5, y + dy - 1))
    else:
        painter.drawLine(QPointF(x - 2, y - 13), QPointF(x - 2, y + 5))
        path = QPainterPath(QPointF(x - 2, y))
        path.cubicTo(x + 7, y - 7, x + 8, y + 1, x - 2, y + 5)
        painter.drawPath(path)


def draw_unit(p, positions, notes, top):
    """Beam contiguous short notes within this unit, never across units."""
    p.save()
    stem_ends = []
    for (x, y), note in zip(positions, notes):
        draw_head(p, x, y, note.ticks == 24)
        # Ledger lines below/above the five-line staff.
        p.setPen(QPen(INK, 1))
        for ledger in range(1, 5):
            for ly in (top - ledger * SPACE, top + 40 + ledger * SPACE):
                if (ly < top and y <= ly + .1) or (ly > top + 40 and y >= ly - .1):
                    p.drawLine(QPointF(x - 8, ly), QPointF(x + 8, ly))
        end = min(y - 30, top - 12)
        stem_ends.append(end)
        p.setPen(QPen(INK, 1.4))
        p.drawLine(QPointF(x + 5, y), QPointF(x + 5, end))
        if note.ticks in (9, 18):
            p.setBrush(INK)
            p.drawEllipse(QPointF(x + 11, y - 5 if (y - top) % 10 == 0 else y), 1.8, 1.8)

    # A horizontal beam above the highest note keeps dense melodies legible.
    beam_y = min(stem_ends) if stem_ends else top - 12
    groups, current = [], []
    for index, note in enumerate(notes):
        if note.ticks in (3, 4, 6, 9):
            current.append(index)
        elif current:
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    for group in groups:
        p.setPen(QPen(INK, 1.4))
        for i in group:
            x, y = positions[i]
            p.drawLine(QPointF(x + 5, y), QPointF(x + 5, beam_y))
        if len(group) == 1:
            i = group[0]
            x = positions[i][0] + 5
            # Dots use a solid brush; flags must always use the same open curve.
            p.setBrush(Qt.NoBrush)
            for flag in range(2 if notes[i].ticks == 3 else 1):
                path = QPainterPath(QPointF(x, beam_y + flag * 7))
                path.cubicTo(x + 12, beam_y + flag * 7 + 6,
                             x + 10, beam_y + flag * 7 + 13, x + 7, beam_y + flag * 7 + 17)
                p.setPen(QPen(INK, 2.4))
                p.drawPath(path)
        else:
            left, right = positions[group[0]][0] + 5, positions[group[-1]][0] + 5
            p.fillRect(QRectF(left, beam_y, right - left, 3.5), INK)
            for loc, i in enumerate(group):
                if notes[i].ticks != 3:
                    continue
                x = positions[i][0] + 5
                if loc + 1 < len(group) and notes[group[loc + 1]].ticks == 3:
                    end = positions[group[loc + 1]][0] + 5
                    p.fillRect(QRectF(x, beam_y + 7, end - x, 3), INK)
                elif loc == 0 or notes[group[loc - 1]].ticks != 3:
                    direction = 1 if loc < len(group) - 1 else -1
                    p.fillRect(QRectF(x if direction == 1 else x - 9, beam_y + 7, 9, 3), INK)
    if notes and notes[0].triplet:
        left, right = positions[0][0] + 5, positions[-1][0] + 5
        p.setPen(INK)
        p.setFont(QFont("Segoe UI", 10))
        p.drawText(QRectF(left, beam_y - 23, max(20, right - left), 20), Qt.AlignCenter, "3")
    p.restore()


class RhythmPreview(QWidget):
    def __init__(self, pattern, parent=None):
        super().__init__(parent)
        self.pattern = pattern
        self.setFixedSize(140, 68)
        self.setToolTip(pattern.name)

    def paintEvent(self, event):
        from .music import Note
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(0, 8)
        count = len(self.pattern.notes)
        positions = [(16 + i * 27, 48) for i in range(count)]
        notes = [Note(0, duration, 0, 0, triplet=self.pattern.triplet) for duration in self.pattern.notes]
        draw_unit(p, positions, notes, 28)


class ScoreWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.exercise = None
        self.hidden_answer = False
        self.setMinimumWidth(600)
        self.setAutoFillBackground(True)
        palette = self.palette()
        palette.setColor(self.backgroundRole(), QColor("white"))
        self.setPalette(palette)

    def set_exercise(self, exercise, hidden=False):
        self.exercise, self.hidden_answer = exercise, hidden
        self.relayout()

    def bar_width(self, bar):
        count = sum(n.bar == bar for n in self.exercise.notes)
        return max(165, count * 27 + 35)

    def systems(self):
        if not self.exercise:
            return []
        available = max(520, self.width() - 170)
        rows, current, used = [], [], 0
        for bar in range(self.exercise.bars):
            width = self.bar_width(bar)
            if current and used + width > available:
                rows.append(current)
                current, used = [], 0
            current.append(bar)
            used += width
        if current:
            rows.append(current)
        return rows

    def relayout(self):
        rows = self.systems()
        width = 600
        if self.exercise:
            width = max(width, max(self.bar_width(b) for b in range(self.exercise.bars)) + 170)
        self.setMinimumWidth(width)
        self.setMinimumHeight(max(320, 75 + len(rows) * 170))
        self.updateGeometry()
        self.update()

    def resizeEvent(self, event):
        self.relayout()
        super().resizeEvent(event)

    def sizeHint(self):
        return QSize(900, self.minimumHeight())

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.fillRect(self.rect(), QColor("white"))
        if not self.exercise or self.hidden_answer:
            p.setPen(TEAL)
            p.setFont(QFont("Segoe UI", 22))
            p.drawText(QRectF(30, 60, self.width() - 60, 60), Qt.AlignCenter,
                       "Listen. Remember. Write." if self.hidden_answer else "Your practice starts here.")
            p.setPen(QColor("#61727a"))
            p.setFont(QFont("Segoe UI", 12))
            p.drawText(QRectF(30, 130, self.width() - 60, 90), Qt.AlignHCenter | Qt.TextWordWrap,
                       "Write the melody on paper, then reveal the score to compare.\nReplay as often as you need."
                       if self.hidden_answer else "Choose your rhythms and start a practice session.")
            return
        ex = self.exercise
        p.setPen(INK)
        p.setFont(QFont("Segoe UI", 11))
        caption = f"{ex.key.name}  ·  " if ex.key else "Rhythm reading  ·  "
        p.drawText(25, 30, caption + f"♩ = {ex.bpm}   ·   {ex.bars} bars")
        positions = {}
        row_edges = {}
        for row, bars in enumerate(self.systems()):
            top = 105 + row * 170
            # Extra room for full seven-accidental key signatures.
            signature_width = abs(ex.key.signature) * 9 if ex.key else 0
            start_x = 105 + signature_width
            total = sum(self.bar_width(b) for b in bars)
            extra = max(0, self.width() - 30 - start_x - total) / len(bars)
            right_edge = start_x + total + extra * len(bars)
            row_edges[row] = (start_x - 12, right_edge, top)
            p.setPen(QPen(QColor("#8b999e"), .8))
            for line in range(5):
                p.drawLine(QPointF(25, top + line * SPACE), QPointF(right_edge, top + line * SPACE))
            p.setPen(INK)
            if ex.key:
                p.setFont(QFont("Segoe UI Symbol", 32))
                p.drawText(QRectF(27, top - 20, 45, 80), Qt.AlignCenter, "𝄞")
                offsets = (0, 3, -1, 2, 5, 1, 4) if ex.key.signature > 0 else (4, 1, 5, 2, 6, 3, 7)
                for i in range(abs(ex.key.signature)):
                    draw_accidental(p, 70 + i * 9, top + offsets[i] * 5, ex.key.signature > 0)
            else:
                p.setPen(QPen(INK, 3))
                p.drawLine(QPointF(43, top + 13), QPointF(43, top + 28))
                p.drawLine(QPointF(51, top + 13), QPointF(51, top + 28))
            p.setPen(INK)
            p.setFont(QFont("Segoe UI", 15, QFont.Bold))
            for text, yy in ((str(ex.meter.numerator), top - 4), (str(ex.meter.denominator), top + 17)):
                p.drawText(QRectF(start_x - 35, yy, 30, 26), Qt.AlignCenter, text)
            x = start_x
            for bar in bars:
                width = self.bar_width(bar) + extra
                p.setPen(QColor("#6b7c83"))
                p.setFont(QFont("Segoe UI", 9))
                p.drawText(QPointF(x, top - 45), str(bar + 1))
                notes = [(i, n) for i, n in enumerate(ex.notes) if n.bar == bar]
                # Mix time spacing with a guaranteed minimum distance for short notes.
                weights = [math.sqrt(n.ticks) for _, n in notes]
                total_weight = sum(weights)
                used_weight = 0
                groups = {}
                for idx, ((i, note), weight) in enumerate(zip(notes, weights)):
                    nx = x + 12 + idx * 22 + used_weight / total_weight * max(0, width - 35 - len(notes) * 22)
                    ny = note_y(note, top)
                    positions[i] = (row, nx, ny)
                    groups.setdefault(note.unit, []).append((i, note))
                    used_weight += weight
                for items in groups.values():
                    draw_unit(p, [(positions[i][1], positions[i][2]) for i, n in items],
                              [n for i, n in items], top)
                x += width
                p.setPen(QPen(INK, 1))
                p.drawLine(QPointF(x, top), QPointF(x, top + 40))
                if bar == ex.bars - 1:
                    p.setPen(QPen(INK, 3))
                    p.drawLine(QPointF(x - 4, top), QPointF(x - 4, top + 40))
        p.setPen(QPen(TEAL, 1.7))
        p.setBrush(Qt.NoBrush)
        for i, note in enumerate(ex.notes[:-1]):
            if not note.tie_next:
                continue
            row1, x1, y1 = positions[i]
            row2, x2, y2 = positions[i + 1]
            if row1 == row2:
                self.tie(p, x1 + 3, y1 + 8, x2 - 3, y2 + 8)
            else:
                self.tie(p, x1 + 3, y1 + 8, row_edges[row1][1], y1 + 8)
                self.tie(p, row_edges[row2][0], y2 + 8, x2 - 3, y2 + 8)

    @staticmethod
    def tie(p, x1, y1, x2, y2):
        path = QPainterPath(QPointF(x1, y1))
        bend = min(18, max(9, (x2 - x1) * .15))
        path.cubicTo(x1 + (x2 - x1) / 3, y1 + bend,
                     x2 - (x2 - x1) / 3, y2 + bend, x2, y2)
        p.drawPath(path)
