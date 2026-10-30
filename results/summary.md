# Resultados (corpus principal: `tts-es-PE`)

Generado: 2026-10-30T16:05:12+00:00. Regenerar con `python pipeline.py evaluate`.

## Verdad de campo: distribución de cada campo

| tarea      | campo               | distribución                                                                                                                                                                                                                                                                                                             |
|:-----------|:--------------------|:-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| entrevista | anios_experiencia   | 4 ×1, 5.5 ×1, 8 ×1, 2 ×1, 3 ×1                                                                                                                                                                                                                                                                                           |
| entrevista | ultimo_puesto       | analista de datos ×1, desarrollador backend ×1, jefe de proyectos ×1, ingeniera de datos junior ×1, desarrollador frontend ×1                                                                                                                                                                                            |
| entrevista | tecnologias         | Python ×2, SQL ×1, Power BI ×1, Java ×1, Spring Boot ×1, PostgreSQL ×1, Docker ×1, Kubernetes ×1, Jira ×1, Excel ×1, SAP ×1, Airflow ×1, Spark ×1, AWS ×1, React ×1, TypeScript ×1, Node.js ×1, Figma ×1                                                                                                                 |
| entrevista | pretension_salarial | 6500 PEN ×1, 3000 USD ×1, 9000 PEN ×1, 4200 PEN ×1, 7250 PEN ×1                                                                                                                                                                                                                                                          |
| entrevista | disponibilidad      | 2_semanas ×1, 1_mes ×2, inmediata ×1, 2_meses ×1                                                                                                                                                                                                                                                                         |
| entrevista | nivel_ingles        | intermedio ×2, avanzado ×2, basico ×1                                                                                                                                                                                                                                                                                    |
| pedido     | items               | 1× pollo a la brasa entero ×2, 1× papas fritas familiar ×1, 1× chicha morada jarra ×2, 2× pollo a la brasa cuarto ×1, 2× chicha morada vaso ×1, 1× ensalada ×2, 2× anticuchos ×1, 1× gaseosa grande ×1, 2× pollo a la brasa medio ×1, 2× papas fritas personal ×1, 1× pollo a la brasa cuarto ×1, 1× gaseosa personal ×1 |
| pedido     | promocion           | None ×2, martes brasero ×1, combo familiar ×1, cupon de bienvenida ×1                                                                                                                                                                                                                                                    |
| pedido     | direccion_entrega   | avenida los proceres 845 santiago de surco ×1, jiron huascar 1450 departamento 302 jesus maria ×1, calle las begonias 2280 san isidro ×1, avenida brasil 3021 pueblo libre ×1, calle tarata 160 miraflores ×1                                                                                                            |
| pedido     | metodo_pago         | yape ×2, tarjeta ×1, efectivo ×1, plin ×1                                                                                                                                                                                                                                                                                |
| pedido     | total_dicho         | 103 ×1, 62.5 ×1, 127 ×1, 91 ×1, 35 ×1                                                                                                                                                                                                                                                                                    |
| pedido     | trampas             | correccion ×4, total_erroneo ×3                                                                                                                                                                                                                                                                                          |

## Capa 1 — Transcripción (L0)

| corpus    | tarea      | modelo   | dispositivo (runtime)   | precisión (runtime)   | glosario   |   VAD |    WER | IC95 WER       |    CER |   s/min audio | VRAM pico MB   | GPU   |
|:----------|:-----------|:---------|:------------------------|:----------------------|:-----------|------:|-------:|:---------------|-------:|--------------:|:---------------|:------|
| tts-es-PE | entrevista | base     | cpu                     | int8_float32          | True       |  0.25 | 0.1089 | [0.035, 0.200] | 0.084  |          9.85 |                |       |
| tts-es-PE | entrevista | small    | cpu                     | float32               | True       |  0.25 | 0.0363 | [0.003, 0.104] | 0.0314 |         37.45 |                |       |
| tts-es-PE | entrevista | small    | cpu                     | int8_float32          | True       |  0.25 | 0.0056 | [0.003, 0.009] | 0.0029 |         25.94 |                |       |
| tts-es-PE | entrevista | small    | cpu                     | int8_float32          | True       |  0.5  | 0.0056 | [0.003, 0.009] | 0.0029 |         17.46 |                |       |
| tts-es-PE | entrevista | small    | cpu                     | int8_float32          | False      |  0.25 | 0.0113 | [0.006, 0.018] | 0.0049 |         23.51 |                |       |
| tts-es-PE | pedido     | small    | cpu                     | int8_float32          | True       |  0.25 | 0.006  | [0.001, 0.010] | 0.0014 |         25.45 |                |       |
| tts-es-PE | pedido     | small    | cpu                     | int8_float32          | True       |  0.5  | 0.006  | [0.001, 0.010] | 0.0014 |         17.23 |                |       |
| tts-es-PE | pedido     | small    | cpu                     | int8_float32          | False      |  0.25 | 0.0181 | [0.008, 0.025] | 0.0041 |         30.76 |                |       |

