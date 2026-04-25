from __future__ import annotations

from typing import Dict, Any


def spectrum_to_xy(spectrum):
    """
    Convert RamanSpectrum object to x/y arrays.
    """
    return spectrum.wavenumbers, spectrum.intensities


def spectrum_to_dict(spectrum) -> Dict[str, Any]:
    """
    Convert RamanSpectrum to a serializable dict-like structure
    useful for Dash state handling.
    """
    return {
        "filename": spectrum.filename,
        "name": spectrum.spectrum_name or spectrum.filename,
        "is_blc": spectrum.is_blc,
        "x": list(spectrum.wavenumbers),
        "y": list(spectrum.intensities),
        "y_raw": list(spectrum.intensities_raw) if spectrum.intensities_raw is not None else None,
        "metadata": dict(spectrum.metadata),
        "history": list(spectrum.history),
    }


def spectra_to_dict(spectra):
    """
    Convert a list of RamanSpectrum objects to the format expected
    by overlay/stacked figure builders.
    """
    out = {}
    for sp in spectra:
        name = sp.spectrum_name or sp.filename
        out[name] = {
            "x": sp.wavenumbers,
            "y": sp.intensities,
            "metadata": sp.metadata,
            "filename": sp.filename,
            "is_blc": sp.is_blc,
        }
    return out
