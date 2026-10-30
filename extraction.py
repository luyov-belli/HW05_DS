"""Del texto al registro: normalización, extracción (reglas o LLM) y verificación literal.

Todo lo específico de cada registro (campos, sinónimos, carta, prompt) viene del esquema
en config.yaml; este módulo solo sabe tratar *tipos* de campo: number, money, text, list,
category e items. Por eso el mismo código sirve a entrevistas y a pedidos.
"""
import json
import os
import re
import unicodedata

from rapidfuzz import fuzz

# --------------------------------------------------------------------------------------
# 1. Normalización de texto (la misma para WER, extracción y verificación)
# --------------------------------------------------------------------------------------
# Cada palabra numérica tiene un valor y una "posición": centenas (100), decenas (10) o
# unidades (1). Un número solo puede seguir creciendo hacia posiciones menores, así
# "ciento veinte" se une (120) pero "veinticuatro cincuenta" queda como 24 y 50.
_UNITS = {"cero": 0, "un": 1, "uno": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4,
          "cinco": 5, "seis": 6, "siete": 7, "ocho": 8, "nueve": 9}
_TEENS = {"diez": 10, "once": 11, "doce": 12, "trece": 13, "catorce": 14, "quince": 15,
          "dieciseis": 16, "diecisiete": 17, "dieciocho": 18, "diecinueve": 19, "veinte": 20,
          "veintiun": 21, "veintiuno": 21, "veintiuna": 21, "veintidos": 22, "veintitres": 23,
          "veinticuatro": 24, "veinticinco": 25, "veintiseis": 26, "veintisiete": 27,
          "veintiocho": 28, "veintinueve": 29}
_TENS = {"treinta": 30, "cuarenta": 40, "cincuenta": 50, "sesenta": 60, "setenta": 70,
         "ochenta": 80, "noventa": 90}
_HUNDREDS = {"cien": 100, "ciento": 100, "doscientos": 200, "doscientas": 200,
             "trescientos": 300, "trescientas": 300, "cuatrocientos": 400,
             "cuatrocientas": 400, "quinientos": 500, "quinientas": 500,
             "seiscientos": 600, "seiscientas": 600, "setecientos": 700,
             "setecientas": 700, "ochocientos": 800, "ochocientas": 800,
             "novecientos": 900, "novecientas": 900}
_WORDS = {**{w: (v, 1) for w, v in _UNITS.items()}, **{w: (v, 1) for w, v in _TEENS.items()},
          **{w: (v, 10) for w, v in _TENS.items()}, **{w: (v, 100) for w, v in _HUNDREDS.items()}}
_MULTIPLIERS = {"mil": 1_000, "millon": 1_000_000, "millones": 1_000_000}
_NUMBER = re.compile(r"^\d+(\.\d+)?$")


def _parse_number(tokens, i):
    """Lee un número escrito en palabras que empieza en tokens[i].

    Devuelve (valor, índice siguiente) o None si tokens[i] no inicia un número.
    """
    total, current, last_place, j = 0, 0, 1000, i
    if tokens[i].isdigit() and i + 1 < len(tokens) and tokens[i + 1] in _MULTIPLIERS:
        current, last_place, j = int(tokens[i]), 1, i + 1      # "5 mil" -> 5000
    while j < len(tokens):
        tok = tokens[j]
        if tok in _MULTIPLIERS:
            if _MULTIPLIERS[tok] == 1_000:
                total += (current or 1) * 1_000                 # "mil" sola vale 1000
            else:
                total = (total + (current or 1)) * _MULTIPLIERS[tok]
            current, last_place = 0, 1000
        elif tok == "y" and last_place == 10 and j + 1 < len(tokens) and tokens[j + 1] in _UNITS:
            pass                                                # "treinta y cinco"
        elif tok in _WORDS and _WORDS[tok][1] < last_place:
            current += _WORDS[tok][0]
            last_place = _WORDS[tok][1]
        else:
            break
        j += 1
    if j == i:
        return None
    return total + current, j


def _words_to_digits(text):
    tokens, out, i = text.split(), [], 0
    while i < len(tokens):
        parsed = _parse_number(tokens, i)
        if parsed:
            out.append(str(parsed[0]))
            i = parsed[1]
        else:
            out.append(tokens[i])
            i += 1
    return " ".join(out)


