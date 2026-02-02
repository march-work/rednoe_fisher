def percent_to_alpha(percent, *, default=0):
    try:
        p = float(percent)
    except Exception:
        p = float(default)
    if p != p:
        p = float(default)
    p = max(0.0, min(100.0, p))
    return int(max(0, min(255, round(255.0 * p / 100.0))))
