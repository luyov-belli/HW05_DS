"""Pasos por lotes sobre el corpus (corren una vez). Lo que corre por cada audio nuevo es engine.process.

  python pipeline.py tts        --locales es-PE es-MX es-ES es-AR es-CO   # clips sintéticos (grupo aparte)
  python pipeline.py ladder     --corpus real                             # escalera L1-L3 de las llamadas
  python pipeline.py transcribe --corpus real --task pedido --level L2    # una corrida -> results/transcripts
  python pipeline.py bench      --corpus real                             # rejilla GPU/CPU/precisión (Colab)
  python pipeline.py extract    --extractor llm --runs "real__*"          # registros desde transcripciones cacheadas
  python pipeline.py evaluate   --gate                                    # métricas + gate de regresión
"""
import argparse
import asyncio
import gc
import io
import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import yaml

import engine
import extraction
import metrics
import validation

CFG = engine.load_config()
SR = 16000
TASKS = ("entrevista", "pedido")


# --------------------------------------------------------------------------------------
# Utilidades de archivos
# --------------------------------------------------------------------------------------
def path(key):
    return engine.ROOT / CFG["paths"][key]


def ground_truth(task):
    with open(engine.ROOT / CFG["paths"]["ground_truth"][task], encoding="utf-8") as f:
        return yaml.safe_load(f)


def audio_file(corpus, level, clip_id):
    """real -> data/audio/real/E01.*, tts-es-PE -> data/audio/tts/es-PE/E01.wav, L1-L3 -> escalera."""
    if level != "L0":
        candidates = [path("audio_ladder") / corpus / level / f"{clip_id}.wav"]
    elif corpus == "real":
        candidates = sorted(path("audio_real").glob(f"{clip_id}.*"))
    else:
        candidates = [path("audio_tts") / corpus.removeprefix("tts-") / f"{clip_id}.wav"]
    return next((p for p in candidates if p.exists()), None)


def run_id(corpus, task, level, model, device, compute_type, glossary, vad_threshold):
    rid = "__".join([corpus, task, level, model, device, compute_type, "glosario" if glossary else "plano"])
    return rid if vad_threshold == CFG["asr"]["vad_threshold"] else f"{rid}__vad{vad_threshold}"


def is_reference(row):
    """Configuración de referencia de config.yaml: la que alimenta tablas principales, app y gate."""
    asr = CFG["asr"]
    return (row["model"] == asr["model"] and row["glossary"] == asr["use_glossary"]
            and row["vad_threshold"] == asr["vad_threshold"]
            and row["compute_type_requested"] == engine.resolve_compute_type(asr["compute_type"], row["device_runtime"]))


def save_json(file, data):
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def load_json(file):
    return json.loads(Path(file).read_text(encoding="utf-8"))


def write_wav(file, audio, sample_rate=SR):
    import soundfile as sf
    file.parent.mkdir(parents=True, exist_ok=True)
    sf.write(file, audio, sample_rate)


# --------------------------------------------------------------------------------------
# tts: clips sintéticos con Edge TTS (grupo separado; también es el eje de acentos)
# --------------------------------------------------------------------------------------
async def _speak(text, voice, attempts=7, timeout=90):
    import edge_tts

    async def collect():
        audio = bytearray()
        async for chunk in edge_tts.Communicate(text, voice, rate=CFG["tts"]["rate"]).stream():
            if chunk["type"] == "audio":
                audio.extend(chunk["data"])
        return bytes(audio)

    for attempt in range(attempts):                       # el servicio a veces corta o se cuelga: reintentar
        try:
            return await asyncio.wait_for(collect(), timeout)
        except (edge_tts.exceptions.EdgeTTSException, asyncio.TimeoutError) as exc:
            print(f"  reintento {attempt + 1} ({voice}): {exc}")
            await asyncio.sleep(2 ** attempt)
    raise RuntimeError(f"Edge TTS no devolvió audio para: {text[:60]}")


def cmd_tts(args):
    from faster_whisper import decode_audio
    pause = np.zeros(int(SR * CFG["tts"]["pause_ms"] / 1000), dtype=np.float32)
    for locale in args.locales:
        voice_a, voice_b = CFG["tts"]["voices"][locale]
        for task in TASKS:
            for clip in ground_truth(task):
                out = path("audio_tts") / locale / f"{clip['id']}.wav"
                if out.exists() and not args.force:
                    continue
                parts = []
                for line in clip["guion"].strip().splitlines():
                    speaker, text = line.split(":", 1)
                    mp3 = asyncio.run(_speak(text.strip(), voice_a if speaker.strip() == "A" else voice_b))
                    parts += [decode_audio(io.BytesIO(mp3)), pause]
                write_wav(out, np.concatenate(parts))
                print(f"tts {locale} {clip['id']}: {sum(len(p) for p in parts) / SR:.0f} s")


