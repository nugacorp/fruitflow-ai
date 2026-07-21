"""RN-09: los apodos se resuelven contra la base, no con la IA."""

from backend.domain.common.tipos import nuevo_id
from backend.infrastructure.ai.resolver import normalizar, resolver, similitud

EXPO = nuevo_id()
PINOS = nuevo_id()
REYES = nuevo_id()

CATALOGO = [
    (EXPO, "Exportadora del Norte"),
    (PINOS, "Rancho Los Pinos"),
    (REYES, "Los Reyes Berries"),
]
ALIAS = [(EXPO, "Memo"), (PINOS, "Chuy")]


def test_normalizacion_quita_acentos_y_mayusculas():
    assert normalizar("  Rancho  El PARAÍSO ") == "rancho el paraiso"


def test_alias_exacto_resuelve_automaticamente():
    r = resolver("Memo", CATALOGO, alias=ALIAS)
    assert r.es_automatica
    assert r.elegido.id == EXPO


def test_nombre_parcial_resuelve():
    r = resolver("Los Pinos", CATALOGO, alias=ALIAS)
    assert r.es_automatica
    assert r.elegido.id == PINOS


def test_texto_ambiguo_pide_confirmacion():
    r = resolver("Los", CATALOGO, alias=ALIAS)
    assert not r.es_automatica


def test_contraparte_desconocida_se_marca_como_nueva():
    r = resolver("Comercializadora Zapopan XYZ", CATALOGO, alias=ALIAS)
    assert r.es_nueva or r.requiere_pregunta
    assert r.elegido is None


def test_similitud_es_simetrica_y_acotada():
    assert 0.0 <= similitud("Memo", "Memito") <= 1.0
    assert similitud("abc", "abc") == 1.0
