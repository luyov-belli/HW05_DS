# Resultados (corpus principal: `real`)

Generado: 2026-11-02T01:04:58+00:00. Regenerar con `python pipeline.py evaluate`.

## Verdad de campo: distribución de cada campo

| tarea      | campo               | distribución                                                                                                                                                                                                                                                      |
|:-----------|:--------------------|:------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| entrevista | grabaciones         | E01 P1 138 s, E02 P3 141 s, E03 P2 102 s, E04 P4 104 s                                                                                                                                                                                                            |
| entrevista | anios_experiencia   | 4 ×1, 5.5 ×1, 8 ×1, 2 ×1                                                                                                                                                                                                                                          |
| entrevista | ultimo_puesto       | analista de datos ×1, desarrolladora backend ×1, jefe de proyectos ×1, ingeniero de datos junior ×1                                                                                                                                                               |
| entrevista | tecnologias         | Python ×2, SQL ×1, Power BI ×1, Java ×1, Spring Boot ×1, PostgreSQL ×1, Docker ×1, Kubernetes ×1, Jira ×1, Excel ×1, SAP ×1, Airflow ×1, Spark ×1, AWS ×1                                                                                                         |
| entrevista | pretension_salarial | 6500 PEN ×1, 3000 USD ×1, 9000 PEN ×1, 4200 PEN ×1                                                                                                                                                                                                                |
| entrevista | disponibilidad      | 2_semanas ×1, 1_mes ×1, inmediata ×1, 2_meses ×1                                                                                                                                                                                                                  |
| entrevista | nivel_ingles        | intermedio ×1, avanzado ×2, basico ×1                                                                                                                                                                                                                             |
| pedido     | grabaciones         | L01 P1 97 s, L02 P3 82 s, L03 P2 79 s, L04 P4 80 s                                                                                                                                                                                                                |
| pedido     | items               | 1× pollo a la brasa entero ×2, 1× papas fritas familiar ×1, 1× chicha morada jarra ×2, 2× pollo a la brasa cuarto ×1, 2× chicha morada vaso ×1, 1× ensalada ×1, 2× anticuchos ×1, 1× gaseosa grande ×1, 2× pollo a la brasa medio ×1, 2× papas fritas personal ×1 |
| pedido     | promocion           | None ×1, martes brasero ×1, combo familiar ×1, cupon de bienvenida ×1                                                                                                                                                                                             |
| pedido     | direccion_entrega   | avenida los proceres 845 santiago de surco ×1, jiron huascar 1450 departamento 302 jesus maria ×1, calle las begonias 2280 san isidro ×1, avenida brasil 3021 pueblo libre ×1                                                                                     |
| pedido     | metodo_pago         | yape ×1, tarjeta ×1, efectivo ×1, plin ×1                                                                                                                                                                                                                         |
| pedido     | total_dicho         | 103 ×1, 62.5 ×1, 127 ×1, 91 ×1                                                                                                                                                                                                                                    |
| pedido     | trampas             | correccion ×3, total_erroneo ×3                                                                                                                                                                                                                                   |

## Capa 1 — Transcripción (L0)

| corpus   | tarea      | modelo   | dispositivo (runtime)   | precisión (runtime)   | glosario   |   VAD |    WER | IC95 WER       |    CER |   s/min audio | VRAM pico MB   | GPU   |
|:---------|:-----------|:---------|:------------------------|:----------------------|:-----------|------:|-------:|:---------------|-------:|--------------:|:---------------|:------|
| real     | entrevista | base     | cpu                     | int8_float32          | True       |  0.25 | 0.15   | [0.112, 0.193] | 0.0671 |          6.78 |                |       |
| real     | entrevista | small    | cpu                     | float32               | True       |  0.25 | 0.0662 | [0.037, 0.089] | 0.0271 |         28.89 |                |       |
| real     | entrevista | small    | cpu                     | int8_float32          | True       |  0.25 | 0.0691 | [0.040, 0.089] | 0.0305 |         59.27 |                |       |
| real     | entrevista | small    | cpu                     | int8_float32          | False      |  0.25 | 0.0808 | [0.054, 0.102] | 0.0346 |         14.92 |                |       |
| real     | pedido     | small    | cpu                     | int8_float32          | True       |  0.25 | 0.0905 | [0.056, 0.126] | 0.0408 |         27.35 |                |       |
| real     | pedido     | small    | cpu                     | int8_float32          | False      |  0.25 | 0.1117 | [0.085, 0.135] | 0.0467 |         15.19 |                |       |

## Capa 2 — Registro (exactitud por campo, L0)