# --------------------------------------------------------------------------------------
# ladder: escalera de degradación L1-L3
# --------------------------------------------------------------------------------------
def opus_roundtrip(audio, bitrate, sample_rate):
    """Codifica a Opus (como una nota de voz de WhatsApp) y decodifica de vuelta a 16 kHz."""
    import av
    from faster_whisper import decode_audio
    buffer = io.BytesIO()
    with av.open(buffer, "w", format="ogg") as container:
        stream = container.add_stream("libopus", rate=sample_rate, layout="mono")
        stream.bit_rate = bitrate
        pcm = (np.clip(audio, -1, 1) * 32767).astype(np.int16)[None, :]
        frame = av.AudioFrame.from_ndarray(pcm, format="s16", layout="mono")
        frame.sample_rate = SR
        for packet in stream.encode(frame):
            container.mux(packet)
        for packet in stream.encode(None):
            container.mux(packet)
    buffer.seek(0)
    return decode_audio(buffer)


def phone_band(audio, band_hz, sample_rate):
    """Filtro pasa banda 300-3400 Hz y remuestreo a 8 kHz (una llamada telefónica)."""
    from scipy.signal import butter, resample_poly, sosfiltfilt
    sos = butter(6, band_hz, btype="bandpass", fs=SR, output="sos")
    return resample_poly(sosfiltfilt(sos, audio), sample_rate, SR).astype(np.float32)


def speech_power(audio, frame=400):
    """Potencia media en tramas de 25 ms con voz (energía a menos de 40 dB del pico)."""
    frames = audio[: len(audio) // frame * frame].reshape(-1, frame)
    energy = (frames ** 2).mean(axis=1)
    return float(energy[energy > energy.max() * 1e-4].mean())


def babble(others, length, voices, rng):
    """Ruido de murmullo: varias conversaciones ajenas del mismo corpus, superpuestas."""
    noise = np.zeros(length, dtype=np.float32)
    for k in rng.choice(len(others), size=min(voices, len(others)), replace=False):
        track = np.tile(others[k], int(np.ceil(length / len(others[k]))) + 1)
        start = rng.integers(0, len(others[k]))
        noise += track[start:start + length]
    return noise


def add_noise(audio, noise, snr_db):
    """Escala el ruido para lograr el SNR pedido y devuelve (mezcla, SNR medido)."""
    p_speech, p_noise = speech_power(audio), float((noise ** 2).mean())
    noise = noise * np.sqrt(p_speech / (p_noise * 10 ** (snr_db / 10)))
    measured = 10 * np.log10(p_speech / float((noise ** 2).mean()))
    return (audio + noise).astype(np.float32), round(float(measured), 2)


def cmd_ladder(args):
    from faster_whisper import decode_audio
    levels, rng = CFG["ladder"]["levels"], np.random.default_rng(CFG["ladder"]["seed"])
    clips = {c["id"]: audio_file(args.corpus, "L0", c["id"]) for t in TASKS for c in ground_truth(t)}
    audio = {cid: decode_audio(str(p)) for cid, p in clips.items() if p}
    log = {}
    for clip in ground_truth("pedido"):
        cid = clip["id"]
        if cid not in audio:
            continue
        clean, entry = audio[cid], {}
        for level, spec in levels.items():
            if level == "L0":
                continue
            out = path("audio_ladder") / args.corpus / level / f"{cid}.wav"
            x = clean
            if "snr_db" in spec:
                others = [a for k, a in audio.items() if k != cid]
                x, entry["snr_db_medido"] = add_noise(x, babble(others, len(x), spec["babble_voices"], rng),
                                                      spec["snr_db"])
            base = levels.get(spec.get("base"), spec)
            if "codec" in base:
                x = opus_roundtrip(x, base["bitrate"], base["sample_rate"])
                write_wav(out, x)
            elif "band_hz" in base:
                write_wav(out, phone_band(x, base["band_hz"], base["sample_rate"]), base["sample_rate"])
        log[cid] = entry
        print(f"ladder {args.corpus} {cid}: {entry}")
    save_json(engine.ROOT / "results" / f"ladder_{args.corpus}.json", {"levels": levels, "clips": log})


# --------------------------------------------------------------------------------------
# transcribe / bench: corridas cacheadas con evidencia de GPU
# --------------------------------------------------------------------------------------
class VramMonitor:
    """Muestrea la memoria usada de la GPU 0 (NVML) en un hilo y guarda el pico sobre la línea base."""

    def __init__(self, every):
        self.every, self.handle, self.peak_mb, self.gpu = every, None, None, None

    def __enter__(self):
        try:
            import pynvml
            pynvml.nvmlInit()
            self.handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception:
            return self                                   # sin GPU NVIDIA: no hay nada que medir
        self.nvml, self.gpu = pynvml, pynvml.nvmlDeviceGetName(self.handle)
        self.baseline = self.peak = self._used()
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self._poll, daemon=True)
        self.thread.start()
        return self

    def _used(self):
        return self.nvml.nvmlDeviceGetMemoryInfo(self.handle).used

    def _poll(self):
        while not self.stop.is_set():
            self.peak = max(self.peak, self._used())
            time.sleep(self.every)

    def __exit__(self, *exc):
        if self.handle is not None:
            self.stop.set()
            self.thread.join()
            self.peak_mb = round((self.peak - self.baseline) / 2 ** 20)


