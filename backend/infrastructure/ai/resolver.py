"""Resolucion de entidades (RN-09).

La IA extrae el texto tal cual; la resolucion de a quien se refiere ocurre
AQUI, contra la base de datos, con similitud trigram. Nunca se le pide al
modelo que invente identificadores.
"""

from __future__ import annotations

import math
import unicodedata
import uuid
from dataclasses import dataclass
from difflib import SequenceMatcher

UMBRAL_AUTOMATICO = 0.75
UMBRAL_SUGERENCIA = 0.45


def normalizar(texto: str) -> str:
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn"
    )
    return " ".join(sin_acentos.lower().split())


def _cobertura(a: str, b: str) -> float:
    """Que tanto se contiene un nombre en el otro, a nivel de palabras.

    "Los Pinos" contra "Rancho Los Pinos" debe puntuar alto; "Los" solo,
    contra cualquier nombre que empiece con "Los", debe quedarse bajo.
    Emula el comportamiento de pg_trgm word_similarity.
    """
    tokens_a = set(normalizar(a).split())
    tokens_b = set(normalizar(b).split())
    if not tokens_a or not tokens_b:
        return 0.0
    comunes = tokens_a & tokens_b
    if not comunes:
        return 0.0
    precision = len(comunes) / len(tokens_a)
    cobertura = len(comunes) / len(tokens_b)
    return precision * math.sqrt(cobertura)


def similitud(a: str, b: str) -> float:
    """Puntaje 0-1. En produccion lo calcula PostgreSQL con pg_trgm;
    esta version pura permite probar la logica sin base de datos."""
    ratio = SequenceMatcher(None, normalizar(a), normalizar(b)).ratio()
    return max(ratio, _cobertura(a, b))


@dataclass(frozen=True, slots=True)
class Candidato:
    id: uuid.UUID
    nombre: str
    puntaje: float


@dataclass(frozen=True, slots=True)
class Resolucion:
    """Resultado de intentar identificar una contraparte."""

    texto_original: str
    elegido: Candidato | None
    candidatos: list[Candidato]

    @property
    def es_automatica(self) -> bool:
        return self.elegido is not None

    @property
    def requiere_pregunta(self) -> bool:
        return self.elegido is None and bool(self.candidatos)

    @property
    def es_nueva(self) -> bool:
        return self.elegido is None and not self.candidatos


def resolver(
    texto: str,
    catalogo: list[tuple[uuid.UUID, str]],
    *,
    alias: list[tuple[uuid.UUID, str]] | None = None,
) -> Resolucion:
    """Empareja `texto` contra nombres y alias conocidos.

    Se resuelve automaticamente solo si hay UN candidato por encima del
    umbral. Si hay varios, el bot pregunta con botones.
    """
    entradas = list(catalogo) + list(alias or [])
    puntajes: dict[uuid.UUID, Candidato] = {}
    for entidad_id, nombre in entradas:
        puntaje = similitud(texto, nombre)
        previo = puntajes.get(entidad_id)
        if previo is None or puntaje > previo.puntaje:
            puntajes[entidad_id] = Candidato(entidad_id, nombre, puntaje)

    ordenados = sorted(puntajes.values(), key=lambda c: c.puntaje, reverse=True)
    sobre_umbral = [c for c in ordenados if c.puntaje >= UMBRAL_AUTOMATICO]

    if len(sobre_umbral) == 1:
        return Resolucion(texto, sobre_umbral[0], ordenados[:5])
    if len(sobre_umbral) > 1 and sobre_umbral[0].puntaje - sobre_umbral[1].puntaje >= 0.15:
        return Resolucion(texto, sobre_umbral[0], ordenados[:5])

    sugerencias = [c for c in ordenados if c.puntaje >= UMBRAL_SUGERENCIA][:5]
    return Resolucion(texto, None, sugerencias)
