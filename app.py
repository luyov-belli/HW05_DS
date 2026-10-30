"""App Streamlit. Lee resultados precalculados (no re-transcribe el corpus al arrancar).
Solo la pestaña "Probador" llama al motor, con la misma función que usa el pipeline.

    streamlit run app.py
"""
import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
import yaml

import engine

CFG = engine.load_config()
ROOT = engine.ROOT
TASKS = {"entrevista": "Tarea 1 — Entrevistas", "pedido": "Tarea 2 — Llamadas de venta"}
STATUS_ICON = {"verificado": "✅ verificado", "sin_verificar": "⚠️ sin_verificar", "vacio": "— vacío"}

st.set_page_config(page_title="De la voz al registro", page_icon="🎙️", layout="wide")


@st.cache_data
def load_json(path):
    path = ROOT / path
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


@st.cache_data
def ground_truth(task):
    with open(ROOT / CFG["paths"]["ground_truth"][task], encoding="utf-8") as f:
        return yaml.safe_load(f)


def find_run(metrics, task, level="L0"):
    """Corrida de referencia: corpus principal, modelo y glosario por defecto de config.yaml."""
    rows = [r for r in metrics["asr"] if r["corpus"] == metrics["main_corpus"] and r["task"] == task
            and r["level"] == level and r["model"] == CFG["asr"]["model"]
            and r["glossary"] == CFG["asr"]["use_glossary"]]
    return rows[0]["run"] if rows else None


def audio_for(clip_id, corpus):
    real = sorted((ROOT / CFG["paths"]["audio_real"]).glob(f"{clip_id}.*"))
    if real:
        return real[0], "grabación real"
    tts = ROOT / CFG["paths"]["audio_tts"] / corpus.removeprefix("tts-") / f"{clip_id}.wav"
    return (tts, "sintético (Edge TTS)") if tts.exists() else (None, None)


def show_record(fields, verified):
    rows = [{"campo": k, "valor": json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v,
             "verificación": STATUS_ICON.get((verified or {}).get(k), "")} for k, v in (fields or {}).items()]
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)


def show_validation(check):
    if not check:
        return
    label = {"cuadra": "✅ El pedido cuadra", "no_cuadra": "🚨 El pedido NO cuadra",
             "incompleto": "⚠️ No se puede validar"}[check["estado"]]
    st.markdown(f"**{label}**")
    if check["estado"] != "incompleto":
        cols = st.columns(4)
        cols[0].metric("Subtotal", check["subtotal"])
        cols[1].metric("Descuento", check["descuento"])
        cols[2].metric("Total calculado", check["total_calculado"])
        cols[3].metric("Total dicho", check["total_dicho"], delta=check["diferencia"] or None)
    if check.get("causa"):
        st.markdown(f"Diagnóstico: **{check['causa']}**")
    for reason in check.get("motivos", []):
        st.caption(f"• {reason}")
    for fix in check.get("correcciones", []):                  # solo con diarización activada
        st.caption(f"🗣️ corrección del {fix['rol']} ({fix['hablante']}): {fix['texto']}")


metrics = load_json(CFG["paths"]["metrics"])
st.title("De la voz al registro")
st.caption("Entrevistas y llamadas de venta → registros verificados. Todo el contenido de los audios es inventado.")
if metrics is None:
    st.error("No hay resultados precalculados. Corre `python pipeline.py evaluate` primero.")
    st.stop()

tab_method, tab_corpus, tab_results, tab_orders, tab_tester = st.tabs(
    ["Problema y método", "Corpus", "Resultados", "Pedidos", "Probador"])

with tab_method:
    st.markdown(f"""
### El problema
El teléfono ya transcribe, pero **transcribir no es registrar**: nadie convierte esas notas de voz en
filas verificadas de una tabla. Este sistema recibe un audio y devuelve un **registro** con sus campos,
**cuáles se verificaron literalmente** en la transcripción y, en los pedidos, si **la aritmética cuadra**.

### El método (un solo motor, dos esquemas)
1. **ASR** — `faster-whisper` (`{CFG['asr']['model']}` por defecto) con glosario de dominio como *hotwords*.
2. **Normalización** — minúsculas, sin tildes ni puntuación, números en palabras → dígitos
   (*seis mil quinientos* → `6500`).
3. **Extracción** — por **reglas** (regex + vocabularios) o por **LLM local** (`{CFG['llm']['model']}` vía Ollama, JSON).
4. **Verificación literal** — un valor que no aparece en la transcripción queda `sin_verificar`.
5. **Validación aritmética** (pedidos) — Σ cantidad × precio − promoción = total dicho; si no cuadra,
   diagnostica si el error fue del **ASR** o de **quien habló**.

El mismo `engine.process(audio, tarea)` sirve a las dos tareas: lo único que cambia es el esquema en `config.yaml`.

**Corpus principal de estas tablas:** `{metrics['main_corpus']}`.
""")

