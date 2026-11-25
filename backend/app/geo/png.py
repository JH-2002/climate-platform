"""Codificador PNG mínimo (RGB ou RGBA de 8 bits), só com a biblioteca padrão.

Evita uma dependência de imagem só para os blocos de relevo e o relevo sombreado.
"""

from __future__ import annotations

import struct
import zlib

import numpy as np
import numpy.typing as npt

_SIGNATURE = b"\x89PNG\r\n\x1a\n"


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
    )


def encode_png(pixels: npt.NDArray[np.uint8], level: int = 6) -> bytes:
    """`pixels` com forma (altura, largura, 3 ou 4)."""
    if pixels.ndim != 3 or pixels.shape[2] not in (3, 4) or pixels.dtype != np.uint8:
        raise ValueError("esperado uint8 com forma (altura, largura, 3 ou 4)")
    height, width, channels = pixels.shape
    color_type = 2 if channels == 3 else 6
    header = struct.pack(">IIBBBBB", width, height, 8, color_type, 0, 0, 0)
    rows = np.zeros((height, 1 + width * channels), dtype=np.uint8)  # filtro 0 por linha
    rows[:, 1:] = pixels.reshape(height, width * channels)
    return (
        _SIGNATURE
        + _chunk(b"IHDR", header)
        + _chunk(b"IDAT", zlib.compress(rows.tobytes(), level))
        + _chunk(b"IEND", b"")
    )


def decode_png(data: bytes) -> npt.NDArray[np.uint8]:
    """Decodifica o que `encode_png` gera (filtro 0); usado nos testes."""
    if data[:8] != _SIGNATURE:
        raise ValueError("não é PNG")
    pos = 8
    idat = b""
    width = height = channels = 0
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            width, height, _, color_type = struct.unpack(">IIBB", body[:10])
            channels = 3 if color_type == 2 else 4
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    raw = np.frombuffer(zlib.decompress(idat), dtype=np.uint8).reshape(height, -1)
    if np.any(raw[:, 0] != 0):
        raise ValueError("só o filtro 0 é suportado")
    return raw[:, 1:].reshape(height, width, channels).copy()