def transcribe_run(corpus, task, level, model, device, compute_type, glossary, vad_threshold):
    import ctranslate2
    import faster_whisper
    device = engine.resolve_device(device)
    compute_type = engine.resolve_compute_type(compute_type, device)
    engine.load_model.cache_clear()                       # cada corrida mide su propia carga y VRAM
    gc.collect()
    clips, first = {}, None
    with VramMonitor(CFG["benchmark"]["vram_poll_seconds"]) as vram:
        for clip in ground_truth(task):
            audio = audio_file(corpus, level, clip["id"])
            if audio is None:
                continue
            asr = engine.transcribe(audio, task, model, device, compute_type, glossary, vad_threshold)
            first = first or asr
            clips[clip["id"]] = {k: asr[k] for k in ("text", "segments", "audio_seconds", "asr_seconds")}
            print(f"  {clip['id']}: {asr['asr_seconds']} s de ASR para {asr['audio_seconds']} s de audio")
    if not clips:
        print(f"sin audios para {corpus}/{task}/{level}: nada que transcribir")
        return
    audio_s = sum(c["audio_seconds"] for c in clips.values())
    asr_s = sum(c["asr_seconds"] for c in clips.values())
    meta = {
        "corpus": corpus, "task": task, "level": level, "model": model, "glossary": glossary,
        "vad_threshold": vad_threshold, "device_requested": device, "compute_type_requested": compute_type,
        "device_runtime": first["device"], "compute_type_runtime": first["compute_type"],
        "gpu": vram.gpu, "vram_peak_mb": vram.peak_mb,
        "load_seconds": first["load_seconds"], "audio_seconds": round(audio_s, 1), "asr_seconds": round(asr_s, 1),
        "seconds_per_audio_minute": round(asr_s / (audio_s / 60), 2),
        "faster_whisper": faster_whisper.__version__, "ctranslate2": ctranslate2.__version__,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }
    rid = run_id(corpus, task, level, model, device, compute_type, glossary, vad_threshold)
    save_json(path("transcripts") / f"{rid}.json", {"meta": meta, "clips": clips})
    print(f"{rid}: device={meta['device_runtime']} vram={meta['vram_peak_mb']} MB "
          f"{meta['seconds_per_audio_minute']} s/min")


def cmd_transcribe(args):
    asr = CFG["asr"]
    glossary = asr["use_glossary"] if args.glossary is None else args.glossary
    vad = asr["vad_threshold"] if args.vad_threshold is None else args.vad_threshold
    for task in args.task:
        for level in args.level:
            transcribe_run(args.corpus, task, level, args.model or asr["model"], args.device or asr["device"],
                           args.compute_type or asr["compute_type"], glossary, vad)


def cmd_bench(args):
    bench = CFG["benchmark"]
    for run in bench["runs"]:
        transcribe_run(args.corpus, bench["task"], "L0", run["model"], run["device"], run["compute_type"],
                       run.get("glossary", CFG["asr"]["use_glossary"]), CFG["asr"]["vad_threshold"])


