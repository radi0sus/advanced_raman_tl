import numpy as np
from scipy import sparse
from scipy.sparse import linalg
from scipy.special import expit


def baseline_arpls(y, lam=1000.0, ratio=1e-6, max_iter=200):
    """
    arPLS baseline correction.

    Parameters
    ----------
    y : array-like
        Intensity values.
    lam : float
        Smoothness parameter.
    ratio : float
        Convergence threshold.
    max_iter : int
        Maximum number of iterations.

    Returns
    -------
    np.ndarray
        Estimated baseline.
    """
    y = np.asarray(y, dtype=float)
    n = len(y)

    if n < 3:
        return np.zeros_like(y)

    diag = np.ones(n - 2)
    d = sparse.spdiags([diag, -2 * diag, diag], [0, -1, -2], n, n - 2)
    h = (lam * d.dot(d.T)).tocsc()

    w = np.ones(n)
    w_mat = sparse.spdiags(w, 0, n, n).tocsc()

    for _ in range(max_iter):
        a = (w_mat + h).tocsc()
        z = linalg.spsolve(a, w * y)

        diff = y - z
        negative_diff = diff[diff < 0]

        if negative_diff.size == 0:
            break

        mean_neg = np.mean(negative_diff)
        std_neg = np.std(negative_diff)

        if std_neg == 0:
            break

        w_new = expit(-2 * (diff - (2 * std_neg - mean_neg)) / std_neg)
        crit = np.linalg.norm(w_new - w) / max(np.linalg.norm(w), 1e-12)

        w = w_new
        w_mat = sparse.spdiags(w, 0, n, n).tocsc()

        if crit < ratio:
            break

    return z


def baseline_snip(y, iterations=60):
    """
    SNIP baseline estimation for Raman intensity data.

    Parameters
    ----------
    y : array-like
        Intensity values.
    iterations : int
        Number of SNIP iterations.

    Returns
    -------
    np.ndarray
        Estimated baseline.
    """
    y = np.asarray(y, dtype=float)
    n = len(y)

    if n < 3:
        return np.zeros_like(y)

    iterations = max(1, int(iterations))
    baseline = y.copy()

    for k in range(1, iterations + 1):
        next_baseline = baseline.copy()

        for i in range(k, n - k):
            avg = 0.5 * (baseline[i - k] + baseline[i + k])
            if avg < next_baseline[i]:
                next_baseline[i] = avg

        baseline = next_baseline

    return baseline


def subtract_baseline(y, baseline):
    y = np.asarray(y, dtype=float)
    baseline = np.asarray(baseline, dtype=float)
    return y - baseline