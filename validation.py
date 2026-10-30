"""Validación aritmética de un pedido y diagnóstico de la causa cuando no cuadra.

La verificación (extraction.verify) pregunta "¿esto se dijo?". La validación pregunta
"¿lo que se dijo es coherente consigo mismo?": cantidad x precio, sumado, menos la
promoción, debe ser igual al total dicho. No necesita verdad de campo.
"""
from extraction import normalize, numbers_in


def _catalog_price(item, catalog):
    sizes = catalog.get(item.get("producto"), {}).get("sizes", {})
    return sizes.get(item.get("tamano"))


def _discount(promotion, subtotal, schema):
    promo = schema["promotions"].get(promotion) if promotion else None
    if not promo:
        return 0.0
    return subtotal * promo["percent"] / 100 if "percent" in promo else float(promo["amount"])


def check_order(record, segments, schema, cfg):
    """Devuelve el estado del pedido: 'cuadra', 'no_cuadra' o 'incompleto', con el detalle."""
    tolerance = cfg["validation"]["tolerance"]
    items, notes = record.get("items") or [], []
    subtotal = 0.0
    for item in items:
        price, qty = item.get("precio_unitario"), item.get("cantidad")
        if price is None:
            price = _catalog_price(item, schema["catalog"])
            if price is not None:
                notes.append(f"precio de {item.get('producto')} tomado de la carta (no se escuchó)")
        if price is None or qty is None:
            return {"estado": "incompleto", "motivos": [f"falta precio o cantidad de {item.get('producto')}"]}
        subtotal += float(qty) * float(price)
    total = record.get("total_dicho")
    if not items or total is None:
        return {"estado": "incompleto", "motivos": ["no hay ítems o no se escuchó el total"]}

    discount = _discount(record.get("promocion"), subtotal, schema)
    expected = round(subtotal - discount, 2)
    result = {"estado": "cuadra", "subtotal": round(subtotal, 2), "descuento": round(discount, 2),
              "total_calculado": expected, "total_dicho": total,
              "diferencia": round(float(total) - expected, 2), "motivos": notes, "causa": None}
    if abs(result["diferencia"]) > tolerance:
        result["estado"] = "no_cuadra"
        result["causa"], reasons = diagnose(record, segments, schema, cfg)
        result["motivos"] = notes + reasons
    return result


def diagnose(record, segments, schema, cfg):
    """¿Error del reconocimiento (ASR) o error de quien habló?

    Los precios tienen una referencia externa (la carta); el total dicho no. Regla:
      (a) si un precio unitario no coincide con la carta, se oyó mal -> 'error_asr';
      (b) si los precios cuadran con la carta, lo único sin comprobar es el total: si
          Whisper le dio baja probabilidad a esa palabra -> 'error_asr';
      (c) si no, todo se oyó con confianza y coincide con la carta -> 'error_hablante'.
    """
    reasons = []
    for item in record.get("items") or []:
        reference = _catalog_price(item, schema["catalog"])
        heard = item.get("precio_unitario")
        if reference is not None and heard is not None and float(heard) != float(reference):
            reasons.append(f"precio de {item['producto']} ({heard}) distinto a la carta ({reference})")

    threshold = cfg["validation"]["low_word_probability"]
    total = float(record["total_dicho"])
    targets = {total, float(int(total))}          # "62 con 50" llega como palabras sueltas: basta el entero
    for seg in segments or []:
        for w in seg.get("words", []):
            if targets & numbers_in(normalize(w["word"])) and w["probability"] < threshold:
                reasons.append(f"el total '{w['word'].strip()}' se oyó con probabilidad {w['probability']}")
    return ("error_asr" if reasons else "error_hablante"), reasons
