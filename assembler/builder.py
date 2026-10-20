from __future__ import annotations

import re

from dataclasses import dataclass
from typing import IO, Any, Callable, Iterable, Iterator

from line import Inst, Line, Match, Span


class _Token: pass
@dataclass
class _Space(_Token): pass
@dataclass
class _Text(_Token): text: str
@dataclass
class _Hole(_Token): name: str

@dataclass
class _Pattern:
    parts: list[_Token]
    compact: str

def _parse_pattern(fmt: str) -> _Pattern:
    parts = []
    first = True
    compact = []
    for sub in fmt.split():
        if not first:
            parts.append(_Space())
        while True:
            start = sub.find('{')
            if start < 0: break
            end = sub.find('}')
            if end < 0: raise SyntaxError("Missing '}' in pattern")

            text = sub[:start]
            if text:
                parts.append(_Text(text))
                compact.append(text)
            name = sub[start+1:end]

            # That's right, it goes in the square hole
            parts.append(_Hole(name))
            sub = sub[end+1:]

        if sub:
            parts.append(_Text(sub))
            compact.append(sub)
        first = False
    return _Pattern(parts, ''.join(compact))

class _Entry: pass
@dataclass
class _Regex(_Entry):
    name: str
    regex: str
    func: Callable[[Match], Any]
@dataclass
class _Local(_Entry):
    name: str
    pats: list[_Pattern]
    func: Callable
@dataclass
class _Import(_Entry):
    src: Builder
    entry: _Entry
@dataclass
class _Combine(_Entry):
    src: Builder
    entries: list[_Entry]


@dataclass(frozen=True)
class _Owner:
    name: str

class _ParseNode: pass
@dataclass
class _ParseRegex(_ParseNode):
    regex: re.Pattern
    then: _ParseNode
    shown: str
    owner: _Owner
@dataclass
class _ParseText(_ParseNode):
    text: str
    then: _ParseNode
    shown: str
    owner: _Owner
@dataclass
class _ParseAlts(_ParseNode):
    alts: list[_ParseNode]
@dataclass
class _ParseCall(_ParseNode):
    target: _ParseNode
    then: _ParseNode
    owner: _Owner
    hole: str
@dataclass
class _ParseReturn(_ParseNode):
    compact: str
    index: int
    func: Callable
    owner: _Owner


Cons = tuple[Any, 'Cons'] | None
def _to_list(c: Cons) -> list:
    out = []
    while c is not None: out.append(c[0]); c = c[1]
    return out[::-1]


@dataclass
class _Frame:
    call: _ParseCall | None
    start: int
    args: Cons

@dataclass
class _Tree:
    func: Callable
    compact: str
    index: int
    span: Span
    args: list['_Tree']

@dataclass
class Diagnostic:
    line: int
    start: int
    end: int
    severity: str
    message: str


class _Parser:
    def __init__(self, text: str, root: _ParseNode) -> None:
        self.text = text
        self.root = root
        self.lower = text.lower()
        self.expected = dict[str, set[tuple[_Owner, ...]]]()
        self.far = -1

    def parse(self) -> Iterator[_Tree]:
        stack = (_Frame(None, 0, None), None)
        yield from self._parse(self.root, 0, None, stack)

    def _parse(self, node: _ParseNode, pos: int, args: Cons, stack: Cons) -> Iterator[_Tree]:
        match node:
            case _ParseRegex(regex, then, shown, owner):
                if match := regex.match(self.text, pos):
                    yield from self._parse(then, match.end(0), args, stack)
                else:
                    self._fail(pos, shown, owner, stack)
            case _ParseText(text, then, shown, owner):
                if self.lower.startswith(text, pos):
                    yield from self._parse(then, pos + len(text), args, stack)
                else:
                    self._fail(pos, shown, owner, stack)
            case _ParseAlts(alts):
                for alt in alts:
                    yield from self._parse(alt, pos, args, stack)
            case _ParseCall(target, then):
                yield from self._parse(target, pos, None, (_Frame(node, pos, args), stack))
            case _ParseReturn(compact, index, func, owner):
                assert stack, 'No more frames to pop'
                frame, rest = stack
                tree = _Tree(func, compact, index, (frame.start, pos), _to_list(args))
                if rest is None:
                    if pos == len(self.text): yield tree
                    else: self._fail(pos, 'end of line', owner, stack)
                else: yield from self._parse(frame.call.then, pos, (tree, frame.args), rest)

    def _fail(self, pos: int, what: str, owner: _Owner, stack: Cons):
        if pos < self.far: return
        if pos > self.far:
            self.far = pos
            self.expected = {}
        path = list[_Owner]()
        for f in _to_list(stack)[1:]:
            path.append(f.call.owner)
            if f.start == pos:
                what = '{' + f.call.hole + '}'
                break
        else:
            path.append(owner)
        self.expected.setdefault(what, set()).add(tuple(path))

    def report(self, line: Line):
        pos = self.far
        tok = re.match(r'\w+|\S', self.text[pos:])
        span = (pos, pos + (tok.end() if tok else 1))
        if pos == 0:
            line.add_error(span, f'Unknown instruction {self.text[slice(*span)]!r}')
            return
        exp = sorted(self.expected)
        paths = sorted({
            ' > '.join(owner.name for owner in path)
                for paths in self.expected.values()
                for path in paths
        })
        
        msg = f'Expected {", ".join(exp[:-1]) + " or " + exp[-1] if len(exp) > 1 else exp[0]}'
        msg += '\n       while matching ' + '\n                      '.join(paths[:6])
        if len(paths) > 6: msg += f'\n                    ... {len(paths) - 6} more'
        line.add_error(span, msg)


