def update_confirm(pending_key, pending_count, key, frames):
    frames = max(1, int(frames))
    key = (key or "").strip()
    if not key:
        return pending_key, int(pending_count or 0), False

    if frames <= 1:
        return key, 1, True

    if pending_key == key:
        pending_count = int(pending_count or 0) + 1
    else:
        pending_key = key
        pending_count = 1

    return pending_key, pending_count, pending_count >= frames