# --------------------------------------------------------------------------------------
# extract: registros desde transcripciones cacheadas (misma función del motor)
# --------------------------------------------------------------------------------------
def revalidate(out, data):
    """Recalcula verificación y validación sobre campos ya extraídos (sin volver a llamar al LLM)."""
    cached = load_json(out)
    schema = CFG["schemas"][data["meta"]["task"]]
    for cid, rec in cached["clips"].items():
        if rec["fields"] is not None:
            text, segments = data["clips"][cid]["text"], data["clips"][cid]["segments"]
            rec["verified"] = extraction.verify(rec["fields"], text, schema, CFG)
            rec["validation"] = (validation.check_order(rec["fields"], segments, schema, CFG)
                                 if data["meta"]["task"] == "pedido" else None)
    save_json(out, cached)
    print(f"{out.name}: revalidado")


def cmd_extract(args):
    for file in sorted(path("transcripts").glob(f"{args.runs}.json")):
        out = path("records") / f"{file.stem}__{args.extractor}.json"
        if args.revalidate:
            if out.exists():
                revalidate(out, load_json(file))
            continue
        if out.exists() and not args.force:
            continue
        data = load_json(file)
        records = {}
        for cid, clip in data["clips"].items():
            t0 = time.perf_counter()
            try:
                rec = engine.extract_record(clip["text"], data["meta"]["task"], args.extractor, clip["segments"])
                rec["error"] = None
            except Exception as exc:
                rec = {"fields": None, "verified": None, "validation": None, "error": f"{type(exc).__name__}: {exc}"}
            rec["seconds"] = round(time.perf_counter() - t0, 2)
            records[cid] = rec
        model = CFG["llm"]["model"] if args.extractor == "llm" else None
        save_json(out, {"meta": {**data["meta"], "run": file.stem, "extractor": args.extractor, "llm": model},
                        "clips": records})
        print(f"{out.name}: {sum(r['error'] is None for r in records.values())}/{len(records)} clips")


# --------------------------------------------------------------------------------------
# evaluate: las dos capas de métricas, la escalera, el validador y el gate
# --------------------------------------------------------------------------------------
def _gold():
    return {c["id"]: c for t in TASKS for c in ground_truth(t)}


def evaluate_asr(runs, gold):
    rows = []
    for rid, data in runs.items():
        meta, per_clip = data["meta"], {}
        meta.setdefault("vad_threshold", 0.5)            # corridas previas al ajuste usaban el 0.5 de Silero
        for cid, clip in data["clips"].items():
            per_clip[cid] = metrics.wer_cer(gold[cid]["guion"], clip["text"])
        clips = list(per_clip.values())
        terms = [t.strip() for t in CFG["glossary"][meta["task"]].split(",")]
        hits = [metrics.glossary_recall(gold[cid]["guion"], c["text"], terms) for cid, c in data["clips"].items()]
        rows.append({
            "run": rid, **{k: meta[k] for k in ("corpus", "task", "level", "model", "glossary", "vad_threshold",
                                                "device_runtime", "compute_type_requested", "compute_type_runtime",
                                                "gpu", "vram_peak_mb", "seconds_per_audio_minute", "load_seconds")},
            "n_clips": len(clips),
            "wer": round(metrics.pooled_rate(clips), 4),
            "wer_ci": metrics.bootstrap_ci(clips, metrics.pooled_rate, CFG),
            "cer": round(metrics.pooled_rate(clips, "char_errors", "chars"), 4),
            "cer_ci": metrics.bootstrap_ci(clips, lambda r: metrics.pooled_rate(r, "char_errors", "chars"), CFG),
            "glossary_recall": round(sum(h for h, _ in hits) / max(1, sum(n for _, n in hits)), 4),
            "clips": {cid: {"wer": round(m["wer"], 4), "cer": round(m["cer"], 4)} for cid, m in per_clip.items()},
        })
    return rows


def _pairs(asr_rows, key):
    """Corridas idénticas salvo en `key` (p. ej. el dispositivo, la precisión o el glosario).

    La precisión se compara por lo pedido (int8), porque CTranslate2 reporta int8_float32 en CPU
    e int8_float16 en GPU para la misma cuantización de pesos.
    """
    same = ("corpus", "task", "level", "model", "glossary", "vad_threshold", "device_runtime",
            "compute_type_requested")
    groups = {}
    for row in asr_rows:
        groups.setdefault(tuple(row[k] for k in same if k != key), []).append(row)
    return [(a, b) for rows in groups.values() for i, a in enumerate(rows) for b in rows[i + 1:]]