SPACE_REGEX = re.compile(r'\s+|(?<!\w)|(?!\w)')
def _build(src: Builder, entry: _Entry, memo: dict[int, _ParseNode]) -> _ParseNode:
    if id(entry) in memo:
        return memo[id(entry)]
    match entry:
        case _Regex(name, regex, func):
            owner = _Owner(name)
            node = _ParseRegex(re.compile(regex), _ParseReturn(regex, 0, func, owner), regex, owner)
        case _Local(name, pats, func):
            alts = list[_ParseNode]()
            for i, pat in enumerate(pats):
                owner = _Owner(name)
                seq = _ParseReturn(pat.compact, i, func, owner)
                for part in reversed(pat.parts):
                    match part:
                        case _Space():    seq = _ParseRegex(SPACE_REGEX,  seq, 'space',    owner)
                        case _Text(text): seq = _ParseText (text.lower(), seq, repr(text), owner)
                        case _Hole(name):
                            target = _build(src, src.entries[src.names[name]], memo)
                            seq = _ParseCall(target, seq, owner, name)
                alts.append(seq)
            node = _ParseAlts(alts)
        case _Import(src, entry): return _build(src, entry, memo)
        case _Combine(src, entries): 
            node = _ParseAlts([_build(src, entry, memo) for entry in entries])
        case _: raise AssertionError('Expected entry to be one of _Regex, _Local, _Import, _Combine')
    memo[id(entry)] = node
    return node


LABEL_REGEX = re.compile(r'([A-Za-z0-9_]+):')
class Assembler:
    @property
    def ipos(self) -> int: return len(self._words)

    def __init__(self, root: _ParseNode) -> None:
        self._root = root
        self._words = list[int]()
        self._labels = dict[str, int]()
        self._to_link = dict[int, str]()

    def _eval(self, line: Line, tree: _Tree) -> Any | None:
        args = [self._eval(line, arg) for arg in tree.args]
        spans = [arg.span for arg in tree.args]
        m = Match(line, tree.span, spans, tree.compact, tree.index)
        return tree.func(m, *args)

    def _match(self, parser: _Parser) -> tuple[list[Line], Any | None]:
        vals = list[tuple[Line, Any]]()
        lines = list[Line]()
        for tree in parser.parse():
            line2 = Line(parser.text)
            lines.append(line2)
            val = self._eval(line2, tree)
            if val is not None: vals.append((line2, val))
        if not vals: return lines, None
        line, val = vals[0]
        if len(vals) > 1: line.add_warn(line.span, 'Multiple candidates found, using first one')
        return [line], val

    def assemble_line(self, text: str, report: Callable[[Line]]) -> bool:
        if mlbl := LABEL_REGEX.fullmatch(text):
            if mlbl.group(1) in self._labels:
                line = Line(text)
                line.add_warn(line.span, f'Label {mlbl.group(1)!r} redefined')
                report(line)
            self._labels[mlbl.group(1)] = self.ipos
            return True

        if self.ipos > 0xFFFF:
            line = Line(text)
            line.add_error(line.span, 'PRAM end reached')
            report(line)
            return False

        parser = _Parser(text, self._root)

        lines, inst = self._match(parser)
        for line in lines:
            if line.has_info(): report(line)

        if not isinstance(inst, Inst):
            if not any(line.has_error() for line in lines):
                line = Line(text)
                parser.report(line)
                report(line)
            return False

        if inst.ref is not None: self._to_link[self.ipos] = inst.ref
        self._words.append(inst.word)
        return True

    def assemble(self, input: IO[str], report: Callable[[Line]] = print) -> bool:
        while True:
            line = input.readline()
            if not line: break
            line = line.strip()
            if not line or line.startswith('#'): continue
            if not self.assemble_line(line.strip(), report):
                return False
        return True

    def link(self) -> bool:
        for ipos, ref in self._to_link.items():
            if ref not in self._labels:
                line = Line(ref)
                print(f'ERROR: undefined label {ref}')
                return False
            to = self._labels[ref]
            self._words[ipos] = (self._words[ipos] & 0xFFFF0000) | (to & 0xFFFF)
        return True

    def emit(self, output: IO[bytes]):
        for word in self._words:
            output.write(word.to_bytes(4, 'big'))

    def check(self, lines: Iterable[str]) -> list[Diagnostic]:
        diags = list[Diagnostic]()
        refs = list[tuple[int, int, str, str]]()

        def collect(line: Line, lineno: int, col: int):
            for sev, items in (('error', line.errs), ('warning', line.warns)):
                for (start, end), msg in items:
                    msg = re.sub(r'\n\s+', '\n  ', msg)
                    d = Diagnostic(lineno, col + start, col + max(end, start + 1), sev, msg)
                    if d not in diags: diags.append(d)

        for lineno, raw in enumerate(lines):
            text = raw.strip()
            if not text or text.startswith('#'): continue
            col = len(raw) - len(raw.lstrip())
            report = lambda line: collect(line, lineno, col)
            ipos = self.ipos
            self.assemble_line(text, report)
            if ipos in self._to_link: refs.append((lineno, col, text, self._to_link[ipos]))

        for lineno, col, text, ref in refs:
            if ref in self._labels: continue
            match = re.search(rf'(?<!\w){re.escape(ref)}(?!\w)', text)
            start, end = match.span() if match else (0, len(text))
            diags.append(Diagnostic(lineno, col + start, col + end, 'error', f'Undefined label {ref!r}'))
        return diags


