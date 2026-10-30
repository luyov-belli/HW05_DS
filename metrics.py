"""Métricas de las dos capas, siempre sobre texto normalizado con extraction.normalize.

Capa transcripción: WER y CER ("¿oyó las palabras?").
Capa registro: exactitud por campo, F1 macro en categóricos, error absoluto en numéricos
("¿el dato sirve?"). Con 4-5 clips por tarea, todo se reporta con un intervalo bootstrap.
"""
import jiwer
import numpy as np

from extraction import has_phrase, normalize, same_value


def wer_cer(reference, hypothesis):
    ref, hyp = normalize(reference), normalize(hypothesis)
    words = jiwer.process_words(ref, hyp)
    chars = jiwer.process_characters(ref, hyp)
    word_errors = words.substitutions + words.deletions + words.insertions
    char_errors = chars.substitutions + chars.deletions + chars.insertions
    n_words, n_chars = len(ref.split()), len(ref)
    return {"wer": word_errors / n_words, "cer": char_errors / n_chars,
            "word_errors": word_errors, "words": n_words, "char_errors": char_errors, "chars": n_chars}


def pooled_rate(rows, errors="word_errors", total="words"):
    """WER del corpus = errores totales / palabras totales (no el promedio de WER por clip)."""
    return sum(r[errors] for r in rows) / max(1, sum(r[total] for r in rows))


def bootstrap_ci(rows, statistic, cfg):
    """Intervalo percentil remuestreando clips con reemplazo. Con pocos clips sale ancho, y eso es honesto."""
    ev = cfg["evaluation"]
    if len(rows) < 2:
        return [None, None]
    rng = np.random.default_rng(ev["seed"])
    stats = [statistic([rows[i] for i in rng.integers(0, len(rows), len(rows))])
             for _ in range(ev["bootstrap_samples"])]
    alpha = (1 - ev["confidence"]) / 2
    return [round(float(np.quantile(stats, alpha)), 4), round(float(np.quantile(stats, 1 - alpha)), 4)]


def mean(values):
    return float(np.mean(values)) if len(values) else float("nan")


def macro_f1(golds, preds):
    """F1 por clase, promediado sin pesar por frecuencia (las clases raras cuentan igual)."""
    classes = {str(g) for g in golds} | {str(p) for p in preds if p is not None}
    scores = []
    for c in classes:
        tp = sum(str(g) == c and str(p) == c for g, p in zip(golds, preds))
        fp = sum(str(g) != c and str(p) == c for g, p in zip(golds, preds))
        fn = sum(str(g) == c and str(p) != c for g, p in zip(golds, preds))
        scores.append(2 * tp / (2 * tp + fp + fn) if tp + fp + fn else 1.0)
    return mean(scores)


def score_record(pred, gold, schema, cfg):
    """Por campo: ¿correcto? y, si es numérico, el error absoluto."""
    out = {}
    for name, spec in schema["fields"].items():
        p, g = (pred or {}).get(name), gold.get(name)
        row = {"correct": same_value(p, g, spec, cfg)}
        if spec["type"] in ("number", "money"):
            pv = p.get("monto") if isinstance(p, dict) else p
            gv = g.get("monto") if isinstance(g, dict) else g
            row["abs_error"] = abs(float(pv) - float(gv)) if pv is not None and gv is not None else None
        out[name] = row
    return out


def glossary_recall(reference, hypothesis, terms):
    """De los términos del glosario que se dijeron, ¿cuántos aparecen bien escritos en la transcripción?"""
    ref, hyp = normalize(reference), normalize(hypothesis)
    said = [t for t in terms if has_phrase(ref, t)]
    return sum(has_phrase(hyp, t) for t in said), len(said)
