"""Cliente OpenAI para extraer operaciones de texto libre.

La IA solo extrae (RN-09): copia nombres tal cual y nunca inventa
identificadores; la resolucion ocurre despues contra la base de datos.

TODO(fase-8): registrar cada llamada en ia_llamadas y aplicar el
presupuesto diario (ai_daily_budget_mxn).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from openai import APIConnectionError, APITimeoutError, AsyncOpenAI, RateLimitError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from backend.config import get_settings
from backend.infrastructure.ai.esquemas import ExtraccionIA

_RUTA_PROMPT = Path(__file__).resolve().parents[3] / "prompts" / "extraer_operacion.md"


def extractor_disponible() -> bool:
    settings = get_settings()
    return settings.ai_enabled and bool(settings.openai_api_key)


def construir_prompt(
    fecha_actual: date,
    contrapartes: list[str],
    productos: list[str],
) -> str:
    plantilla = _RUTA_PROMPT.read_text(encoding="utf-8")
    return (
        plantilla.replace("{fecha_actual}", fecha_actual.isoformat())
        .replace("{lista_contrapartes}", ", ".join(contrapartes) or "(ninguna)")
        .replace("{lista_productos}", ", ".join(productos) or "(ninguno)")
    )


class ExtractorOperaciones:
    """Una instancia por proceso; el cliente httpx interno se reutiliza."""

    def __init__(self) -> None:
        settings = get_settings()
        self._cliente = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)
        self._modelo = settings.openai_model_extraccion

    @retry(
        retry=retry_if_exception_type((APIConnectionError, APITimeoutError, RateLimitError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, max=8),
        reraise=True,
    )
    async def extraer(
        self,
        texto: str,
        *,
        fecha_actual: date,
        contrapartes: list[str],
        productos: list[str],
    ) -> ExtraccionIA:
        respuesta = await self._cliente.beta.chat.completions.parse(
            model=self._modelo,
            messages=[
                {
                    "role": "system",
                    "content": construir_prompt(fecha_actual, contrapartes, productos),
                },
                {"role": "user", "content": texto},
            ],
            response_format=ExtraccionIA,
        )
        extraccion = respuesta.choices[0].message.parsed
        if extraccion is None:
            return ExtraccionIA()
        return extraccion


_instancia: ExtractorOperaciones | None = None


def extractor() -> ExtractorOperaciones:
    global _instancia
    if _instancia is None:
        _instancia = ExtractorOperaciones()
    return _instancia