def strip_accents(text):
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c))


def normalize(text):
    """Regla única de normalización (documentada en el README):

    1. minúsculas, sin tildes, sin etiquetas de hablante ("A:", "B:");
    2. símbolos a palabras: S/ -> soles, $ -> dolares, % -> porciento;
    3. separador de miles fuera (6.500 o 6,500 -> 6500) y coma decimal a punto (1,5 -> 1.5);
    4. se borra toda puntuación;
    5. números en palabras a dígitos (seis mil quinientos -> 6500);
    6. "N con NN" -> decimal (24 con 50 -> 24.50) y "N <unidad> y medio" -> N.5.
    """
    t = strip_accents(text.lower())
    t = re.sub(r"(?m)^\s*[ab]\s*:", " ", t)
    t = re.sub(r"s/\.?", " soles ", t)
    t = t.replace("us$", " dolares ").replace("$", " dolares ").replace("%", " porciento ")
    t = re.sub(r"(?<=\d)[.,](?=\d{3}\b)", "", t)
    t = re.sub(r"(?<=\d),(?=\d)", ".", t)
    t = re.sub(r"[^a-z0-9.\s]", " ", t)
    t = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", t)
    t = re.sub(r"\bpor ciento\b", "porciento", t)
    t = _words_to_digits(t)
    t = re.sub(r"\b(\d+) con (\d{2})\b", r"\1.\2", t)
    t = re.sub(r"\b(\d+) (anos?|meses|litros?) y medi[oa]\b", r"\1.5 \2", t)
    return " ".join(t.split())


def sentences(text):
    """Frases del texto crudo (antes de borrar la puntuación), ya normalizadas."""
    parts = re.split(r"[?!¿¡\n]+|\.(?!\d)", text)          # "62.50" no corta la frase
    return [s for s in (normalize(p) for p in parts) if s]


def numbers_in(norm_text):
    return {float(tok) for tok in norm_text.split() if _NUMBER.match(tok)}


def has_phrase(norm_text, phrase):
    return re.search(rf"(?<!\S){re.escape(normalize(phrase))}(?!\S)", norm_text) is not None


def _as_number(token):
    return float(token) if _NUMBER.match(token) else None


def _clean_number(value):
    """6500.0 -> 6500 para que el registro se lea como lo diría una persona."""
    return int(value) if value is not None and float(value).is_integer() else value


# --------------------------------------------------------------------------------------
# 2. Extracción por reglas
# --------------------------------------------------------------------------------------
def _positions(tokens, phrase):
    words = normalize(phrase).split()
    return [i for i in range(len(tokens) - len(words) + 1) if tokens[i:i + len(words)] == words]


def _rule_number(tokens, spec, window=8):
    """Número más cercano a una palabra clave; si el campo tiene unidad, debe ir seguido de ella."""
    unit = re.compile(rf"^{spec['unit']}$") if spec.get("unit") else None
    best = None
    for cue in spec["cues"]:
        for p in _positions(tokens, cue):
            lo = p - window if unit else p                       # sin unidad: solo después de la clave
            for j in range(max(0, lo), min(len(tokens), p + window)):
                value = _as_number(tokens[j])
                if value is None or (unit and not (j + 1 < len(tokens) and unit.match(tokens[j + 1]))):
                    continue
                distance = abs(j - p)
                if best is None or distance < best[0] or (not unit and distance == best[0]):
                    best = (distance, value)
    return _clean_number(best[1]) if best else None


def _rule_money(tokens, spec, window=8):
    """Como _rule_number, pero el número debe ir seguido (a 2 palabras) de una moneda."""
    currency_of = {normalize(w): code for code, words in spec["currencies"].items() for w in words}
    best = None
    for cue in spec["cues"]:
        for p in _positions(tokens, cue):
            for j in range(max(0, p - window), min(len(tokens), p + window)):
                value = _as_number(tokens[j])
                currency = next((currency_of[w] for w in tokens[j + 1:j + 3] if w in currency_of), None)
                if value is not None and currency and (best is None or abs(j - p) < best[0]):
                    best = (abs(j - p), value, currency)
    return {"monto": _clean_number(best[1]), "moneda": best[2]} if best else None