| tarea      | extractor   |   exactitud | IC95           |   anios_experiencia |   ultimo_puesto |   tecnologias |   pretension_salarial |   disponibilidad |   nivel_ingles | verificados y correctos   | sin_verificar y correctos   |   items |   promocion |   direccion_entrega |   metodo_pago |   total_dicho |
|:-----------|:------------|------------:|:---------------|--------------------:|----------------:|--------------:|----------------------:|-----------------:|---------------:|:--------------------------|:----------------------------|--------:|------------:|--------------------:|--------------:|--------------:|
| entrevista | llm         |       0.875 | [0.750, 1.000] |                0.75 |            1    |          0.75 |                     1 |                1 |           0.75 | 20/21                     | 1/3                         |   nan   |         nan |               nan   |           nan |           nan |
| entrevista | rules       |       0.75  | [0.583, 0.917] |                0.5  |            0.75 |          0.25 |                     1 |                1 |           1    | 18/24                     | 0/0                         |   nan   |         nan |               nan   |           nan |           nan |
| pedido     | llm         |       0.8   | [0.600, 0.950] |              nan    |          nan    |        nan    |                   nan |              nan |         nan    | 15/17                     | 0/2                         |     0.5 |           1 |                 0.5 |             1 |             1 |
| pedido     | rules       |       0.9   | [0.750, 1.000] |              nan    |          nan    |        nan    |                   nan |              nan |         nan    | 17/19                     | 0/0                         |     1   |           1 |                 0.5 |             1 |             1 |

### F1 macro (categóricos) y error absoluto medio (numéricos)

| tarea      | extractor   |   F1 macro disponibilidad |   F1 macro nivel_ingles |   MAE anios_experiencia |   MAE pretension_salarial |   F1 macro promocion |   F1 macro metodo_pago |   MAE total_dicho |
|:-----------|:------------|--------------------------:|------------------------:|------------------------:|--------------------------:|---------------------:|-----------------------:|------------------:|
| entrevista | llm         |                         1 |                  0.7778 |                    0.12 |                         0 |                  nan |                    nan |               nan |
| entrevista | rules       |                         1 |                  1      |                    1    |                         0 |                  nan |                    nan |               nan |
| pedido     | llm         |                       nan |                nan      |                  nan    |                       nan |                    1 |                      1 |                 0 |
| pedido     | rules       |                       nan |                nan      |                  nan    |                       nan |                    1 |                      1 |                 0 |

## Glosario (hotwords): mejora de WER, IC95 bootstrap pareado por clip

| corpus    | cambia   | de    | a    | tarea      | nivel   | modelo   |   clips |   wer_antes |   wer_despues |   mejora_wer_media | mejora_wer_ci   |   recall_glosario_antes |   recall_glosario_despues |
|:----------|:---------|:------|:-----|:-----------|:--------|:---------|--------:|------------:|--------------:|-------------------:|:----------------|------------------------:|--------------------------:|
| real      | glossary | False | True | entrevista | L0      | small    |       4 |      0.0808 |        0.0691 |             0.0107 | [0.001, 0.017]  |                  0.9474 |                    1      |
| real      | glossary | False | True | pedido     | L0      | small    |       4 |      0.1117 |        0.0905 |             0.0203 | [-0.003, 0.061] |                  0.5294 |                    0.8824 |
| tts-es-PE | glossary | False | True | entrevista | L0      | small    |       5 |      0.0113 |        0.0056 |             0.0061 | [0.003, 0.009]  |                  0.7083 |                    0.7917 |
| tts-es-PE | glossary | False | True | pedido     | L0      | small    |       5 |      0.0181 |        0.006  |             0.0113 | [0.004, 0.018]  |                  0.7368 |                    1      |

## Umbral del VAD: mejora de WER al bajarlo de 0.5 a 0.25

| corpus    | cambia        |   de |    a | tarea      | nivel   | modelo   |   clips |   wer_antes |   wer_despues |   mejora_wer_media | mejora_wer_ci   |   recall_glosario_antes |   recall_glosario_despues |
|:----------|:--------------|-----:|-----:|:-----------|:--------|:---------|--------:|------------:|--------------:|-------------------:|:----------------|------------------------:|--------------------------:|
| real      | vad_threshold |  0.5 | 0.25 | pedido     | L2      | small    |       4 |      0.1386 |        0.1132 |             0.0254 | [0.011, 0.041]  |                  0.9412 |                    0.9412 |
| tts-es-PE | vad_threshold |  0.5 | 0.25 | entrevista | L0      | small    |       5 |      0.0056 |        0.0056 |             0      | [0.000, 0.000]  |                  0.7917 |                    0.7917 |
| tts-es-PE | vad_threshold |  0.5 | 0.25 | pedido     | L0      | small    |       5 |      0.006  |        0.006  |             0      | [0.000, 0.000]  |                  1      |                    1      |
| tts-es-PE | vad_threshold |  0.5 | 0.25 | pedido     | L1      | small    |       5 |      0.0096 |        0.0096 |             0      | [0.000, 0.000]  |                  1      |                    1      |
| tts-es-PE | vad_threshold |  0.5 | 0.25 | pedido     | L2      | small    |       5 |      0.6145 |        0.0133 |             0.6059 | [0.563, 0.652]  |                  0.6842 |                    1      |
| tts-es-PE | vad_threshold |  0.5 | 0.25 | pedido     | L3      | small    |       5 |      0.212  |        0.212  |             0      | [0.000, 0.000]  |                  0.8947 |                    0.8947 |

