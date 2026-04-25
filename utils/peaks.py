import numpy as np
from scipy.signal import find_peaks, peak_widths


def estimate_auto_prominence(y, factor=0.05):
    """
    Estimate an automatic prominence threshold from the signal range.

    Parameters
    ----------
    y : array-like
        Signal values.
    factor : float
        Fraction of signal range used as prominence threshold.

    Returns
    -------
    float
        Estimated prominence threshold.
    """
    y = np.asarray(y, dtype=float)

    if y.size == 0:
        return 0.0

    signal_range = np.max(y) - np.min(y)
    return max(signal_range * float(factor), 0.0)


def estimate_dx(x):
    """
    Estimate average x spacing.

    Parameters
    ----------
    x : array-like
        X-axis values.

    Returns
    -------
    float
        Mean spacing of x values.
    """
    x = np.asarray(x, dtype=float)

    if x.size < 2:
        return 1.0

    diffs = np.diff(x)
    diffs = diffs[np.isfinite(diffs)]

    if diffs.size == 0:
        return 1.0

    return float(np.mean(np.abs(diffs)))


def x_to_samples(x, value_x):
    """
    Convert a width/distance from x-units to samples.

    Parameters
    ----------
    x : array-like
        X-axis values.
    value_x : float or None
        Value in x-units (e.g. cm^-1).

    Returns
    -------
    float or None
        Value converted to samples.
    """
    if value_x is None:
        return None

    dx = estimate_dx(x)
    if dx <= 0:
        return None

    return max(float(value_x) / dx, 1.0)


def detect_peaks(
    x,
    y,
    prominence=None,
    prominence_factor=0.05,
    width_x=None,
    distance_x=None,
    height=None,
    rel_height=0.5,
):
    """
    Detect peaks in a Raman spectrum.

    Parameters
    ----------
    x : array-like
        Raman shift values.
    y : array-like
        Signal values.
    prominence : float or None
        Required prominence. If None, an automatic prominence is estimated.
    prominence_factor : float
        Factor for auto-prominence estimation.
    width_x : float, tuple, or None
        Peak width requirement in x-units (e.g. cm^-1).
        Can be a single minimum width or a tuple (min_width, max_width).
    distance_x : float or None
        Minimum peak distance in x-units.
    height : float or None
        Optional minimum peak height.
    rel_height : float
        Relative height for peak width calculation.

    Returns
    -------
    dict
        Peak detection result.
    """
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    if x.size != y.size:
        raise ValueError("x and y must have the same length")

    if x.size == 0:
        return {
            "indices": np.array([], dtype=int),
            "x": np.array([], dtype=float),
            "y": np.array([], dtype=float),
            "prominence_used": 0.0,
            "widths_samples": np.array([], dtype=float),
            "widths_x": np.array([], dtype=float),
            "left_ips": np.array([], dtype=float),
            "right_ips": np.array([], dtype=float),
            "left_x": np.array([], dtype=float),
            "right_x": np.array([], dtype=float),
            "properties": {},
        }

    if prominence is None:
        prominence_used = estimate_auto_prominence(y, factor=prominence_factor)
    else:
        prominence_used = abs(float(prominence))

    # convert width requirement from x-units to samples
    width_samples = None
    if width_x is not None:
        if isinstance(width_x, (tuple, list)) and len(width_x) == 2:
            width_samples = (
                x_to_samples(x, width_x[0]) if width_x[0] is not None else None,
                x_to_samples(x, width_x[1]) if width_x[1] is not None else None,
            )
        else:
            width_samples = x_to_samples(x, width_x)

    # convert distance from x-units to samples
    distance_samples = None
    if distance_x is not None:
        distance_samples = int(max(round(x_to_samples(x, distance_x)), 1))

    peaks, properties = find_peaks(
        y,
        prominence=prominence_used,
        width=width_samples,
        distance=distance_samples,
        height=height,
    )

    if peaks.size == 0:
        return {
            "indices": peaks,
            "x": np.array([], dtype=float),
            "y": np.array([], dtype=float),
            "prominence_used": prominence_used,
            "widths_samples": np.array([], dtype=float),
            "widths_x": np.array([], dtype=float),
            "left_ips": np.array([], dtype=float),
            "right_ips": np.array([], dtype=float),
            "left_x": np.array([], dtype=float),
            "right_x": np.array([], dtype=float),
            "properties": properties,
        }

    widths_samples, width_heights, left_ips, right_ips = peak_widths(
        y, peaks, rel_height=rel_height
    )

    dx = estimate_dx(x)
    widths_x = widths_samples * dx

    x_index = np.arange(len(x), dtype=float)
    left_x = np.interp(left_ips, x_index, x)
    right_x = np.interp(right_ips, x_index, x)

    return {
        "indices": peaks,
        "x": x[peaks],
        "y": y[peaks],
        "prominence_used": prominence_used,
        "widths_samples": widths_samples,
        "widths_x": widths_x,
        "width_heights": width_heights,
        "left_ips": left_ips,
        "right_ips": right_ips,
        "left_x": left_x,
        "right_x": right_x,
        "properties": properties,
    }