## Capa 2 — Registro (exactitud por campo, L0)

| tarea      | extractor   |   exactitud | IC95           |   anios_experiencia |   ultimo_puesto |   tecnologias |   pretension_salarial |   disponibilidad |   nivel_ingles | verificados y correctos   | sin_verificar y correctos   |   items |   promocion |   direccion_entrega |   metodo_pago |   total_dicho |
|:-----------|:------------|------------:|:---------------|--------------------:|----------------:|--------------:|----------------------:|-----------------:|---------------:|:--------------------------|:----------------------------|--------:|------------:|--------------------:|--------------:|--------------:|
| entrevista | llm         |      0.7667 | [0.632, 0.900] |                 0.8 |               1 |           0   |                     1 |                1 |            0.8 | 22/27                     | 1/3                         |   nan   |         nan |               nan   |           nan |           nan |
| entrevista | rules       |      0.8    | [0.667, 0.933] |                 0.6 |               1 |           0.2 |                     1 |                1 |            1   | 24/30                     | 0/0                         |   nan   |         nan |               nan   |           nan |           nan |
| pedido     | llm         |      0.88   | [0.759, 1.000] |               nan   |             nan |         nan   |                   nan |              nan |          nan   | 20/21                     | 0/2                         |     0.4 |           1 |                 1   |             1 |             1 |
| pedido     | rules       |      0.96   | [0.880, 1.000] |               nan   |             nan |         nan   |                   nan |              nan |          nan   | 22/23                     | 0/0                         |     1   |           1 |                 0.8 |             1 |             1 |

### F1 macro (categóricos) y error absoluto medio (numéricos)

| tarea      | extractor   |   F1 macro disponibilidad |   F1 macro nivel_ingles |   MAE anios_experiencia |   MAE pretension_salarial |   F1 macro promocion |   F1 macro metodo_pago |   MAE total_dicho |
|:-----------|:------------|--------------------------:|------------------------:|------------------------:|--------------------------:|---------------------:|-----------------------:|------------------:|
| entrevista | llm         |                         1 |                  0.8222 |                     0.2 |                         0 |                  nan |                    nan |               nan |
| entrevista | rules       |                         1 |                  1      |                     0.8 |                         0 |                  nan |                    nan |               nan |
| pedido     | llm         |                       nan |                nan      |                   nan   |                       nan |                    1 |                      1 |                 0 |
| pedido     | rules       |                       nan |                nan      |                   nan   |                       nan |                    1 |                      1 |                 0 |

## Glosario (hotwords): mejora de WER, IC95 bootstrap pareado por clip

| cambia   | de    | a    | tarea      | nivel   | modelo   |   clips |   wer_antes |   wer_despues |   mejora_wer_media | mejora_wer_ci   |   recall_glosario_antes |   recall_glosario_despues |
|:---------|:------|:-----|:-----------|:--------|:---------|--------:|------------:|--------------:|-------------------:|:----------------|------------------------:|--------------------------:|
| glossary | False | True | entrevista | L0      | small    |       5 |      0.0113 |        0.0056 |             0.0061 | [0.003, 0.009]  |                  0.7083 |                    0.7917 |
| glossary | False | True | pedido     | L0      | small    |       5 |      0.0181 |        0.006  |             0.0113 | [0.004, 0.018]  |                  0.7368 |                    1      |

## Umbral del VAD: mejora de WER al bajarlo de 0.5 a 0.25

