from __future__ import annotations

import bisect
import re
from typing import Dict, List, Tuple

from PySide6.QtCore import QTimer
from PySide6.QtGui import QColor, QSyntaxHighlighter, QTextCharFormat


class RainbowBracketsHighlighter(QSyntaxHighlighter):
    """A non-incremental QSyntaxHighlighter that applies rainbow
    bracket highlighting using the original pairing logic from
    RainbowBrackets' executor.

    Usage: create with a QTextDocument (e.g. text_edit.document()),
    provide bracket_pairs (dict of opening->closing) and a list of
    color hex strings for layers. The highlighter will scan the
    whole document on changes and apply formats per block.
    """

    def __init__(
        self,
        document,
        bracket_pairs: Dict[str, str],
        colors: List[str],
        error_color: str = "#ff0000",
    ):
        super().__init__(document)
        self.brackets = bracket_pairs
        # Build a regexp pattern similar to the original plugin.
        brackets_list = sorted(
            list(bracket_pairs.keys()) + list(bracket_pairs.values()),
            key=len,
            reverse=True,
        )
        self.pattern = (
            "|".join(re.escape(b) for b in brackets_list) if brackets_list else ""
        )
        self.regexp = re.compile(self.pattern) if self.pattern else re.compile(r"$")

        self.num_layers = max(1, len(colors))
        self.colors = colors

        # Prepare Qt formats for each layer and for error
        self.layer_formats: List[QTextCharFormat] = []
        for c in colors:
            fmt = QTextCharFormat()
            fmt.setForeground(QColor(c))
            self.layer_formats.append(fmt)

        self.error_format = QTextCharFormat()
        self.error_format.setForeground(QColor(error_color))
        # Mark errors with underline as well (best-effort)
        try:
            self.error_format.setFontUnderline(True)
        except Exception:
            pass

        # block -> list of tuples (start_in_block, length, format_index_or_-1_for_error)
        self.block_formats: Dict[int, List[Tuple[int, int, int]]] = {}

        # Recompute guard to avoid re-entrancy / recursion when document
        # signals while we're already recomputing.
        self._in_recompute = False

        # Debounce timer for content changes (to avoid heavy recompute on rapid typing).
        # If you want immediate updates, set debounce_interval_ms to 0.
        self.debounce_interval_ms = 0
        self._debounce_timer = QTimer()
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.timeout.connect(self._on_debounce_timeout)

        # Recompute on document change
        doc = self.document()
        try:
            doc.contentsChanged.connect(self._on_contents_changed)
        except Exception:
            # some bindings expose contentsChanged differently; ignore if not available
            pass

        # initial compute
        self.recompute_regions()

    def _on_contents_changed(self):
        # Start/refresh debounce timer instead of immediate recompute.
        if self.debounce_interval_ms <= 0:
            # immediate path (no debounce)
            self._do_recompute_immediate()
        else:
            self._debounce_timer.start(self.debounce_interval_ms)

    def _on_debounce_timeout(self):
        self._do_recompute_immediate()

    def _do_recompute_immediate(self):
        # Recompute regions and request rehighlight.
        # To avoid re-entrancy where document operations during recompute
        # emit contentsChanged again, temporarily disconnect the signal.
        doc = self.document()
        try:
            try:
                doc.contentsChanged.disconnect(self._on_contents_changed)
            except Exception:
                # if disconnect fails (e.g. different binding) continue
                pass

            if self._in_recompute:
                return
            self.recompute_regions()
            # rehighlight will call highlightBlock for each block
            self.rehighlight()
        finally:
            try:
                doc.contentsChanged.connect(self._on_contents_changed)
            except Exception:
                pass

    def recompute_regions(self):
        """Scan the whole document and populate self.block_formats."""
        if self._in_recompute:
            return
        self._in_recompute = True
        try:
            self.block_formats = {}

            full_text = self.document().toPlainText()

            opening_stack: List[Tuple[str, int, int]] = []  # (bracket, pos, length)
            regions_by_layer: List[List[Tuple[int, int]]] = [
                list() for _ in range(self.num_layers)
            ]
            err_regions: List[Tuple[int, int]] = []

            # First pass: collect matched pairs and unmatched brackets.
            # We'll store matched pairs and later compute nesting/layers only
            # among matched pairs so that unmatched openings do not affect
            # the layer calculation.
            matched_pairs: List[Tuple[int, int, int, int]] = (
                []
            )  # (open_pos, open_len, close_pos, close_len)

            for m in self.regexp.finditer(full_text):
                pos = m.start()
                bracket = m.group()
                if bracket in self.brackets:
                    opening_stack.append((bracket, pos, len(bracket)))
                else:
                    if opening_stack and bracket == self.brackets[opening_stack[-1][0]]:
                        ob, op, olen = opening_stack.pop()
                        # record matched pair; do not assign layer now
                        matched_pairs.append((op, olen, pos, len(bracket)))
                    else:
                        # unmatched closing
                        err_regions.append((pos, len(bracket)))

            # Any remaining openings are unmatched left-brackets; mark them as errors
            while opening_stack:
                ob, op, olen = opening_stack.pop()
                err_regions.append((op, olen))

            # Second pass: compute nesting/layers among matched pairs only.
            # Build events for opens and closes from matched_pairs and traverse
            # to assign layer based on nesting depth of matched pairs.
            events: List[Tuple[int, str, int]] = []  # (pos, 'open'|'close', pair_index)
            for idx, (op, olen, cp, clen) in enumerate(matched_pairs):
                events.append((op, "open", idx))
                events.append((cp, "close", idx))
            # sort by position; opens before closes if same pos
            events.sort(key=lambda e: (e[0], 0 if e[1] == "open" else 1))

            pair_open_pos = {
                idx: (op, olen)
                for idx, (op, olen, cp, clen) in enumerate(matched_pairs)
            }
            pair_close_pos = {
                idx: (cp, clen)
                for idx, (op, olen, cp, clen) in enumerate(matched_pairs)
            }

            matched_stack: List[int] = []
            for pos, typ, idx in events:
                if typ == "open":
                    matched_stack.append(idx)
                else:  # close
                    # the top of matched_stack should be this idx
                    if matched_stack and matched_stack[-1] == idx:
                        matched_stack.pop()
                        layer = len(matched_stack) % self.num_layers
                        op, olen = pair_open_pos[idx]
                        cp, clen = pair_close_pos[idx]
                        regions_by_layer[layer].append((op, olen))
                        regions_by_layer[layer].append((cp, clen))
                    else:
                        # mismatched order among matched_pairs is unexpected,
                        # but if it happens, mark close as error
                        err_regions.append((pos, pair_close_pos.get(idx, (0, 1))[1]))

            # Map absolute positions to block-relative entries.
            # Optimize by caching block start offsets and using bisect instead
            # of calling findBlock for every match.
            doc = self.document()
            block = doc.firstBlock()
            block_starts: List[int] = []
            blocks: List = []
            while block.isValid():
                block_starts.append(block.position())
                blocks.append(block)
                block = block.next()

            def pos_to_block(abs_pos: int):
                # bisect_right-1 gives the block index whose start <= abs_pos
                i = bisect.bisect_right(block_starts, abs_pos) - 1
                if i < 0 or i >= len(blocks):
                    return None
                return blocks[i]

            for layer_index, regs in enumerate(regions_by_layer):
                for abs_pos, length in regs:
                    blk = pos_to_block(abs_pos)
                    if blk is None or not blk.isValid():
                        continue
                    block_no = blk.blockNumber()
                    start_in_block = abs_pos - blk.position()
                    self.block_formats.setdefault(block_no, []).append(
                        (start_in_block, length, layer_index)
                    )

            for abs_pos, length in err_regions:
                blk = pos_to_block(abs_pos)
                if blk is None or not blk.isValid():
                    continue
                block_no = blk.blockNumber()
                start_in_block = abs_pos - blk.position()
                self.block_formats.setdefault(block_no, []).append(
                    (start_in_block, length, -1)
                )

            # Optionally, sort formats inside each block by start
            for lst in self.block_formats.values():
                lst.sort(key=lambda x: x[0])
        finally:
            self._in_recompute = False

    def highlightBlock(self, text: str) -> None:  # required override
        block_no = self.currentBlock().blockNumber()
        entries = self.block_formats.get(block_no, [])
        for start, length, fmt_idx in entries:
            if start < 0 or start >= len(text):
                continue
            if fmt_idx == -1:
                self.setFormat(start, min(length, len(text) - start), self.error_format)
            else:
                fmt = self.layer_formats[fmt_idx % len(self.layer_formats)]
                self.setFormat(start, min(length, len(text) - start), fmt)