## ¿Cambia el texto con el dispositivo o la precisión?

| corpus    | cambia                 |   clips |   clips_identicos |   diferencia_texto_wer |   wer_a |   wer_b | a                                                        | b                                                     |
|:----------|:-----------------------|--------:|------------------:|-----------------------:|--------:|--------:|:---------------------------------------------------------|:------------------------------------------------------|
| real      | compute_type_requested |       4 |                 0 |                 0.0194 |  0.0662 |  0.0691 | real__entrevista__L0__small__cpu__float32__glosario      | real__entrevista__L0__small__cpu__int8__glosario      |
| tts-es-PE | compute_type_requested |       5 |                 3 |                 0.0324 |  0.0363 |  0.0056 | tts-es-PE__entrevista__L0__small__cpu__float32__glosario | tts-es-PE__entrevista__L0__small__cpu__int8__glosario |

## Escalera de degradación y validador aritmético (pedidos)

| nivel   | extractor   |    WER |   exactitud registro |   items |   total_dicho |   atrapados |   escapados |   falsas alarmas | diagnóstico ok   |
|:--------|:------------|-------:|---------------------:|--------:|--------------:|------------:|------------:|-----------------:|:-----------------|
| L0      | llm         | 0.0905 |                 0.8  |    0.5  |          1    |           3 |           0 |                0 | 1/1              |
| L0      | rules       | 0.0905 |                 0.9  |    1    |          1    |           3 |           0 |                0 | 3/3              |
| L1      | llm         | 0.1146 |                 0.8  |    0.75 |          1    |           3 |           0 |                0 | 2/2              |
| L1      | rules       | 0.1146 |                 0.85 |    1    |          1    |           3 |           0 |                0 | 3/3              |
| L2      | llm         | 0.1132 |                 0.7  |    0.25 |          1    |           3 |           0 |                0 | 0/0              |
| L2      | rules       | 0.1132 |                 0.85 |    1    |          1    |           3 |           0 |                0 | 3/3              |
| L3      | llm         | 0.5686 |                 0.5  |    0.25 |          0.75 |           3 |           0 |                0 | 0/0              |
| L3      | rules       | 0.5686 |                 0.5  |    0.25 |          0.75 |           4 |           0 |                0 | 0/0              |

## WER no predice si el registro sirve

```json
{
 "wer_alto_registro_perfecto": {
  "run": "real__pedido__L2__small__cpu__int8__glosario",
  "extractor": "rules",
  "clip": "L01",
  "wer": 0.1638,
  "incorrectos": []
 },
 "wer_bajo_registro_roto": {
  "run": "real__entrevista__L0__small__cpu__int8__glosario",
  "extractor": "rules",
  "clip": "E02",
  "wer": 0.0286,
  "incorrectos": [
   "anios_experiencia",
   "tecnologias"
  ]
 }
}
```

## Eje de acentos (voces sintéticas, NO hablantes humanos)

| locale   | tarea      |    WER | IC95           |    CER |
|:---------|:-----------|-------:|:---------------|-------:|
| es-AR    | entrevista | 0.0137 | [0.009, 0.019] | 0.0046 |
| es-AR    | pedido     | 0.0108 | [0.000, 0.026] | 0.0018 |
| es-CO    | entrevista | 0.0694 | [0.023, 0.139] | 0.0468 |
| es-CO    | pedido     | 0.047  | [0.037, 0.059] | 0.0114 |
| es-ES    | entrevista | 0.0371 | [0.003, 0.097] | 0.0317 |
| es-ES    | pedido     | 0.012  | [0.004, 0.019] | 0.003  |
| es-MX    | entrevista | 0.0056 | [0.002, 0.009] | 0.0027 |
| es-MX    | pedido     | 0.0072 | [0.001, 0.013] | 0.0018 |
| es-PE    | entrevista | 0.0056 | [0.003, 0.009] | 0.0029 |
| es-PE    | pedido     | 0.006  | [0.001, 0.010] | 0.0014 |

## Gate de regresión: PASA

| chequeo                            |   valor | ok   |
|:-----------------------------------|--------:|:-----|
| WER entrevista <= 0.2              |  0.0691 | True |
| exactitud reglas entrevista >= 0.6 |  0.75   | True |
| WER pedido <= 0.2                  |  0.0905 | True |
| exactitud reglas pedido >= 0.5     |  0.9    | True |
| recall del validador >= 0.66       |  1      | True |