_STOP = {"en", "para", "con", "y", "que", "donde", "desde", "hace"}


def _rule_text(raw, spec):
    """Texto libre: lo que sigue a la primera frase clave que aparezca, hasta un conector."""
    sents = sentences(raw)
    max_words = spec.get("max_words", 5)
    for cue in spec["cues"]:
        for k, sent in enumerate(sents):
            words = sent.split()
            hits = _positions(words, cue)
            if not hits:
                continue
            if spec.get("max_words"):        # direcciones: primera frase con número desde la clave
                follow = next((s for s in sents[k:] if re.search(r"\d", s)), None)
                return " ".join(follow.split()[:max_words]) if follow else None
            after = words[hits[0] + len(normalize(cue).split()):]
            captured = []
            for w in after[:max_words]:
                if w in _STOP:
                    break
                captured.append(w)
            if captured:
                return " ".join(captured)
    return None


def _match_vocabulary(tokens, vocabulary):
    """Recorre los tokens buscando alias (los más largos primero). Devuelve [(índice, nombre)]."""
    aliases = sorted(((normalize(a).split(), name) for name, al in vocabulary.items() for a in al),
                     key=lambda x: -len(x[0]))
    found, i = [], 0
    while i < len(tokens):
        for words, name in aliases:
            if tokens[i:i + len(words)] == words:
                found.append((i, name))
                i += len(words)
                break
        else:
            i += 1
    return found


def _rule_list(raw, spec):
    """Vocabulario cerrado; se descarta lo mencionado en una frase con negación."""
    result = []
    for sent in sentences(raw):
        words = sent.split()
        if {"no", "nunca"} & set(words):
            continue
        for _, name in _match_vocabulary(words, spec["vocabulary"]):
            if name not in result:
                result.append(name)
    return result


def _rule_category(tokens, spec, classes, window=15):
    """Último sinónimo de clase que aparece tras una palabra clave (o en todo el texto si no hay)."""
    hits = _match_vocabulary(tokens, classes)
    if spec.get("cues"):
        starts = [p for cue in spec["cues"] for p in _positions(tokens, cue)]
        hits = [(i, c) for i, c in hits if any(0 <= i - p <= window for p in starts)]
    return hits[-1][1] if hits else None


def _rule_items(tokens, schema):
    """Pedido por reglas: cada mención de un producto actualiza su línea (la última gana)."""
    catalog = schema["catalog"]
    product_of = {normalize(a): name for name, p in catalog.items() for a in p["aliases"]}
    remove_cues = {normalize(w) for w in schema["remove_cues"]}
    items = {}
    for i, tok in enumerate(tokens):
        product = product_of.get(tok)
        if not product:
            continue
        before = tokens[max(0, i - 3):i]
        if remove_cues & set(before[-2:]):
            items.pop(product, None)
            continue
        line = items.setdefault(product, {"producto": product, "tamano": None,
                                          "cantidad": 1, "precio_unitario": None})
        start = max(0, i - 3)          # cantidad: número justo antes que no sea un precio ("69 soles")
        qty = [int(float(w)) for k, w in enumerate(before, start)
               if _as_number(w) is not None and tokens[k + 1] != "soles"]
        if qty:
            line["cantidad"] = qty[-1]
        size_aliases = catalog[product].get("size_aliases", {})
        for side in (before, tokens[i + 1:i + 4]):
            found = _match_vocabulary(side, size_aliases)
            if found:
                line["tamano"] = found[0][1]
                break
        j = i + 1
        while j < min(len(tokens) - 1, i + 10) and tokens[j] not in product_of:
            if _as_number(tokens[j]) is not None and tokens[j + 1] == "soles":
                line["precio_unitario"] = _clean_number(float(tokens[j]))
                break
            j += 1
    return list(items.values())


def extract_rules(transcript, schema):
    tokens = normalize(transcript).split()
    record = {}
    for name, spec in schema["fields"].items():
        kind = spec["type"]
        if kind == "number":
            record[name] = _rule_number(tokens, spec)
        elif kind == "money":
            record[name] = _rule_money(tokens, spec)
        elif kind == "text":
            record[name] = _rule_text(transcript, spec)
        elif kind == "list":
            record[name] = _rule_list(transcript, spec)
        elif kind == "category":
            record[name] = _rule_category(tokens, spec, _classes(spec, schema))
        elif kind == "items":
            record[name] = _rule_items(tokens, schema)
    return record