def evaluate_text_changes(asr_rows, runs):
    """¿Cambió el TEXTO al cambiar de dispositivo o de precisión? (no solo la velocidad)."""
    out = []
    for key in ("device_runtime", "compute_type_requested"):
        for a, b in _pairs(asr_rows, key):
            ca, cb = runs[a["run"]]["clips"], runs[b["run"]]["clips"]
            common = sorted(set(ca) & set(cb))
            diffs = [metrics.wer_cer(ca[c]["text"], cb[c]["text"]) for c in common]
            out.append({"cambia": key, "run_a": a["run"], "run_b": b["run"], "clips": len(common),
                        "clips_identicos": sum(d["word_errors"] == 0 for d in diffs),
                        "diferencia_texto_wer": round(metrics.pooled_rate(diffs), 4),
                        "wer_a": a["wer"], "wer_b": b["wer"]})
    return out


def evaluate_effect(asr_rows, key):
    """Efecto de cambiar `key` (glosario o umbral VAD) con todo lo demás igual.

    La mejora es WER(base) - WER(config de referencia) por clip, con IC bootstrap pareado.
    """
    reference = CFG["asr"]["use_glossary"] if key == "glossary" else CFG["asr"]["vad_threshold"]
    out = []
    for a, b in _pairs(asr_rows, key):
        if reference not in (a[key], b[key]):
            continue
        base, new = (a, b) if b[key] == reference else (b, a)
        common = sorted(set(base["clips"]) & set(new["clips"]))
        deltas = [base["clips"][c]["wer"] - new["clips"][c]["wer"] for c in common]
        out.append({"cambia": key, "de": base[key], "a": new[key], "tarea": new["task"], "nivel": new["level"],
                    "modelo": new["model"], "clips": len(common), "wer_antes": base["wer"], "wer_despues": new["wer"],
                    "mejora_wer_media": round(metrics.mean(deltas), 4),
                    "mejora_wer_ci": metrics.bootstrap_ci(deltas, metrics.mean, CFG),
                    "recall_glosario_antes": base["glossary_recall"], "recall_glosario_despues": new["glossary_recall"]})
    return out


def _truth_cause(gold_clip, record_ok):
    """Causa real de un pedido que no cuadra, según la verdad de campo (None si es ambiguo)."""
    planted = "total_erroneo" in gold_clip.get("trampas", [])
    if planted and record_ok:
        return "error_hablante"
    if not planted and not record_ok:
        return "error_asr"
    return None


def evaluate_records(record_files, asr_by_run, gold):
    rows = []
    for file in record_files:
        data = load_json(file)
        meta = data["meta"]
        schema = CFG["schemas"][meta["task"]]
        asr_clips = asr_by_run.get(meta["run"], {}).get("clips", {})
        clips, scored, validator = {}, [], {"caught": 0, "missed": 0, "false_alarms": 0, "correct_pass": 0,
                                            "diagnosis_right": 0, "diagnosis_total": 0}
        for cid, rec in data["clips"].items():
            gold_fields = gold[cid]["campos"]
            score = metrics.score_record(rec["fields"], gold_fields, schema, CFG)
            verified = rec["verified"] or {}
            scored.append((score, verified, rec["fields"] or {}, gold_fields))
            clips[cid] = {"wer": asr_clips.get(cid, {}).get("wer"), "error": rec["error"],
                          "correctos": sum(s["correct"] for s in score.values()), "campos": len(score),
                          "incorrectos": [f for f, s in score.items() if not s["correct"]]}
            if meta["task"] == "pedido":
                record_ok = all(score[f]["correct"] for f in ("items", "promocion", "total_dicho"))
                broken = "total_erroneo" in gold[cid].get("trampas", []) or not record_ok
                state = (rec["validation"] or {}).get("estado")
                flagged = state != "cuadra"
                key = ("caught" if flagged else "missed") if broken else ("false_alarms" if flagged else "correct_pass")
                validator[key] += 1
                truth = _truth_cause(gold[cid], record_ok)
                if state == "no_cuadra" and truth:
                    validator["diagnosis_total"] += 1
                    validator["diagnosis_right"] += rec["validation"]["causa"] == truth
                clips[cid].update(estado=state, causa=(rec["validation"] or {}).get("causa"), roto=broken)
        rows.append(_record_summary(meta, schema, scored, clips, validator))
    return rows


