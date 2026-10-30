"""Servidor MCP: expone el motor como herramienta para Claude Code (u otro agente).

Registro (ya incluido en .mcp.json):  claude mcp add voz-a-registro -- .venv/Scripts/python mcp_server.py
"""
from pathlib import Path

from mcp.server.mcpserver import MCPServer

import engine

server = MCPServer("voz-a-registro", instructions="Convierte un audio de entrevista o de pedido en un registro verificado.")


@server.tool()
def procesar_audio(ruta_audio: str, tarea: str = "entrevista", extractor: str = "rules") -> dict:
    """Transcribe un audio y devuelve el registro estructurado.

    Args:
        ruta_audio: ruta local del audio (wav, mp3, m4a, ogg...).
        tarea: "entrevista" (registro de candidato) o "pedido" (registro de pedido con validación aritmética).
        extractor: "rules" (expresiones regulares) o "llm" (modelo local vía Ollama).
    """
    if not Path(ruta_audio).is_file():
        return {"error": f"no existe el archivo: {ruta_audio}"}
    result = engine.process(ruta_audio, tarea, extractor)
    result.pop("segments", None)                 # las marcas de tiempo por palabra no le sirven al agente
    return result


@server.tool()
def extraer_de_texto(transcripcion: str, tarea: str = "entrevista", extractor: str = "rules") -> dict:
    """Extrae y verifica el registro a partir de una transcripción ya hecha (sin audio)."""
    return engine.extract_record(transcripcion, tarea, extractor)


if __name__ == "__main__":
    server.run()