with tab_corpus:
    task = st.radio("Tarea", list(TASKS), format_func=TASKS.get, horizontal=True, key="corpus_task")
    clips = ground_truth(task)
    run_id = find_run(metrics, task)
    run = load_json(f"{CFG['paths']['transcripts']}/{run_id}.json") if run_id else None
    clip = st.selectbox("Clip", clips, format_func=lambda c: f"{c['id']} — {c.get('variacion') or c.get('nota')}")
    audio, kind = audio_for(clip["id"], metrics["main_corpus"])
    if audio:
        st.caption(f"Audio: {kind}")
        st.audio(str(audio))
    else:
        st.info("El audio no está en el repositorio (ver README: cómo regenerarlo o pedirlo).")
    left, right = st.columns(2)
    left.markdown("**Transcripción de referencia (guion)**")
    left.text(clip["guion"])
    right.markdown(f"**Transcripción ASR** ({run_id or 'sin corrida'})")
    right.text(run["clips"].get(clip["id"], {}).get("text", "—") if run else "—")
    st.markdown("**Verdad de campo**")
    st.json(clip["campos"])
    st.markdown("**Distribución de cada campo en el corpus**")
    for field in clips[0]["campos"]:
        values = [c["campos"][field] for c in clips]
        flat = [json.dumps(x, ensure_ascii=False) if isinstance(x, dict) else x
                for v in values for x in (v if isinstance(v, list) else [v])]
        st.caption(f"`{field}`: " + ", ".join(f"{k} ×{n}" for k, n in pd.Series(flat).astype(str).value_counts().items()))

with tab_results:
    asr = pd.DataFrame(metrics["asr"])
    st.subheader("Capa 1 — Transcripción")
    st.dataframe(asr[["corpus", "task", "level", "model", "device_runtime", "compute_type_runtime", "glossary",
                      "wer", "wer_ci", "cer", "seconds_per_audio_minute", "vram_peak_mb", "gpu"]],
                 hide_index=True, use_container_width=True)
    st.subheader("Capa 2 — Registro")
    rec = pd.DataFrame([{**{k: r[k] for k in ("corpus", "task", "level", "extractor", "model", "accuracy",
                                                "accuracy_ci")},
                         **{f: v["accuracy"] for f, v in r["fields"].items()}} for r in metrics["records"]])
    st.dataframe(rec, hide_index=True, use_container_width=True)
    st.subheader("Glosario (hotwords) — mejora de WER con IC95")
    st.dataframe(pd.DataFrame(metrics["glossary_effect"]), hide_index=True, use_container_width=True)
    st.subheader("¿Cambia el texto con el dispositivo o la precisión?")
    st.dataframe(pd.DataFrame(metrics["text_changes"]), hide_index=True, use_container_width=True)
    st.subheader("El WER no predice si el registro sirve")
    st.json(metrics["wer_vs_record"])

with tab_orders:
    main = metrics["main_corpus"]
    rows = [r for r in metrics["records"] if r["task"] == "pedido" and r["corpus"] == main]
    wer_of = {a["run"]: a["wer"] for a in metrics["asr"]}
    ladder = pd.DataFrame([{"nivel": r["level"], "extractor": r["extractor"], "WER": wer_of.get(r["run"]),
                            "exactitud registro": r["accuracy"], **{k: r["validator"][k] for k in
                            ("caught", "missed", "false_alarms", "correct_pass", "recall", "diagnosis_accuracy")}}
                           for r in sorted(rows, key=lambda r: r["level"])])
    if ladder.empty:
        st.info("Aún no hay resultados de la escalera.")
    else:
        st.subheader("Escalera de degradación")
        chart = ladder.pivot_table(index="nivel", columns="extractor", values="exactitud registro")
        chart["WER"] = ladder.groupby("nivel")["WER"].first()
        st.line_chart(chart)
        st.subheader("Validador aritmético: atrapados vs. escapados")
        st.dataframe(ladder, hide_index=True, use_container_width=True)
        pick = st.selectbox("Ver detalle", rows, format_func=lambda r: f"{r['level']} · {r['extractor']}")
        records = load_json(f"{CFG['paths']['records']}/{pick['run']}__{pick['extractor']}.json")
        gold = {c["id"]: c for c in ground_truth("pedido")}
        for cid, rec in records["clips"].items():
            with st.expander(f"{cid} — trampas: {', '.join(gold[cid].get('trampas', [])) or 'ninguna'} — "
                             f"{(rec['validation'] or {}).get('estado')}"):
                show_record(rec["fields"], rec["verified"])
                show_validation(rec["validation"])

with tab_tester:
    st.markdown("Sube un audio y el **mismo motor** devuelve la transcripción, el registro y qué se verificó.")
    c1, c2, c3 = st.columns(3)
    task = c1.selectbox("Tarea", list(TASKS), format_func=TASKS.get)
    extractor = c2.selectbox("Extractor", ["rules", "llm"], help="llm requiere Ollama corriendo")
    model = c3.text_input("Modelo Whisper", CFG["app"]["model"])
    upload = st.file_uploader("Audio (wav, mp3, m4a, ogg, opus)", type=["wav", "mp3", "m4a", "ogg", "opus", "webm"])
    if upload and upload.size > CFG["app"]["max_upload_mb"] * 2 ** 20:
        st.error(f"El archivo supera {CFG['app']['max_upload_mb']} MB.")
    elif upload and st.button("Procesar", type="primary"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / upload.name
            path.write_bytes(upload.getvalue())
            with st.spinner("Transcribiendo y extrayendo…"):
                result = engine.process(path, task, extractor, model=model)
        if result["error"]:
            st.error(result["error"])
        st.caption(f"Dispositivo: {result['device']} · precisión: {result['compute_type']} · "
                   f"modelo: {result['model']} · {result['elapsed_seconds']} s")
        st.markdown("**Transcripción**")
        st.write(result["transcript"])
        st.markdown("**Registro**")
        show_record(result["fields"], result["verified"])
        show_validation(result["validation"])