| cambia        |   de |    a | tarea      | nivel   | modelo   |   clips |   wer_antes |   wer_despues |   mejora_wer_media | mejora_wer_ci   |   recall_glosario_antes |   recall_glosario_despues |
|:--------------|-----:|-----:|:-----------|:--------|:---------|--------:|------------:|--------------:|-------------------:|:----------------|------------------------:|--------------------------:|
| vad_threshold |  0.5 | 0.25 | entrevista | L0      | small    |       5 |      0.0056 |        0.0056 |             0      | [0.000, 0.000]  |                  0.7917 |                    0.7917 |
| vad_threshold |  0.5 | 0.25 | pedido     | L0      | small    |       5 |      0.006  |        0.006  |             0      | [0.000, 0.000]  |                  1      |                    1      |
| vad_threshold |  0.5 | 0.25 | pedido     | L1      | small    |       5 |      0.0096 |        0.0096 |             0      | [0.000, 0.000]  |                  1      |                    1      |
| vad_threshold |  0.5 | 0.25 | pedido     | L2      | small    |       5 |      0.6145 |        0.0133 |             0.6059 | [0.563, 0.652]  |                  0.6842 |                    1      |
| vad_threshold |  0.5 | 0.25 | pedido     | L3      | small    |       5 |      0.212  |        0.212  |             0      | [0.000, 0.000]  |                  0.8947 |                    0.8947 |

## ¿Cambia el texto con el dispositivo o la precisión?

| cambia                 |   clips |   clips_identicos |   diferencia_texto_wer |   wer_a |   wer_b | a                                                        | b                                                     |
|:-----------------------|--------:|------------------:|-----------------------:|--------:|--------:|:---------------------------------------------------------|:------------------------------------------------------|
| compute_type_requested |       5 |                 3 |                 0.0324 |  0.0363 |  0.0056 | tts-es-PE__entrevista__L0__small__cpu__float32__glosario | tts-es-PE__entrevista__L0__small__cpu__int8__glosario |

## Escalera de degradación y validador aritmético (pedidos)

| nivel   | extractor   |    WER |   exactitud registro |   items |   total_dicho |   atrapados |   escapados |   falsas alarmas | diagnóstico ok   |
|:--------|:------------|-------:|---------------------:|--------:|--------------:|------------:|------------:|-----------------:|:-----------------|
| L0      | llm         | 0.006  |                 0.88 |     0.4 |           1   |           3 |           0 |                0 | 0/0              |
| L0      | rules       | 0.006  |                 0.96 |     1   |           1   |           3 |           0 |                0 | 3/3              |
| L1      | llm         | 0.0096 |                 0.88 |     0.4 |           1   |           3 |           0 |                0 | 0/0              |
| L1      | rules       | 0.0096 |                 1    |     1   |           1   |           3 |           0 |                0 | 3/3              |
| L2      | llm         | 0.0133 |                 0.88 |     0.6 |           1   |           3 |           0 |                0 | 1/1              |
| L2      | rules       | 0.0133 |                 0.92 |     1   |           1   |           3 |           0 |                0 | 3/3              |
| L3      | llm         | 0.212  |                 0.76 |     0.6 |           0.8 |           3 |           0 |                0 | 1/1              |
| L3      | rules       | 0.212  |                 0.52 |     0.4 |           0.8 |           3 |           0 |                0 | 0/0              |

## WER no predice si el registro sirve

```json
{
 "wer_alto_registro_perfecto": {
  "run": "tts-es-PE__pedido__L3__small__cpu__int8__glosario",
  "extractor": "llm",
  "clip": "L01",
  "wer": 0.1864,
  "incorrectos": []
 },
 "wer_bajo_registro_roto": {
  "run": "tts-es-PE__entrevista__L0__small__cpu__int8__glosario",
  "extractor": "llm",
  "clip": "E03",
  "wer": 0.0,
  "incorrectos": [
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
| WER entrevista <= 0.2              |  0.0056 | True |
| exactitud reglas entrevista >= 0.6 |  0.8    | True |
| WER pedido <= 0.2                  |  0.006  | True |
| exactitud reglas pedido >= 0.5     |  0.96   | True |
| recall del validador >= 0.66       |  1      | True |
