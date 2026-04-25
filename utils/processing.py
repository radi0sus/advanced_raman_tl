import numpy as np

from utils.baseline import baseline_arpls, baseline_snip, subtract_baseline
from utils.smoothing import smooth_signal
from utils.peaks import detect_peaks


def nearest_index(x, value):
    x = np.asarray(x, dtype=float)
    return int(np.argmin(np.abs(x - value)))


def crop_spectrum(x, y, xmin=None, xmax=None):
    """
    Crop spectrum to [xmin, xmax].
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    if x.size != y.size:
        raise ValueError("x and y must have the same length")

    start = 0 if xmin is None else nearest_index(x, xmin)
    stop = len(x) if xmax is None else nearest_index(x, xmax) + 1

    if start >= stop:
        raise ValueError("Invalid crop range: xmin must be smaller than xmax")

    return x[start:stop], y[start:stop]


def process_spectrum(
    x,
    y,
    *,
    xmin=None,
    xmax=None,
    x_shift=0.0,
    intensity_offset=0.0,
    intensity_scale=1.0,
    baseline_method="arpls",
    baseline_params=None,
    smoothing_method="whittaker",
    smoothing_params=None,
    peak_prominence=None,
    peak_prominence_factor=0.05,
    peak_width=None,
    peak_distance=None,
    peak_height=None,
    peak_rel_height=0.5,
):
    """
    Full Raman processing pipeline for one spectrum.

    Parameters
    ----------
    x, y : array-like
        Spectrum data.
    xmin, xmax : float or None
        Crop range.
    x_shift : float
        Shift applied to x-axis.
    intensity_offset : float
        Constant offset added to intensities.
    intensity_scale : float
        Multiplicative factor for intensities.
    baseline_method : str
        Currently supports 'arpls'.
    baseline_params : dict or None
        Parameters for baseline correction.
    smoothing_method : str
        Smoothing method, e.g. 'whittaker' or 'savgol'.
    smoothing_params : dict or None
        Parameters for smoothing.
    peak_prominence : float or None
        Peak prominence in intensity units.
    peak_prominence_factor : float
        Auto-prominence factor if prominence is None.
    peak_width : float, tuple, or None
        Peak width requirement in x-units (cm^-1).
    peak_distance : float or None
        Minimum peak distance in x-units (cm^-1).
    peak_height : float or None
        Optional minimum peak height.
    peak_rel_height : float
        Relative height for width calculation.

    Returns
    -------
    dict
        Processed spectrum data and peak metadata.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    if x.size != y.size:
        raise ValueError("x and y must have the same length")

    baseline_params = baseline_params or {}
    smoothing_params = smoothing_params or {}

    x_proc = x + float(x_shift)
    y_proc = y * abs(float(intensity_scale)) + float(intensity_offset)

    x_crop, y_crop = crop_spectrum(x_proc, y_proc, xmin=xmin, xmax=xmax)

    baseline_method = baseline_method.lower()
    if baseline_method == "arpls":
        baseline = baseline_arpls(y_crop, **baseline_params)
    elif baseline_method == "snip":
        baseline = baseline_snip(y_crop, **baseline_params)
    else:
        raise ValueError(f"Unknown baseline method: {baseline_method}")

    corrected = subtract_baseline(y_crop, baseline)
    smoothed = smooth_signal(corrected, method=smoothing_method, **smoothing_params)

    peak_result = detect_peaks(
        x_crop,
        smoothed,
        prominence=peak_prominence,
        prominence_factor=peak_prominence_factor,
        width_x=peak_width,
        distance_x=peak_distance,
        height=peak_height,
        rel_height=peak_rel_height,
    )

    return {
        "x": x_crop,
        "raw": y_crop,
        "baseline": baseline,
        "corrected": corrected,
        "smoothed": smoothed,
        "peaks": peak_result,
    }