def _classes(spec, schema):
    """Clases de un campo categórico: propias o tomadas de otra sección (p. ej. promociones)."""
    if "classes_from" in spec:
        return {name: v["aliases"] for name, v in schema[spec["classes_from"]].items()}
    return spec["classes"]


# --------------------------------------------------------------------------------------
# 3. Extracción con un modelo de lenguaje (JSON estructurado)
# --------------------------------------------------------------------------------------
def extract_llm(transcript, schema, cfg):
    from openai import OpenAI          # import local: el motor no lo necesita para la ruta de reglas

    llm = cfg["llm"]
    client = OpenAI(base_url=llm["base_url"], api_key=os.getenv(llm["api_key_env"]) or "local",
                    timeout=llm["timeout_seconds"])
    fields = "\n".join(f'- "{name}": {spec["describe"]}' for name, spec in schema["fields"].items())
    if "catalog" in schema:                # la carta le da al LLM los nombres válidos, no los precios
        menu = "; ".join(f"{name} (tamaños: {', '.join(str(s) for s in p['sizes'] if s) or 'ninguno'})"
                         for name, p in schema["catalog"].items())
        fields += f"\n  Productos válidos: {menu}."
    response = client.chat.completions.create(
        model=llm["model"],
        temperature=llm["temperature"],
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": llm["prompt"].format(fields=fields, transcript=transcript)}],
    )
    return _coerce(json.loads(response.choices[0].message.content), schema)


def _to_number(value):
    if isinstance(value, (int, float)):
        return _clean_number(float(value))
    found = numbers_in(normalize(str(value))) if value is not None else set()
    return _clean_number(max(found)) if found else None


def _canonical(value, classes):
    """Lleva una respuesta libre del LLM a la clase/nombre canónico, si la reconoce."""
    if value is None:
        return None
    norm = normalize(str(value))
    for name, aliases in classes.items():
        if norm == normalize(str(name)) or any(norm == normalize(a) for a in aliases):
            return name
    contained = {name for name, aliases in classes.items() if any(has_phrase(norm, a) for a in aliases)}
    return contained.pop() if len(contained) == 1 else str(value)    # "intermedio alto" -> intermedio


def _coerce(data, schema):
    """Valida tipos de la respuesta del LLM; lo que no encaja queda en None."""
    record = {}
    for name, spec in schema["fields"].items():
        value, kind = data.get(name), spec["type"]
        if kind == "number":
            record[name] = _to_number(value)
        elif kind == "money":
            if isinstance(value, dict):
                currency = _canonical(value.get("moneda"), spec["currencies"])
                record[name] = {"monto": _to_number(value.get("monto")), "moneda": currency}
            else:
                record[name] = None
        elif kind == "text":
            record[name] = normalize(str(value)) if value else None
        elif kind == "list":
            values = value if isinstance(value, list) else []
            record[name] = [_canonical(v, spec["vocabulary"]) for v in values if v]
        elif kind == "category":
            record[name] = _canonical(value, _classes(spec, schema))
        elif kind == "items":
            record[name] = [_coerce_item(it, schema["catalog"]) for it in (value or []) if isinstance(it, dict)]
    return record


def _coerce_item(item, catalog):
    """Lleva el nombre libre del LLM a la carta: "cuarto de pollo" -> pollo a la brasa, tamaño cuarto."""
    words = normalize(f"{item.get('producto') or ''} {item.get('tamano') or ''}").split()
    product = _canonical(item.get("producto"), {n: p["aliases"] for n, p in catalog.items()})
    if product not in catalog:
        found = _match_vocabulary(words, {n: [n] + p["aliases"] for n, p in catalog.items()})
        product = found[0][1] if found else product
    sizes = catalog.get(product, {}).get("size_aliases", {})
    size = _canonical(item.get("tamano"), sizes) if sizes else None
    if sizes and size not in sizes:
        found = _match_vocabulary(words, sizes)
        size = found[0][1] if found else size
    qty = _to_number(item.get("cantidad"))
    return {"producto": product, "tamano": size, "cantidad": qty if qty is not None else 1,
            "precio_unitario": _to_number(item.get("precio_unitario"))}


