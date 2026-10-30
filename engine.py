"""Motor único de las dos tareas: audio -> transcripción -> registro verificado.

La función pública es `process(audio_path, task)`. La app, el pipeline por lotes y el
servidor MCP la usan tal cual. Este módulo no importa ninguna librería de interfaz;
se comprueba con:  python -c "import engine, sys; assert 'streamlit' not in sys.modules"
"""
import functools
import os
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv

import extraction
import validation

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")                       # HF_TOKEN, LLM_API_KEY: nunca en el código


@functools.cache
def load_config(path="config.yaml"):
    with open(ROOT / path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_device(device):
    """'auto' -> 'cuda' si CTranslate2 ve una GPU, si no 'cpu'."""
    if device != "auto":
        return device
    import ctranslate2
    return "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"


def resolve_compute_type(compute_type, device):
    if compute_type != "auto":
        return compute_type
    return "float16" if device == "cuda" else "int8"


@functools.lru_cache(maxsize=2)
def load_model(name, device, compute_type):
    from faster_whisper import WhisperModel     # import local: la app arranca sin cargar el modelo
    return WhisperModel(name, device=device, compute_type=compute_type)


def transcribe(audio_path, task, model=None, device=None, compute_type=None, glossary=None, vad_threshold=None):
    """Transcribe un audio con faster-whisper y devuelve texto, segmentos y evidencia del dispositivo.

    `device` y `compute_type` del resultado se leen del modelo ya cargado (CTranslate2),
    no de la configuración: si la GPU no estuviera disponible, aquí se vería.
    """
    asr = load_config()["asr"]
    device = resolve_device(device or asr["device"])
    compute_type = resolve_compute_type(compute_type or asr["compute_type"], device)
    use_glossary = asr["use_glossary"] if glossary is None else glossary
    vad_threshold = asr["vad_threshold"] if vad_threshold is None else vad_threshold
    name = model or asr["model"]

    t0 = time.perf_counter()
    whisper = load_model(name, device, compute_type)
    load_seconds = time.perf_counter() - t0

    t0 = time.perf_counter()
    segments, info = whisper.transcribe(
        str(audio_path),
        language=asr["language"],
        beam_size=asr["beam_size"],
        vad_filter=asr["vad_filter"],
        vad_parameters={"threshold": vad_threshold},
        word_timestamps=True,                   # da la probabilidad de cada palabra
        hotwords=load_config()["glossary"][task] if use_glossary else None,
    )
    segments = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
                 "words": [{"word": w.word, "probability": round(w.probability, 3)} for w in s.words or []]}
                for s in segments]               # el generador recién transcribe al recorrerse
    asr_seconds = time.perf_counter() - t0

    return {
        "text": " ".join(s["text"] for s in segments),
        "segments": segments,
        "model": name,
        "device": whisper.model.device,          # leído de la librería en tiempo de ejecución
        "compute_type": whisper.model.compute_type,
        "glossary": use_glossary,
        "vad_threshold": vad_threshold,
        "audio_seconds": round(info.duration, 2),
        "asr_seconds": round(asr_seconds, 2),
        "load_seconds": round(load_seconds, 2),
    }


def diarize(audio_path, segments):
    """Añade 'speaker' a cada segmento con pyannote (opcional: requiere HF_TOKEN)."""
    cfg = load_config()["diarization"]
    import torch
    from faster_whisper import decode_audio

    pipeline = _diarization_pipeline(cfg["model"])
    waveform = torch.from_numpy(decode_audio(str(audio_path))).unsqueeze(0)
    output = pipeline({"waveform": waveform, "sample_rate": 16000}, num_speakers=cfg["num_speakers"])
    turns = getattr(output, "speaker_diarization", output)      # pyannote 4.x vs 3.x
    turns = [(t.start, t.end, label) for t, _, label in turns.itertracks(yield_label=True)]
    for seg in segments:
        overlap = {}
        for start, end, label in turns:
            overlap[label] = overlap.get(label, 0) + max(0.0, min(end, seg["end"]) - max(start, seg["start"]))
        seg["speaker"] = max(overlap, key=overlap.get) if overlap else None
    return segments


def attribute_corrections(segments):
    """¿Quién se corrigió? En una llamada entrante habla primero quien atiende (el vendedor)."""
    cues = load_config()["diarization"]["correction_cues"]
    seller = next((s.get("speaker") for s in segments if s.get("speaker")), None)
    return [{"texto": s["text"], "hablante": s["speaker"],
             "rol": "vendedor" if s["speaker"] == seller else "cliente"}
            for s in segments if s.get("speaker")
            and any(extraction.has_phrase(extraction.normalize(s["text"]), c) for c in cues)]


@functools.cache
def _diarization_pipeline(name):
    from pyannote.audio import Pipeline
    return Pipeline.from_pretrained(name, token=os.getenv("HF_TOKEN"))


def extract_record(transcript, task, extractor="rules", segments=None):
    """Texto -> campos + qué campos se verificaron + validación aritmética (solo pedidos)."""
    cfg = load_config()
    schema = cfg["schemas"][task]
    fields = extraction.extract(transcript, schema, extractor, cfg)
    return {
        "fields": fields,
        "verified": extraction.verify(fields, transcript, schema, cfg),
        "validation": validation.check_order(fields, segments, schema, cfg) if task == "pedido" else None,
    }


def process(audio_path, task="entrevista", extractor="rules", model=None):
    """Función pública del motor: ruta de audio -> resultado estructurado.

    Nunca lanza excepciones: si algo falla, el motivo queda en result['error'].
    """
    result = {"audio": str(audio_path), "task": task, "extractor": extractor, "transcript": None,
              "segments": None, "fields": None, "verified": None, "validation": None,
              "model": None, "device": None, "compute_type": None, "elapsed_seconds": None, "error": None}
    t0 = time.perf_counter()
    try:
        if task not in load_config()["schemas"]:
            raise ValueError(f"tarea desconocida: {task}")
        asr = transcribe(audio_path, task, model=model)
        diarizing = load_config()["diarization"]["enabled"] and bool(os.getenv("HF_TOKEN"))  # sin token (app pública): se omite
        if diarizing:
            asr["segments"] = diarize(audio_path, asr["segments"])
        result.update(transcript=asr["text"], segments=asr["segments"], model=asr["model"],
                      device=asr["device"], compute_type=asr["compute_type"])
        result.update(extract_record(asr["text"], task, extractor, asr["segments"]))
        if task == "pedido" and diarizing:
            result["validation"]["correcciones"] = attribute_corrections(asr["segments"])
    except Exception as exc:                     # el error viaja en el resultado, no rompe la app
        result["error"] = f"{type(exc).__name__}: {exc}"
    result["elapsed_seconds"] = round(time.perf_counter() - t0, 2)
    return result
