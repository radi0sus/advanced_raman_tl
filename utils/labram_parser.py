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

# Binary IDs / LabSpec6 settings-directory parser
SETTINGS_PARENT = struct.pack("<I", 0x8716361)
VALUE_ID = struct.pack("<I", 0x7D6C61DB)
NUMERIC_ID = struct.pack("<I", 0x8736F70)
UNI_ID = struct.pack("<I", 0x7C696E75)

FMT_FLOAT64 = 0x05
FMT_INT32 = 0x04
FMT_STR7 = 0x07

DIR_ENTRY_SIZE = 24
NUMERIC_OFFSET = 16
_INT_TO_WN_GAP = 316

PARAM_TABLE = [
    (0x6F707865, "Acq. time (s)", False),
    (0x7D6363CE, "Accumulations", False),
    (0x6F6E61D7, "Range (cm-1)", False),
    (0x6CE1E0E6, "Windows", False),
    (0x3F415756, "Auto scanning", False),
    (0xECD7E53A, "Autofocus", False),
    (0x4C576339, "AutoExposure", False),
    (0x4F350544, "Spike filter", False),
    (0x696C65DD, "Delay time (s)", False),
    (0x6ED5D7CB, "Binning", False),
    (0xEA3A4A4E, "Readout mode", False),
    (0x6FD3D8CD, "DeNoise", False),
    (0xFC5AA4A0, "ICS correction", False),
    (0x5AB3995F, "Dark correction", False),
    (0x5A48F279, "Inst. Process", False),
    (0x6EDE5114, "Detector temp", False),
    (0xD9E15849, "Instrument", False),
    (0xDFE3D9C7, "Detector", False),
    (0xDBD3D737, "Objective", True),
    (0x7CC8E0D0, "Grating", True),
    (0x7C6CDBCB, "Filter", False),
    (0x6D7361DE, "Laser (nm)", True),
    (0x7C696C73, "Slit", True),
    (0x6D6C6F68, "Hole", True),
    (0xED344A4E, "Temperature", True),
    (0x6FDAECD8, "StageXY", False),
    (0x6F61EED8, "StageZ", False),
    (0x8000078, "X (µm)", True),
    (0x8000079, "Y (µm)", True),
    (0x800007A, "Z (µm)", True),
    (0xD9D9DEDA, "Full time", False),
]

_PARAM_LOOKUP = {pid: (name, use_num) for pid, name, use_num in PARAM_TABLE}


def _read_pointer_string(
    data: bytes,
    node_id_offset: int,
    length: int,
    search_window: int = 300,
) -> str | None:
    def _try_read(pos: int) -> str | None:
        raw = data[pos: pos + length].rstrip(b"\x00")
        if not raw:
            return None
        s = raw.decode("latin-1", errors="replace")
        return s if s.isprintable() else None

    search_end = node_id_offset + search_window

    uni_off = data.find(UNI_ID, node_id_offset, search_end)
    if uni_off != -1:
        pos = uni_off + 4
        while pos < uni_off + 24 and pos < len(data) and data[pos] == 0:
            pos += 1
        label_end = data.find(b"\x00", pos)
        if label_end != -1:
            val = _try_read(label_end + 1)
            if val:
                return val

    name_id = struct.pack("<I", 0x6D6D616E)
    namm_off = data.find(name_id, node_id_offset, node_id_offset + 32)
    if namm_off != -1:
        pool_start = namm_off + 16
        val = _try_read(pool_start)
        if val:
            return val

    return None


def _read_l6s_node(data: bytes, node_id_offset: int):
    fmt_off = node_id_offset - 8
    if fmt_off < 0 or node_id_offset + 16 > len(data):
        return None

    fmt = data[fmt_off]
    pay_off = node_id_offset + 8

    if fmt == FMT_FLOAT64:
        return struct.unpack_from("<d", data, pay_off)[0]

    if fmt == FMT_INT32:
        return struct.unpack_from("<i", data, pay_off)[0]

    if fmt == FMT_STR7:
        raw = data[pay_off: pay_off + 8]
        s = raw.split(b"\x00")[0].decode("latin-1", errors="replace")
        if s and s.isprintable():
            return s

        length = struct.unpack_from("<I", raw, 4)[0]
        if 1 <= length <= 64:
            return _read_pointer_string(data, node_id_offset, length)

    return None


