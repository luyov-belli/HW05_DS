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

    Regla: es 'error_asr' si hay evidencia de que algo se oyó mal:
      (a) un precio unitario no coincide con la carta, o
      (b) Whisper dio baja probabilidad a una palabra numérica en un segmento donde
          aparece alguno de los números del pedido.
    Si no hay ninguna de esas señales, los números se oyeron con confianza y coinciden
    con la carta: el error lo cometió quien habló -> 'error_hablante'.
    """
    reasons = []
    for item in record.get("items") or []:
        reference = _catalog_price(item, schema["catalog"])
        heard = item.get("precio_unitario")
        if reference is not None and heard is not None and float(heard) != float(reference):
            reasons.append(f"precio de {item['producto']} ({heard}) distinto a la carta ({reference})")

    threshold = cfg["validation"]["low_word_probability"]
    money = [record.get("total_dicho")] + [it.get("precio_unitario") for it in record.get("items") or []]
    order_numbers = {float(v) for v in money if v is not None}
    for seg in segments or []:
        if not numbers_in(normalize(seg["text"])) & order_numbers:
            continue
        doubtful = [w["word"].strip() for w in seg.get("words", [])
                    if w["probability"] < threshold and numbers_in(normalize(w["word"]))]
        if doubtful:
            reasons.append(f"números con baja confianza en '{seg['text'].strip()}': {', '.join(doubtful)}")
    return ("error_asr" if reasons else "error_hablante"), reasons