def _record_summary(meta, schema, scored, clips, validator):
    fields = {}
    for name, spec in schema["fields"].items():
        hits = [float(s[name]["correct"]) for s, *_ in scored]
        entry = {"accuracy": round(metrics.mean(hits), 4), "ci": metrics.bootstrap_ci(hits, metrics.mean, CFG)}
        if spec["type"] == "category":
            entry["macro_f1"] = round(metrics.macro_f1([g.get(name) for *_, g in scored],
                                                       [p.get(name) for *_, p, _ in scored]), 4)
        if spec["type"] in ("number", "money"):
            errors = [s[name]["abs_error"] for s, *_ in scored if s[name]["abs_error"] is not None]
            entry["mae"] = round(metrics.mean(errors), 2) if errors else None
        fields[name] = entry
    # ¿La marca "verificado" predice que el dato es correcto?
    pairs = [(v.get(n), s[n]["correct"]) for s, v, *_ in scored for n in schema["fields"] if v.get(n) != "vacio"]
    verified_ok = [ok for st, ok in pairs if st == "verificado"]
    unverified_ok = [ok for st, ok in pairs if st == "sin_verificar"]
    all_hits = [float(s[n]["correct"]) for s, *_ in scored for n in schema["fields"]]
    row = {"run": meta["run"], "extractor": meta["extractor"], "llm": meta.get("llm"),
           **{k: meta[k] for k in ("corpus", "task", "level", "model", "device_runtime", "glossary",
                                   "compute_type_requested")},
           "vad_threshold": meta.get("vad_threshold", 0.5),
           "accuracy": round(metrics.mean(all_hits), 4),
           "accuracy_ci": metrics.bootstrap_ci(all_hits, metrics.mean, CFG),
           "fields": fields,
           "verificados": len(verified_ok), "verificados_correctos": sum(verified_ok),
           "sin_verificar": len(unverified_ok), "sin_verificar_correctos": sum(unverified_ok),
           "clips": clips}
    if meta["task"] == "pedido":
        broken = validator["caught"] + validator["missed"]
        validator["recall"] = round(validator["caught"] / broken, 4) if broken else None
        validator["diagnosis_accuracy"] = (round(validator["diagnosis_right"] / validator["diagnosis_total"], 4)
                                           if validator["diagnosis_total"] else None)
        row["validator"] = validator
    return row


def evaluate_wer_vs_record(record_rows):
    candidates = [(r, cid, c) for r in record_rows for cid, c in r["clips"].items()
                  if c["wer"] is not None and not c["error"]]
    perfect = [x for x in candidates if not x[2]["incorrectos"]]
    broken = [x for x in candidates if x[2]["incorrectos"]]

    def describe(x):
        r, cid, c = x
        return {"run": r["run"], "extractor": r["extractor"], "clip": cid, "wer": c["wer"],
                "incorrectos": c["incorrectos"]}

    return {"wer_alto_registro_perfecto": describe(max(perfect, key=lambda x: x[2]["wer"])) if perfect else None,
            "wer_bajo_registro_roto": describe(min(broken, key=lambda x: x[2]["wer"])) if broken else None}


def evaluate_gate(asr_rows, record_rows):
    gate, checks = CFG["gate"], []
    main = CFG["evaluation"]["main_corpus"]

    def pick(rows, task, **extra):
        return next((r for r in rows if r["corpus"] == main and r["task"] == task and r["level"] == "L0"
                     and is_reference(r) and all(r.get(k) == v for k, v in extra.items())), None)

    for task in TASKS:
        asr, rec = pick(asr_rows, task), pick(record_rows, task, extractor="rules")
        checks.append({"check": f"WER {task} <= {gate['max_wer']}", "value": asr and asr["wer"],
                       "ok": bool(asr) and asr["wer"] <= gate["max_wer"]})
        minimum = gate["min_field_accuracy"][task]
        checks.append({"check": f"exactitud reglas {task} >= {minimum}", "value": rec and rec["accuracy"],
                       "ok": bool(rec) and rec["accuracy"] >= minimum})
        if task == "pedido":
            recall = rec and rec["validator"]["recall"]
            checks.append({"check": f"recall del validador >= {gate['min_validator_recall']}", "value": recall,
                           "ok": recall is not None and recall >= gate["min_validator_recall"]})
    return {"corpus": main, "checks": checks, "passed": all(c["ok"] for c in checks)}


