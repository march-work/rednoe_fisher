import re


def match_keywords(ocr_result, keywords, *, min_avg_conf=55.0, min_token_conf=60.0, min_cjk_ratio=0.02):
    text = (ocr_result or {}).get("text", "") or ""
    avg_conf = float((ocr_result or {}).get("avg_conf", 0.0) or 0.0)
    cjk_ratio = float((ocr_result or {}).get("cjk_ratio", 0.0) or 0.0)
    tokens = (ocr_result or {}).get("tokens", []) or []

    norm_text = re.sub(r"\W+", "", text, flags=re.UNICODE).upper()

    matched = []
    for k in keywords or []:
        if not k:
            continue
        ks = str(k).strip()
        if not ks:
            continue
        nk = re.sub(r"\W+", "", ks, flags=re.UNICODE).upper()
        if not nk:
            continue

        is_ascii = all(ord(ch) < 128 for ch in nk)
        is_cjk = bool(re.search(r"[\u4e00-\u9fff]", nk))
        if is_ascii and len(nk) <= 2:
            if avg_conf < float(min_avg_conf):
                continue
            hit = False
            for tok in tokens:
                t = re.sub(r"\W+", "", str(tok.get("text", "")), flags=re.UNICODE).upper()
                try:
                    conf = float(tok.get("conf", -1))
                except Exception:
                    conf = -1
                if t == nk and conf >= float(min_token_conf):
                    hit = True
                    break
            if hit:
                if cjk_ratio >= float(min_cjk_ratio) or nk.isalpha():
                    matched.append(ks)
            continue

        if nk and nk in norm_text:
            if is_cjk:
                if cjk_ratio >= float(min_cjk_ratio):
                    matched.append(ks)
            else:
                if avg_conf >= float(min_avg_conf):
                    matched.append(ks)

    return matched