def _i(m: Match) -> int | None:
    try: return int(m.text, 0)
    except ValueError: return None

def _n(m: Match) -> str:
    return m.text

def _h(m: Match) -> int | None:
    try: return int(m.text, 16)
    except ValueError: return None

INT_PAT = r'0[xX][0-9A-Fa-f]+|0[bB][01]+|\d+'
class Builder:
    def __init__(self) -> None:
        self.entries = list[_Entry]()
        self.names = dict[str, int]()
        self.exports = list[str]()
        self._add_entry('i',  _Regex('i',  rf'-?({INT_PAT})', _i))
        self._add_entry('u',  _Regex('u',  INT_PAT, _i))
        self._add_entry('n',  _Regex('n',  r'(?-i:[0-9A-Za-z_]+)', _n))
        self._add_entry('hu', _Regex('hu', r'[0-9A-Fa-f]+', _h))

    def _add_entry(self, name: str, entry: _Entry):
        if name in self.names: raise KeyError(f'Entry {name} already exists')
        self.entries.append(entry)
        self.names[name] = len(self.entries) - 1

    def regex(self, regex: str, name: str | None = None, export: bool = False):
        def inner[*T](func: Callable[[Match], Any]):
            fname = name or func.__name__
            self._add_entry(fname, _Regex(fname, regex, func))
            if export: self.exports.append(fname)
            return func
        return inner

    def pattern(self, *texts: str, name: str | None = None, export: bool = False):
        pats = list(map(_parse_pattern, texts))
        for pat in pats:
            for part in pat.parts:
                if isinstance(part, _Hole):
                    if part.name not in self.names:
                        raise KeyError(part.name)
        def inner[*T](func: Callable[[Match, *T], Any]):
            fname = name or func.__name__
            self._add_entry(fname, _Local(fname, pats, func))
            if export: self.exports.append(fname)
            return func
        return inner

    def export(self, *texts: str, name: str | None = None): return self.pattern(*texts, name=name, export=True)

    def import_all(self, other: Builder) -> None:
        for name in other.exports:
            self._add_entry(name, _Import(other, other.entries[other.names[name]]))

    def reexport_all(self, other: Builder) -> None:
        for name in other.exports:
            self._add_entry(name, _Import(other, other.entries[other.names[name]]))
            self.exports.append(name)

    def add(self, name: str, other: Builder) -> None:
        entries = [other.entries[other.names[name]] for name in other.exports]
        self._add_entry(name, _Combine(other, entries))

    def build(self) -> Assembler:
        entries = [self.entries[self.names[name]] for name in self.exports]
        return Assembler(_build(self, _Combine(self, entries), {}))