def cmd_evaluate(args):
    gold = _gold()
    runs = {f.stem: load_json(f) for f in sorted(path("transcripts").glob("*.json"))}
    asr_rows = evaluate_asr(runs, gold)
    asr_by_run = {r["run"]: r for r in asr_rows}
    record_rows = evaluate_records(sorted(path("records").glob("*.json")), asr_by_run, gold)
    main = CFG["evaluation"]["main_corpus"]
    result = {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "main_corpus": main,
        "asr": asr_rows,
        "text_changes": evaluate_text_changes(asr_rows, runs),
        "glossary_effect": evaluate_effect(asr_rows, "glossary"),
        "vad_effect": evaluate_effect(asr_rows, "vad_threshold"),
        "records": record_rows,
        "wer_vs_record": evaluate_wer_vs_record([r for r in record_rows if r["corpus"] == main]),
        "gate": evaluate_gate(asr_rows, record_rows),
    }
    save_json(path("metrics"), result)
    path("summary").write_text(render_summary(result), encoding="utf-8")
    print(f"métricas -> {CFG['paths']['metrics']} y {CFG['paths']['summary']}")
    for check in result["gate"]["checks"]:
        print(f"  [{'OK' if check['ok'] else 'FALLA'}] {check['check']}: {check['value']}")
    if args.gate and not result["gate"]["passed"]:
        sys.exit(1)


# --------------------------------------------------------------------------------------
# Resumen en Markdown (lo que se copia al README)
# --------------------------------------------------------------------------------------
def _table(rows):
    import pandas as pd
    return pd.DataFrame(rows).to_markdown(index=False) if rows else "_sin datos_"


def _ci(ci):
    return f"[{ci[0]:.3f}, {ci[1]:.3f}]" if ci and ci[0] is not None else "—"


def gt_distribution():
    """Distribución de cada campo de la verdad de campo (Fase 1)."""
    from collections import Counter
    rows = []
    for task in TASKS:
        clips = ground_truth(task)
        for field in clips[0]["campos"]:
            values = []
            for clip in clips:
                v = clip["campos"][field]
                if field == "items":
                    values += [f"{it['cantidad']}× {it['producto']} {it['tamano'] or ''}".strip() for it in v]
                elif isinstance(v, dict):
                    values.append(f"{v['monto']} {v['moneda']}")
                else:
                    values += v if isinstance(v, list) else [v]
            counts = Counter(str(v) for v in values)
            rows.append({"tarea": task, "campo": field, "distribución": ", ".join(f"{k} ×{n}" for k, n in counts.items())})
        traps = Counter(t for clip in clips for t in clip.get("trampas", []))
        if traps:
            rows.append({"tarea": task, "campo": "trampas", "distribución": ", ".join(f"{k} ×{n}" for k, n in traps.items())})
    return rows


