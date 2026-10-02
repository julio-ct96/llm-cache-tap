"""Compute the cache verdict of a response and the notes that explain it."""

from cachetap import config, providers, record


def judge(rec: record.Record, prev: record.Record | None) -> None:
    """Mutate rec by setting verdict, notes and server_side."""
    u = rec.get("usage")
    if not u or not isinstance(u, dict):
        rec["verdict"], rec["notes"] = "N/A", ["la respuesta no trae usage"]
        return
    read, total = u["read"], u["input_total"]
    previous_usage = prev.get("usage") if prev else None
    base = previous_usage["input_total"] if isinstance(previous_usage, dict) else None
    minimum = providers.min_cacheable(rec.get("model"))
    if read == 0 and total < minimum:
        result: record.Verdict = "N/A"
    elif read == 0:
        result = "MISS" if prev else "COLD"
    elif base:
        result = "HIT" if read >= 0.9 * base else "PARTIAL"
    else:
        result = "HIT" if read >= 0.9 * total else "PARTIAL"
    notes, server_side = [], False
    if result == "N/A":
        notes.append(f"menos de {minimum} tokens de entrada: por debajo del mínimo cacheable de este modelo")
    elif not prev:
        notes.append("primera petición de esta conversación")
        if read:
            notes.append("parte del prefijo ya estaba en caché de otra conversación")
    else:
        ef = f"{rec.get('prev_effort')} → {rec.get('effort')}"
        if result == "HIT":
            if rec.get("effort_changed"):
                notes.append(f"hit pese al cambio de esfuerzo ({ef})")
            if not rec.get("prefix_intact"):
                notes.append(f"el cliente modificó el prefijo en {rec.get('diverge_at')}; el hit viene de una variante ya cacheada")
        else:
            if rec.get("model_changed"):
                notes.append(f"cambió el modelo ({rec.get('prev_model')} → {rec.get('model')})")
            if rec.get("effort_changed"):
                notes.append(f"cambió el esfuerzo ({ef})")
            if rec.get("params_changed"):
                notes.append("cambiaron thinking/tool_choice")
            if not rec.get("prefix_intact"):
                notes.append(f"el cliente modificó el prefijo en {rec.get('diverge_at')}")
            ttl, age = prev.get("ttl_s", config.TTL_S), rec.get("age_s", 0)
            if age > ttl:
                since = "el inicio" if prev.get("ttl_anchor") == "start" else "el final"
                notes.append(f"pasaron {age:.0f} s desde {since} de #{prev['id']} (TTL {ttl} s, {prev.get('ttl_source')})")
            if prev.get("state") != "done" or (prev.get("status") or 0) >= 400:
                notes.append(f"la petición anterior (#{prev['id']}) no terminó bien")
            if not notes:
                server_side = True
                notes.append(f"sin causa en el cliente: mismo prefijo, mismo esfuerzo, {rec.get('gap_s')} s desde #{prev['id']}")
    rec["verdict"], rec["notes"], rec["server_side"] = result, notes, server_side
