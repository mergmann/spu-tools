from dataclasses import dataclass
from typing import Any

from .usbclient import USBClient


class Encode:
    def encode(self) -> str:
        raise NotImplemented

def encode(obj: Any) -> str:
    if isinstance(obj, Encode):
        return obj.encode()
    if isinstance(obj, (str, bytes)):
        return repr(obj)
    if isinstance(obj, list):
        return '[' + ', '.join(map(encode, obj)) + ']'
    return str(obj)

class Color(Encode):
    WHITE: Color
    BLACK: Color
    RED:   Color
    GREEN: Color
    BLUE:  Color

    @classmethod
    def rgb(cls, r: int, g: int, b: int) -> 'Color':
        return cls(
            (r << 8) & 0xF800 |
            (g << 3) & 0x07E0 |
            (b >> 3) & 0x001F
        )

    def __int__(self):
        return int(self.value)

    def __init__(self, value: int | str = 'WHITE') -> None:
        self.value = value

    def encode(self) -> str:
        if isinstance(self.value, int): return str(self.value)
        else:                           return f'gint.C_{self.value}'

Color.WHITE = Color('WHITE')
Color.BLACK = Color('BLACK')
Color.RED   = Color('RED'  )
Color.GREEN = Color('GREEN')
Color.BLUE  = Color('BLUE' )


def draw_call(func: str):
    def inner(cls):
        fields = list(cls.__dataclass_fields__)
        def cls_encode(self) -> str:
            args = ', '.join(encode(getattr(self, field)) for field in fields)
            return f'{func}({args})'
        cls.encode = cls_encode
        return cls
    return inner

class DrawCall(Encode): pass

@draw_call('gint.dclear')
@dataclass
class DrawClear(DrawCall):
    color: Color = Color.WHITE

@draw_call('gint.dupdate')
@dataclass
class DrawUpdate(DrawCall):
    pass

@draw_call('gint.dpixel')
@dataclass
class DrawPixel(DrawCall):
    x: int
    y: int
    color: Color

@draw_call('gint.drect')
@dataclass
class DrawRect(DrawCall):
    x1: int
    y1: int
    x2: int
    y2: int
    color: Color

@draw_call('gint.drect_border')
@dataclass
class DrawRectBorder(DrawCall):
    x1: int
    y1: int
    x2: int
    y2: int
    fill_color: Color
    border_width: int
    border_color: Color

@draw_call('gint.dline')
@dataclass
class DrawLine(DrawCall):
    x1: int
    y1: int
    x2: int
    y2: int
    color: Color

@draw_call('gint.dhline')
@dataclass
class DrawHLine(DrawCall):
    y: int
    color: Color

@draw_call('gint.dvline')
@dataclass
class DrawVLine(DrawCall):
    x: int
    color: Color

@draw_call('gint.dcircle')
@dataclass
class DrawCircle(DrawCall):
    x: int
    y: int
    r: int
    fill: Color
    border: Color

@draw_call('gint.dellipse')
@dataclass
class DrawEllipse(DrawCall):
    x: int
    y: int
    r: int
    fill: Color
    border: Color

@draw_call('gint.dpoly')
@dataclass
class DrawPoly(DrawCall):
    vertices: list[int]
    fill: Color
    border: Color

@draw_call('gint.dtext')
@dataclass
class DrawText(DrawCall):
    x: int
    y: int
    fg: Color
    text: str

class RemoteScreen:
    def __init__(self, client: USBClient) -> None:
        self.client = client
        self.calls = list[DrawCall]()

    def get_width(self) -> int:
        return int(self.client.exec_all('print(gint.DWIDTH)').strip())

    def get_height(self) -> int:
        return int(self.client.exec_all('print(gint.DHEIGHT)').strip())

    def get_vram(self) -> int:
        match self.get_width():
            case 320: return 0x8C000000 # CP-400
            case 396: return 0x8C0F00A0 # CG-50
        raise ValueError('Unsupported model')

    def add(self, *calls: DrawCall) -> None:
        self.calls.extend(calls)

    def push(self) -> None:
        code = '\n'.join(map(encode, self.calls))
        self.calls = []
        self.client.exec_all(code)

if __name__ == '__main__':
    with USBClient.connect() as client:
        screen = RemoteScreen(client)
        screen.add(
            DrawClear(Color.BLUE),
            DrawLine(0, 0, 319, 519, Color.BLACK),
            DrawText(16, 16, Color.WHITE, 'Hello World!'),
            DrawUpdate(),
        )
        screen.push()