def _parse_l6s_metadata_raw(data: bytes) -> dict:
    sp_off = data.find(SETTINGS_PARENT)
    if sp_off == -1:
        return {}

    first_pid = struct.pack("<I", PARAM_TABLE[0][0])
    dir_start = data.find(first_pid, sp_off, sp_off + 200)
    if dir_start == -1:
        return {}

    dir_ids = [
        struct.unpack_from("<I", data, dir_start + i * DIR_ENTRY_SIZE)[0]
        for i in range(len(PARAM_TABLE))
    ]

    content_start = dir_start + len(PARAM_TABLE) * DIR_ENTRY_SIZE
    content_end = min(content_start + 5000, len(data))

    value_nodes = []
    numeric_nodes = []

    pos = content_start
    while pos < content_end:
        vp = data.find(VALUE_ID, pos, content_end)
        if vp == -1:
            break
        value_nodes.append(_read_l6s_node(data, vp))
        pos = vp + 1

    pos = content_start
    while pos < content_end:
        np = data.find(NUMERIC_ID, pos, content_end)
        if np == -1:
            break
        numeric_nodes.append(_read_l6s_node(data, np))
        pos = np + 1

    meta = {}
    for i, pid in enumerate(dir_ids):
        if pid not in _PARAM_LOOKUP:
            continue

        name, use_num = _PARAM_LOOKUP[pid]

        if use_num and i >= NUMERIC_OFFSET:
            ni = i - NUMERIC_OFFSET
            val = numeric_nodes[ni] if ni < len(numeric_nodes) else None
            if val is not None and isinstance(val, float) and abs(val) < 1e9:
                meta[name] = val
                continue

        val = value_nodes[i] if i < len(value_nodes) else None
        if val is not None:
            meta[name] = val

    text = data.decode("latin-1", errors="replace")
    m = re.search(r"\b\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}\b", text)
    if m:
        meta["Acquired"] = m.group(0)
    else:
        m = re.search(r"\b\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}\b", text)
        if m:
            meta["Acquired"] = m.group(0)

    return meta


def _extract_l6s_metadata(data: bytes) -> dict:
    raw = _parse_l6s_metadata_raw(data)
    meta = {}

    if "Laser (nm)" in raw:
        val = raw["Laser (nm)"]
        if isinstance(val, float) and val.is_integer():
            val = int(val)
        meta["Laser"] = _meta_entry(val, "nm")

    if "Grating" in raw:
        val = raw["Grating"]
        if isinstance(val, float) and val.is_integer():
            val = int(val)
        meta["Grating"] = _meta_entry(val, "g/mm")

    if "Filter" in raw:
        meta["Filter"] = _meta_entry(raw["Filter"])

    if "Acq. time (s)" in raw:
        val = raw["Acq. time (s)"]
        if isinstance(val, float) and val.is_integer():
            val = int(val)
        meta["Acq. time"] = _meta_entry(val, "s")

    if "Accumulations" in raw:
        meta["Accumulations"] = _meta_entry(raw["Accumulations"])

    if "Windows" in raw:
        meta["Windows"] = _meta_entry(raw["Windows"])

    if "Slit" in raw:
        val = raw["Slit"]
        if isinstance(val, float) and val.is_integer():
            val = int(val)
        meta["Slit"] = _meta_entry(val, "µm")

    if "Hole" in raw:
        val = raw["Hole"]
        if isinstance(val, float) and val.is_integer():
            val = int(val)
        meta["Hole"] = _meta_entry(val, "µm")

    if "Instrument" in raw:
        meta["Instrument"] = _meta_entry(raw["Instrument"])

    if "Detector" in raw:
        meta["Detector"] = _meta_entry(raw["Detector"])

    if "Acquired" in raw:
        meta["Acquired"] = _meta_entry(raw["Acquired"])

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