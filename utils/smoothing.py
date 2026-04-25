import numpy as np
from scipy import sparse
from scipy.sparse.linalg import spsolve
from scipy.signal import savgol_filter


def whittaker_smooth(y, lam=1.0, d=2):
    """
    Whittaker smoothing.

    Parameters
    ----------
    y : array-like
        Input signal.
    lam : float
        Smoothing parameter.
    d : int
        Order of differences.

    Returns
    -------
    np.ndarray
        Smoothed signal.
    """
    y = np.asarray(y, dtype=float)
    n = len(y)

    if n <= d:
        return y.copy()

    e = sparse.eye(n, format="csc")
    diff = e[1:] - e[:-1]
    for _ in range(d - 1):
        diff = diff[1:] - diff[:-1]

    a = sparse.eye(n, format="csc") + lam * (diff.T @ diff)
    return spsolve(a, y)


def savgol_smooth(y, window_length=5, polyorder=3):
    """
    Savitzky-Golay smoothing with validation.
    """
    y = np.asarray(y, dtype=float)

    if window_length % 2 == 0:
        window_length += 1

    if window_length <= polyorder:
        window_length = polyorder + 2
        if window_length % 2 == 0:
            window_length += 1

    if window_length > len(y):
        window_length = len(y) if len(y) % 2 == 1 else len(y) - 1

    if window_length < 3:
        return y.copy()

    return savgol_filter(y, window_length=window_length, polyorder=polyorder)


def smooth_signal(y, method="whittaker", **kwargs):
    """
    Dispatch smoothing method.
    """
    method = method.lower()

    if method == "whittaker":
        return whittaker_smooth(
            y,
            lam=kwargs.get("lam", 1.0),
            d=kwargs.get("d", 2),
        )
    elif method in {"savgol", "savitzky-golay", "savitzky_golay"}:
        return savgol_smooth(
            y,
            window_length=kwargs.get("window_length", 5),
            polyorder=kwargs.get("polyorder", 3),
        )
    else:
        raise ValueError(f"Unknown smoothing method: {method}")