def extract(transcript, schema, extractor, cfg):
    if extractor == "rules":
        return extract_rules(transcript, schema)
    if extractor == "llm":
        return extract_llm(transcript, schema, cfg)
    raise ValueError(f"extractor desconocido: {extractor}")


# --------------------------------------------------------------------------------------
# 4. Verificación literal: cada valor debe estar en la transcripción
# --------------------------------------------------------------------------------------
def _without(norm_text, ignore):
    return " ".join(w for w in norm_text.split() if w not in ignore)


def verify(record, transcript, schema, cfg):
    """Devuelve, por campo, 'verificado', 'sin_verificar' o 'vacio'.

    Un valor está verificado solo si aparece literalmente en la transcripción normalizada.
    Los números se comparan ya normalizados: "seis mil quinientos" en el audio y 6500 en el
    registro coinciden; 5.5 obtenido sumando "3 años" y "2 años y medio" NO, porque nadie lo dijo.
    """
    text = normalize(transcript)
    numbers = numbers_in(text)
    ignore = set(cfg["verification"]["ignore_words"])

    def said(phrase):
        return has_phrase(text, phrase)

    def said_number(value):
        return value is not None and float(value) in numbers

    status = {}
    for name, spec in schema["fields"].items():
        value, kind = record.get(name), spec["type"]
        if value in (None, [], {}):
            status[name] = "vacio"
            continue
        if kind == "number":
            ok = said_number(value)
        elif kind == "money":
            ok = said_number(value.get("monto")) and any(
                said(w) for w in spec["currencies"].get(value.get("moneda"), []))
        elif kind == "text":
            ok = has_phrase(_without(text, ignore), _without(normalize(value), ignore))
        elif kind == "list":
            ok = all(any(said(a) for a in spec["vocabulary"].get(v, [v])) for v in value)
        elif kind == "category":
            ok = any(said(a) for a in _classes(spec, schema).get(value, [value]))
        elif kind == "items":
            ok = all(_item_said(it, schema["catalog"], said, said_number) for it in value)
        else:
            ok = False
        status[name] = "verificado" if ok else "sin_verificar"
    return status


def _item_said(item, catalog, said, said_number):
    product = catalog.get(item.get("producto"))
    if not product:
        return False
    size_ok = item.get("tamano") is None or any(
        said(a) for a in product.get("size_aliases", {}).get(item["tamano"], [item["tamano"]]))
    return (any(said(a) for a in product["aliases"]) and size_ok
            and said_number(item.get("cantidad")) and said_number(item.get("precio_unitario")))


# --------------------------------------------------------------------------------------
# 5. ¿El valor extraído es correcto? (se usa en métricas, contra la verdad de campo)
# --------------------------------------------------------------------------------------
def same_value(pred, gold, spec, cfg):
    kind, tol = spec["type"], cfg["matching"]["number_tolerance"]
    if gold is None or pred is None:
        return gold is None and pred is None
    if kind == "number":
        return abs(float(pred) - float(gold)) <= tol
    if kind == "money":
        return (pred.get("moneda") == gold["moneda"] and pred.get("monto") is not None
                and abs(float(pred["monto"]) - float(gold["monto"])) <= tol)
    if kind == "text":
        ignore = set(cfg["verification"]["ignore_words"])
        p, g = _without(normalize(pred), ignore), _without(normalize(gold), ignore)
        digits_equal = re.findall(r"\d+", p) == re.findall(r"\d+", g)
        return digits_equal and fuzz.ratio(p, g) / 100 >= cfg["matching"]["text_min_similarity"]
    if kind == "list":
        return {normalize(v) for v in pred} == {normalize(v) for v in gold}
    if kind == "items":
        return sorted(map(_item_key, pred)) == sorted(map(_item_key, gold))
    return normalize(str(pred)) == normalize(str(gold))


def _item_key(item):
    price = item.get("precio_unitario")
    return (str(item.get("producto")), str(item.get("tamano")), float(item.get("cantidad") or 0),
            float(price) if price is not None else -1.0)
