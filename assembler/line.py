from dataclasses import dataclass, field
from typing import NoReturn


Span = tuple[int, int]
class Line:
    @property
    def span(self): return 0, len(self.text)

    def __init__(self, text: str) -> None:
        self.text = text
        self.warns = list[tuple[Span, str]]()
        self.errs = list[tuple[Span, str]]()

    def add_warn(self, span: Span, msg: str):
        self.warns.append((span, msg))

    def add_error(self, span: Span, msg: str):
        self.errs.append((span, msg))

    def has_info(self) -> bool:
        return len(self.warns) > 0 or len(self.errs) > 0

    def has_error(self) -> bool:
        return len(self.errs) > 0

    def _render(self, out: list[str], span: Span, msg: str):
        start, end = span
        count = end - start
        out.append(self.text)
        out.append(' '*start + '^'*count)
        out.append(msg)

    def __str__(self) -> str:
        lines = list[str]()
        for span, msg in self.errs: self._render(lines, span, 'ERROR: ' + msg)
        for span, msg in self.warns: self._render(lines, span, 'WARN:  ' + msg)
        return '\n'.join(lines)

class Match:
    @property
    def text(self) -> str:
        return self.line.text[slice(*self.span)]

    def __init__(self, line: Line, span: Span, argspan: list[Span], compact: str, index: int) -> None:
        self.line = line
        self.span = span
        self.argspan = argspan
        self.compact = compact
        self.index = index

    def _get_span(self, idx: int | None) -> Span:
        if idx is None or idx >= len(self.argspan): return self.span
        else: return self.argspan[idx]

    def add_warn(self, hole: int | None, msg: str):
        self.line.add_warn(self._get_span(hole), msg)

    def add_error(self, hole: int | None, msg: str):
        self.line.add_error(self._get_span(hole), msg)

    def raise_error(self) -> NoReturn:
        raise

# TODO
class SymRef:
    space: str
    symbol: str
    shift: int
    mask: int

@dataclass
class Inst:
    word: int
    ref: str | None = None

    def __str__(self) -> str:
        if self.ref:
            return f'{self.word:08x} -> {self.ref}'
        return f'{self.word:08x}'
