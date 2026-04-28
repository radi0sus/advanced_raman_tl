"""
parser.py
=========
Raman spectrum parser for:
  .xml   — Horiba LabSpec LSX XML export
  .txt   — two-column text file: wavenumber <tab/space> intensity
  .l6s   — LabSpec6 binary file

Metadata are returned in structured form:

    metadata = {
        "Laser": {"value": 532.15, "unit": "nm"},
        "Grating": {"value": 600, "unit": "g/mm"},
        ...
    }

No external dependencies.
"""

from __future__ import annotations

import re
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# ─────────────────────────────────────────────────────────────────────────────
# Data model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RamanSpectrum:
    filename: str
    is_blc: bool
    wavenumbers: list[float]
    intensities: list[float]
    intensities_raw: Optional[list[float]] = None
    metadata: dict = field(default_factory=dict)
    history: list = field(default_factory=list)

    @property
    def spectrum_name(self) -> Optional[str]:
        return _meta_value(self.metadata, "Name")

    @property
    def laser_nm(self) -> Optional[float]:
        try:
            value = _meta_value(self.metadata, "Laser")
            return float(value) if value is not None else None
        except (ValueError, TypeError):
            return None

    @property
    def acq_time_s(self) -> Optional[float]:
        try:
            value = _meta_value(self.metadata, "Acq. time")
            return float(value) if value is not None else None
        except (ValueError, TypeError):
            return None

    @property
    def accumulations(self) -> Optional[int]:
        try:
            value = _meta_value(self.metadata, "Accumulations")
            return int(value) if value is not None else None
        except (ValueError, TypeError):
            return None

    def __repr__(self) -> str:
        n = len(self.wavenumbers)
        rng = f"{self.wavenumbers[0]:.1f}–{self.wavenumbers[-1]:.1f} cm-1" if n else "?"
        blc = " [BLC]" if self.is_blc else ""

        def meta(key: str, default: str = "?") -> str:
            return _meta_text(self.metadata, key, default)

        return (
            f"RamanSpectrum('{self.filename}'{blc}, "
            f"n={n}, "
            f"range={rng}, "
            f"name={meta('Name')}, "
            f"laser={meta('Laser')}, "
            f"acq={meta('Acq. time')} x {meta('Accumulations')}, "
            f"grating={meta('Grating')}, "
            f"filter={meta('Filter')}, "
            f"slit={meta('Slit')}, "
            f"hole={meta('Hole')}, "
            f"instrument={meta('Instrument')}, "
            f"detector={meta('Detector')})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Metadata helpers
# ─────────────────────────────────────────────────────────────────────────────

def _meta_entry(value, unit: str = "") -> dict:
    return {"value": value, "unit": unit}


def _meta_value(metadata: dict, key: str):
    entry = metadata.get(key)
    if not isinstance(entry, dict):
        return None
    return entry.get("value")


def _meta_text(metadata: dict, key: str, default: str = "") -> str:
    entry = metadata.get(key)
    if not isinstance(entry, dict):
        return default

    value = entry.get("value")
    unit = entry.get("unit", "")

    if value in (None, ""):
        return default

    text = f"{value} {unit}".strip()
    return text or default


def _coerce(value: str) -> object:
    v = str(value).strip()
    try:
        return int(v)
    except ValueError:
        pass
    try:
        return float(v)
    except ValueError:
        pass
    return v


def _extract_number(value: str | None) -> Optional[float]:
    if value is None:
        return None
    m = re.search(r"[-+]?\d+(?:\.\d+)?", str(value).replace(",", "."))
    if not m:
        return None
    num = float(m.group(0))
    return int(num) if num.is_integer() else num


# ─────────────────────────────────────────────────────────────────────────────
# XML parser
# ─────────────────────────────────────────────────────────────────────────────

_LSX_ID_NAME = "0x6d6d616e"
_LSX_ID_VALUE = "0x7d6c61db"
_LSX_ID_NUMERIC = "0x8736f70"
_LSX_ID_WN = "0x7d6cd4db"


def _parse_xml(path: Path) -> RamanSpectrum:
    tree = ET.parse(path)
    root = tree.getroot()

    matrix = root.find("LSX_Matrix")
    row = matrix.find("LSX_Row") if matrix is not None else None
    if row is None or not row.text:
        raise ValueError("No spectral intensity data found in LSX_Matrix")
    intensities = [float(x) for x in row.text.split()]

    wavenumbers = []
    for lsx in root.iter("LSX"):
        if (
            lsx.get("Format") == "6"
            and lsx.get("ID", "").lower() == _LSX_ID_WN
            and lsx.text
        ):
            vals = [float(x) for x in lsx.text.split()]
            if len(vals) == len(intensities):
                wavenumbers = vals
                break

    if not wavenumbers:
        raise ValueError("No matching wavenumber axis found")

    metadata = {}
    history = []

    for node in root.iter("LSX"):
        if node.get("Format") != "9":
            continue

        name = None
        display = None
        numeric = None

        for child in list(node):
            cid = child.get("ID", "").lower()
            text = (child.text or "").strip()

            if cid == _LSX_ID_NAME:
                name = text
            elif cid == _LSX_ID_VALUE:
                display = text
            elif cid == _LSX_ID_NUMERIC:
                numeric = _coerce(text)

        if not name:
            continue

        if name.startswith(("Base:", "Math:", "Filter:", "Acquired")):
            history.append({"action": name, "timestamp": display or ""})
            continue

        if name == "Title":
            metadata["Name"] = _meta_entry(display or "")
        elif name == "Date":
            metadata["Acquired"] = _meta_entry(display or "")
        elif name == "Laser (nm)":
            val = numeric if numeric is not None else _extract_number(display)
            if val is not None:
                metadata["Laser"] = _meta_entry(val, "nm")
        elif name == "Acq. time (s)":
            val = numeric if numeric is not None else _extract_number(display)
            if val is not None:
                metadata["Acq. time"] = _meta_entry(val, "s")
        elif name == "Accumulations":
            val = numeric if numeric is not None else _extract_number(display)
            if val is not None:
                metadata["Accumulations"] = _meta_entry(val)
        elif name == "Windows":
            val = numeric if numeric is not None else _extract_number(display)
            if val is not None:
                metadata["Windows"] = _meta_entry(val)
        elif name == "Grating":
            val = numeric if numeric is not None else _extract_number(display)
            if val is not None:
                metadata["Grating"] = _meta_entry(val, "g/mm")
        elif name == "Filter":
            metadata["Filter"] = _meta_entry(display or "")
        elif name == "Slit":
            val = numeric if numeric is not None else _extract_number(display)
            if val is not None:
                metadata["Slit"] = _meta_entry(val, "µm")
        elif name == "Hole":
            val = numeric if numeric is not None else _extract_number(display)
            if val is not None:
                metadata["Hole"] = _meta_entry(val, "µm")
        elif name == "Instrument":
            metadata["Instrument"] = _meta_entry(display or "")
        elif name == "Detector":
            metadata["Detector"] = _meta_entry(display or "")
        elif name == "Spike filter":
            pass
        elif name == "Full time(mm:ss)":
            pass

    return RamanSpectrum(
        filename=path.name,
        is_blc="_blc" in path.stem.lower(),
        wavenumbers=wavenumbers,
        intensities=intensities,
        metadata=metadata,
        history=history,
    )


# ─────────────────────────────────────────────────────────────────────────────
# TXT parser
# ─────────────────────────────────────────────────────────────────────────────

def _parse_txt(path: Path) -> RamanSpectrum:
    wavenumbers = []
    intensities = []

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue

            parts = re.split(r"[;\t ]+", s)
            parts = [p for p in parts if p]
            if len(parts) < 2:
                continue

            try:
                x = float(parts[0].replace(",", "."))
                y = float(parts[1].replace(",", "."))
            except ValueError:
                continue

            wavenumbers.append(x)
            intensities.append(y)

    if not wavenumbers:
        raise ValueError("No two-column spectral data found in TXT file")

    return RamanSpectrum(
        filename=path.name,
        is_blc="_blc" in path.stem.lower(),
        wavenumbers=wavenumbers,
        intensities=intensities,
        metadata={},
        history=[],
    )


# ─────────────────────────────────────────────────────────────────────────────
# L6S parser
# ─────────────────────────────────────────────────────────────────────────────

# Binary IDs
VALUE_ID = struct.pack("<I", 0x7D6C61DB)
NAME_ID = struct.pack("<I", 0x6D6D616E)
NUMERIC_ID = struct.pack("<I", 0x8736F70)
UNI_ID = struct.pack("<I", 0x7C696E75)

FMT_FLOAT64 = 0x05
FMT_INT32 = 0x04
FMT_STR = 0x07

_INT_TO_WN_GAP = 316


def _find_all(data: bytes, needle: bytes) -> list[int]:
    positions = []
    pos = 0
    while True:
        idx = data.find(needle, pos)
        if idx == -1:
            break
        positions.append(idx)
        pos = idx + 1
    return positions


def _read_value_at(data: bytes, value_id_offset: int):
    fmt_offset = value_id_offset - 8
    if fmt_offset < 0 or value_id_offset + 16 > len(data):
        return None, None

    fmt = data[fmt_offset]
    payload_offset = value_id_offset + 8

    if fmt == FMT_FLOAT64:
        val = struct.unpack_from("<d", data, payload_offset)[0]
        return val, FMT_FLOAT64
    elif fmt == FMT_INT32:
        val = struct.unpack_from("<i", data, payload_offset)[0]
        return val, FMT_INT32
    elif fmt == FMT_STR:
        raw = data[payload_offset: payload_offset + 8]
        s = raw.split(b"\x00")[0].decode("latin-1", errors="replace")
        return s, FMT_STR
    else:
        return None, fmt


def _find_preceding_value(
    data: bytes,
    label_offset: int,
    expected_fmt: int,
    max_lookback: int = 200,
):
    search_start = max(0, label_offset - max_lookback)
    candidates = _find_all(data[search_start:label_offset], VALUE_ID)

    for rel in reversed(candidates):
        abs_pos = search_start + rel
        val, fmt = _read_value_at(data, abs_pos)
        if fmt == expected_fmt and val is not None:
            return val

    return None


def _find_named_block(data: bytes, label_str: str) -> tuple[int, int] | tuple[None, None]:
    label_bytes = label_str.encode("latin-1") + b"\x00"

    pos = 0
    while True:
        npos = data.find(NAME_ID, pos)
        if npos == -1:
            break
        if data[npos + 8:npos + 8 + len(label_bytes)] == label_bytes:
            data_start = npos + 8 + len(label_bytes)
            uni_off = data.find(UNI_ID, data_start, data_start + 200)
            block_end = uni_off if uni_off != -1 else data_start + 150
            return data_start, block_end
        pos = npos + 1

    label_off = data.find(label_bytes)
    if label_off == -1:
        return None, None

    uni_off = None
    pos = max(0, label_off - 200)
    while pos < label_off:
        idx = data.find(UNI_ID, pos, label_off)
        if idx == -1:
            break
        uni_off = idx
        pos = idx + 1
    if uni_off is None:
        return None, None

    namm_off = None
    pos = max(0, uni_off - 300)
    while pos < uni_off:
        idx = data.find(NAME_ID, pos, uni_off)
        if idx == -1:
            break
        namm_off = idx
        pos = idx + 1
    if namm_off is None:
        return None, None

    data_start = namm_off + 16
    return data_start, uni_off


def _block_float(data: bytes, label_str: str) -> float | None:
    data_start, block_end = _find_named_block(data, label_str)
    if data_start is None:
        return None

    for needle in (NUMERIC_ID, VALUE_ID):
        pos = data_start
        while pos < block_end:
            idx = data.find(needle, pos, block_end)
            if idx == -1:
                break
            val, fmt = _read_value_at(data, idx)
            if fmt == FMT_FLOAT64:
                return val
            pos = idx + 1

    return None


def _block_str(data: bytes, label_str: str) -> str | None:
    data_start, block_end = _find_named_block(data, label_str)
    if data_start is None:
        return None

    pos = data_start
    while pos < block_end:
        idx = data.find(VALUE_ID, pos, block_end)
        if idx == -1:
            break
        val, fmt = _read_value_at(data, idx)
        if fmt == FMT_STR and val:
            return val
        pos = idx + 1

    return None


def _extract_l6s_metadata(data: bytes) -> dict:
    text = data.decode("latin-1", errors="replace")
    meta = {}

    acq_label_offset = data.find(b"Acq. time (s)\x00")
    if acq_label_offset != -1:
        val = _find_preceding_value(data, acq_label_offset, FMT_FLOAT64)
        if val is not None:
            meta["Acq. time"] = _meta_entry(
                int(val) if float(val).is_integer() else val,
                "s",
            )

    acc_label_offset = data.find(b"Accumulations\x00")
    if acc_label_offset != -1:
        val = _find_preceding_value(data, acc_label_offset, FMT_INT32)
        if val is not None:
            meta["Accumulations"] = _meta_entry(val)

    win_label_offset = data.find(b"Windows\x00")
    if win_label_offset != -1:
        val = _find_preceding_value(data, win_label_offset, FMT_INT32)
        if val is not None:
            meta["Windows"] = _meta_entry(val)

    val = _block_float(data, "Laser (nm)")
    if val is not None:
        meta["Laser"] = _meta_entry(val, "nm")

    val = _block_float(data, "Grating")
    if val is not None:
        meta["Grating"] = _meta_entry(
            int(val) if float(val).is_integer() else val,
            "g/mm",
        )

    val = _block_str(data, "Filter")
    if val is not None:
        meta["Filter"] = _meta_entry(val)

    val = _block_float(data, "Slit")
    if val is not None:
        meta["Slit"] = _meta_entry(
            int(val) if float(val).is_integer() else val,
            "µm",
        )

    val = _block_float(data, "Hole")
    if val is not None:
        meta["Hole"] = _meta_entry(
            int(val) if float(val).is_integer() else val,
            "µm",
        )

    if b"LabRAM" in data:
        meta["Instrument"] = _meta_entry("LabRAM")

    if b"Andor CCD" in data:
        meta["Detector"] = _meta_entry("Andor CCD")

    m = re.search(r"\b\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}\b", text)
    if m:
        meta["Acquired"] = _meta_entry(m.group(0))
    else:
        m = re.search(r"\b\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}\b", text)
        if m:
            meta["Acquired"] = _meta_entry(m.group(0))

    return meta


def _find_mean_tags(data: bytes) -> list[int]:
    positions = []
    pos = 0
    while True:
        idx = data.find(b"mean\x00\x00\x00\x00", pos)
        if idx == -1:
            break
        positions.append(idx)
        pos = idx + 1
    return positions


def _find_wn_block(data: bytes, search_from: int) -> tuple[int, int]:
    end = min(search_from + 600, len(data) - 8)
    for i in range(search_from, end, 4):
        v1 = struct.unpack_from("<f", data, i)[0]
        v2 = struct.unpack_from("<f", data, i + 4)[0]
        if 10 < v1 < 4000 and 10 < v2 < 4000 and v2 > v1 - 5:
            n = 2
            while i + n * 4 + 4 <= len(data):
                v = struct.unpack_from("<f", data, i + n * 4)[0]
                if not (10 < v < 4000):
                    break
                n += 1
            return i, n
    raise ValueError(f"No wavenumber block found from offset {search_from}")


def _read_float32_block(data: bytes, offset: int, n: int) -> list[float]:
    return list(struct.unpack_from(f"<{n}f", data, offset))


def _read_int_block(data: bytes, wn_start: int, n: int) -> list[float]:
    int_end = wn_start - _INT_TO_WN_GAP
    int_start = int_end - n * 4
    if int_start < 0:
        raise ValueError(f"Invalid intensity block offset: {int_start}")
    return _read_float32_block(data, int_start, n)


def _parse_l6s(path: Path) -> RamanSpectrum:
    data = path.read_bytes()
    is_blc = "_blc" in path.stem.lower()

    means = _find_mean_tags(data)
    if not means:
        raise ValueError("No 'mean' tags found — unknown .l6s format")

    wn_start, n = _find_wn_block(data, means[0] + 12)
    wavenumbers = _read_float32_block(data, wn_start, n)
    intensities = _read_int_block(data, wn_start, n)

    intensities_raw = None
    if is_blc and len(means) >= 2:
        mean1 = means[1]
        try:
            wn2_start, n2 = _find_wn_block(data, mean1 + 12)
            if n2 == n:
                intensities_raw = _read_int_block(data, wn2_start, n2)
        except ValueError:
            i2_end = mean1 - 4
            i2_start = i2_end - n * 4
            if i2_start >= 0:
                intensities_raw = _read_float32_block(data, i2_start, n)

    metadata = _extract_l6s_metadata(data)

    return RamanSpectrum(
        filename=path.name,
        is_blc=is_blc,
        wavenumbers=wavenumbers,
        intensities=intensities,
        intensities_raw=intensities_raw,
        metadata=metadata,
        history=[],
    )


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def load(path: str | Path) -> RamanSpectrum:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    sfx = path.suffix.lower()
    if sfx == ".xml":
        return _parse_xml(path)
    if sfx == ".txt":
        return _parse_txt(path)
    if sfx == ".l6s":
        return _parse_l6s(path)

    raise ValueError(f"Unsupported file format: {sfx!r} (expected .xml, .txt or .l6s)")