def render_summary(m):
    main = m["main_corpus"]
    asr = [{"corpus": r["corpus"], "tarea": r["task"], "modelo": r["model"],  # el eje de acentos va aparte
            "dispositivo (runtime)": r["device_runtime"], "precisión (runtime)": r["compute_type_runtime"],
            "glosario": r["glossary"], "VAD": r["vad_threshold"], "WER": r["wer"], "IC95 WER": _ci(r["wer_ci"]),
            "CER": r["cer"], "s/min audio": r["seconds_per_audio_minute"], "VRAM pico MB": r["vram_peak_mb"],
            "GPU": r["gpu"]}
           for r in m["asr"] if r["level"] == "L0" and (r["corpus"] == main or not r["corpus"].startswith("tts-"))]
    main_records = [r for r in m["records"] if r["level"] == "L0" and r["corpus"] == main and is_reference(r)]
    records = [{"tarea": r["task"], "extractor": r["extractor"], "exactitud": r["accuracy"],
                "IC95": _ci(r["accuracy_ci"]), **{f: v["accuracy"] for f, v in r["fields"].items()},
                "verificados y correctos": f"{r['verificados_correctos']}/{r['verificados']}",
                "sin_verificar y correctos": f"{r['sin_verificar_correctos']}/{r['sin_verificar']}"}
               for r in main_records]
    extras = [{"tarea": r["task"], "extractor": r["extractor"],
               **{f"F1 macro {f}": v["macro_f1"] for f, v in r["fields"].items() if "macro_f1" in v},
               **{f"MAE {f}": v["mae"] for f, v in r["fields"].items() if "mae" in v}}
              for r in main_records]
    ladder = [{"nivel": r["level"], "extractor": r["extractor"], "WER": m_wer,
               "exactitud registro": r["accuracy"], "items": r["fields"]["items"]["accuracy"],
               "total_dicho": r["fields"]["total_dicho"]["accuracy"],
               "atrapados": r["validator"]["caught"], "escapados": r["validator"]["missed"],
               "falsas alarmas": r["validator"]["false_alarms"],
               "diagnóstico ok": f"{r['validator']['diagnosis_right']}/{r['validator']['diagnosis_total']}"}
              for r in sorted(m["records"], key=lambda r: (r["level"], r["extractor"]))
              if r["task"] == "pedido" and r["corpus"] == main and is_reference(r)
              for m_wer in [next((a["wer"] for a in m["asr"] if a["run"] == r["run"]), None)]]
    accents = [{"locale": r["corpus"].removeprefix("tts-"), "tarea": r["task"], "WER": r["wer"],
                "IC95": _ci(r["wer_ci"]), "CER": r["cer"]}
               for r in m["asr"] if r["corpus"].startswith("tts-") and r["level"] == "L0" and is_reference(r)]
    glossary = [{**g, "mejora_wer_ci": _ci(g["mejora_wer_ci"])} for g in m["glossary_effect"]]
    vad = [{**g, "mejora_wer_ci": _ci(g["mejora_wer_ci"])} for g in m["vad_effect"]]
    changes = [{**{k: v for k, v in c.items() if not k.startswith("run")},
                "a": c["run_a"], "b": c["run_b"]} for c in m["text_changes"]]
    gate = [{"chequeo": c["check"], "valor": c["value"], "ok": c["ok"]} for c in m["gate"]["checks"]]
    wvr = m["wer_vs_record"]
    return "\n\n".join([
        f"# Resultados (corpus principal: `{main}`)\n\nGenerado: {m['generated']}. "
        "Regenerar con `python pipeline.py evaluate`.",
        "## Verdad de campo: distribución de cada campo\n\n" + _table(gt_distribution()),
        "## Capa 1 — Transcripción (L0)\n\n" + _table(asr),
        "## Capa 2 — Registro (exactitud por campo, L0)\n\n" + _table(records),
        "### F1 macro (categóricos) y error absoluto medio (numéricos)\n\n" + _table(extras),
        "## Glosario (hotwords): mejora de WER, IC95 bootstrap pareado por clip\n\n" + _table(glossary),
        "## Umbral del VAD: mejora de WER al bajarlo de 0.5 a 0.25\n\n" + _table(vad),
        "## ¿Cambia el texto con el dispositivo o la precisión?\n\n" + _table(changes),
        "## Escalera de degradación y validador aritmético (pedidos)\n\n" + _table(ladder),
        "## WER no predice si el registro sirve\n\n```json\n" + json.dumps(wvr, ensure_ascii=False, indent=1) + "\n```",
        "## Eje de acentos (voces sintéticas, NO hablantes humanos)\n\n" + _table(accents),
        f"## Gate de regresión: {'PASA' if m['gate']['passed'] else 'FALLA'}\n\n" + _table(gate),
    ]) + "\n"


# --------------------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("tts", help="genera clips sintéticos con Edge TTS")
    p.add_argument("--locales", nargs="+", default=["es-PE"])
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_tts)

    p = sub.add_parser("ladder", help="genera la escalera L1-L3 de las llamadas")
    p.add_argument("--corpus", default=CFG["evaluation"]["main_corpus"])
    p.set_defaults(func=cmd_ladder)

    p = sub.add_parser("transcribe", help="transcribe un corpus y cachea el resultado")
    p.add_argument("--corpus", default=CFG["evaluation"]["main_corpus"])
    p.add_argument("--task", nargs="+", default=list(TASKS), choices=TASKS)
    p.add_argument("--level", nargs="+", default=["L0"])
    p.add_argument("--model")
    p.add_argument("--device")
    p.add_argument("--compute-type")
    p.add_argument("--glossary", action=argparse.BooleanOptionalAction, default=None)
    p.add_argument("--vad-threshold", type=float)
    p.set_defaults(func=cmd_transcribe)

    p = sub.add_parser("bench", help="rejilla de modelo/dispositivo/precisión de config.yaml")
    p.add_argument("--corpus", default=CFG["evaluation"]["main_corpus"])
    p.set_defaults(func=cmd_bench)

    p = sub.add_parser("extract", help="extrae registros de las transcripciones cacheadas")
    p.add_argument("--extractor", choices=["rules", "llm"], default="rules")
    p.add_argument("--runs", default="*", help="patrón glob sobre los nombres de corrida")
    p.add_argument("--force", action="store_true", help="vuelve a extraer aunque exista el registro")
    p.add_argument("--revalidate", action="store_true", help="solo recalcula verificación y validación")
    p.set_defaults(func=cmd_extract)

    p = sub.add_parser("evaluate", help="calcula métricas; con --gate falla si bajan del umbral")
    p.add_argument("--gate", action="store_true")
    p.set_defaults(func=cmd_evaluate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
