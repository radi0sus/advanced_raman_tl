"""
labram_parser.py
================
Raman spectrum parser for:
  .xml   — Horiba LabSpec LSX XML export
  .txt   — two-column text file: wavenumber <tab/space> intensity
  .l6s   — LabSpec6 binary file (spectrum only, no metadata extraction)

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
        return self.metadata.get("Spectrum Name")

    @property
    def laser_nm(self) -> Optional[float]:
        try:
            return float(self.metadata["Laser Wavelength (nm)"])
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def acq_time_s(self) -> Optional[float]:
        try:
            return float(self.metadata["Acq. time (s)"])
        except (KeyError, ValueError, TypeError):
            return None

    @property
    def accumulations(self) -> Optional[int]:
        try:
            return int(self.metadata["Accumulations"])
        except (KeyError, ValueError, TypeError):
            return None
            
    @property
    def display_name(self) -> str:
        try:
            return self.metadata.get("Spectrum Name") or self.filename
        except (KeyError, ValueError, TypeError):
            return None
            

    def __repr__(self) -> str:
        n = len(self.wavenumbers)
        rng = f"{self.wavenumbers[0]:.1f}–{self.wavenumbers[-1]:.1f} cm-1" if n else "?"
        blc = " [BLC]" if self.is_blc else ""
    
        def meta(key: str, default: str = "?") -> str:
            v = self.metadata.get(key)
            return str(v) if v not in (None, "") else default
    
        return (
            f"RamanSpectrum('{self.filename}'{blc}, "
            f"n={n}, "
            f"range={rng}, "
            f"name={meta('Spectrum Name')}, "
            f"laser={meta('Laser Wavelength (nm)')} nm, "
            f"acq={meta('Acq. time (s)')} s x {meta('Accumulations')}, "
            f"grating={meta('Grating')}, "
            f"filter={meta('Filter')}, "
            f"slit={meta('Slit')}, "
            f"hole={meta('Hole')}, "
            f"instrument={meta('Instrument Name')}, "
            f"detector={meta('Detector Name')})"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

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


def _normalize_metadata(meta: dict) -> dict:
    out = {}

    def pick(dst, *keys):
        for k in keys:
            if k in meta and meta[k] not in ("", None):
                out[dst] = meta[k]
                return

    pick("Spectrum Name", "Spectrum Name", "Title", "Spectrum", "Name")
    pick("Acq. time (s)", "Acq. time (s)", "Acq. time")
    pick("Accumulations", "Accumulations")
    pick("Spike filter", "Spike filter")
    pick("Instrument Name", "Instrument Name", "Instrument")
    pick("Detector Name", "Detector Name", "Detector")
    pick("Grating", "Grating")
    pick("Filter", "Filter")
    pick("Laser Wavelength (nm)", "Laser Wavelength (nm)", "Laser (nm)", "Laser")
    pick("Slit", "Slit")
    pick("Hole", "Hole")
    pick("Full time(mm:ss)", "Full time(mm:ss)", "Full time")
    pick("Acquired", "Acquired", "Date")

    return out

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
            metadata["Spectrum Name"] = display or ""
        elif name == "Date":
            metadata["Acquired"] = display or ""
        elif name == "Laser (nm)":
            metadata["Laser Wavelength (nm)"] = numeric if numeric is not None else _extract_number(display)
        elif name in ("Acq. time (s)", "Accumulations", "Grating", "Slit", "Hole"):
            metadata[name] = numeric if numeric is not None else _extract_number(display)
        elif name == "Instrument":
            metadata["Instrument Name"] = display or ""
        elif name == "Detector":
            metadata["Detector Name"] = display or ""
        elif name == "Spike filter":
            metadata["Spike filter"] = display or ""
        elif name == "Filter":
            metadata["Filter"] = display or ""
        elif name == "Full time(mm:ss)":
            metadata["Full time(mm:ss)"] = display or ""

    metadata = _normalize_metadata(metadata)

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
# L6S parser (spectrum and some metadata)
# ─────────────────────────────────────────────────────────────────────────────

_INT_TO_WN_GAP = 316

def _extract_l6s_metadata_known_values(data: bytes) -> dict:
    text = data.decode("latin-1", errors="replace")
    meta = {}

    KNOWN = {
        "Instrument Name": ["LabRAM"],
        "Detector Name": ["Andor CCD"],
        "Grating": ["600", "1800"],
        "Filter": ["0.1%", "1%", "10%", "25%", "50%", "100%"],
        "Laser Wavelength (nm)": ["457", "457.0", "532", "532.0", "532.15", "633", "632.81"],
        "Full time(mm:ss)": [],
    }

    def first_match(patterns):
        for p in patterns:
            if p in text:
                return p
        return None

    # direct strings
    inst = first_match(KNOWN["Instrument Name"])
    if inst:
        meta["Instrument"] = inst

    det = first_match(KNOWN["Detector Name"])
    if det:
        meta["Detector Name"] = det

    # context-based text search
    def find_near(label: str, candidates: list[str], window: int = 180) -> Optional[str]:
        idx = text.find(label)
        if idx == -1:
            return None
        block = text[max(0, idx - 80): idx + window]
        for c in candidates:
            if c in block:
                return c
        return None

    g = find_near("Grating", KNOWN["Grating"])
    if g:
        meta["Grating"] = int(float(g))

    f = find_near("Filter", KNOWN["Filter"])
    if f:
        meta["Filter"] = f

    # Laser: first try exact context
    l = find_near("Laser", KNOWN["Laser Wavelength (nm)"], window=220)
    if l:
        meta["Laser Wavelength (nm)"] = float(l)
    else:
        # fallback: accept only known laser values anywhere
        for cand in KNOWN["Laser Wavelength (nm)"]:
            if cand in text:
                try:
                    val = float(cand)
                except ValueError:
                    continue
                # prefer non-integer more specific values if present
                if val in (457.0, 532.15, 632.81, 633.0, 532.0):
                    meta["Laser Wavelength (nm)"] = val
                    break

    # Full time
    m = re.search(r"\b\d{1,2}:\d{2}\b", text)
    if m:
        meta["Full time(mm:ss)"] = m.group(0)

    # Acquired
    m = re.search(r"\b\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}\b", text)
    if m:
        meta["Acquired"] = m.group(0)
    else:
        m = re.search(r"\b\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}\b", text)
        if m:
            meta["Acquired"] = m.group(0)

    # Spectrum name: use a conservative pattern
    m = re.search(r"\b[A-Z]_\d{2,}\b", text)
    if m:
        meta["Spectrum Name"] = m.group(0)

    return _normalize_metadata(meta)
    

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
                
    metadata = _extract_l6s_metadata_known_values(data)
    
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


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    wanted = [
        "Spectrum Name",
        "Acq. time (s)",
        "Accumulations",
        "Spike filter",
        "Instrument Name",
        "Detector Name",
        "Grating",
        "Filter",
        "Laser Wavelength (nm)",
        "Slit",
        "Hole",
        "Full time(mm:ss)",
        "Acquired",
    ]

    if len(sys.argv) < 2:
        print("Usage: python labram_parser.py <file1> [file2 ...]")
        raise SystemExit(1)

    for arg in sys.argv[1:]:
        sp = load(arg)

        print("=" * 72)
        print(sp)
        for key in wanted:
            print(f"{key}: {sp.metadata.get(key, '')}")
            
        try:
            wn, it = sp.wavenumbers, sp.intensities
            print(f"  WN  : {wn[0]:.3f} ... {wn[-1]:.3f}  (N={len(wn)})")
            print(f"  INT : min={min(it):.2f}  max={max(it):.2f}")
            if sp.intensities_raw is not None:
                ir = sp.intensities_raw
                print(f"  RAW : min={min(ir):.2f}  max={max(ir):.2f}")
            if sp.metadata:
                print("  Metadaten:")
                for k, v in sorted(sp.metadata.items()):
                    if not k.startswith('_') and v is not None:
                        print(f"    {k:35s}: {v}")
            if sp.history:
                last = sp.history[-1]
                print(f"  Historie: {len(sp.history)} Einträge  "
                      f"(zuletzt: {last['action']} {last['timestamp']})")
        except Exception as exc:
            import traceback
            print(f"  FEHLER: {exc}")
            traceback.print_exc()