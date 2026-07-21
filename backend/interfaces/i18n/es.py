"""Todos los textos de cara al usuario. Nunca hardcodear strings en handlers."""

from __future__ import annotations

BIENVENIDA = (
    "Listo. Mandame por voz, texto, foto o PDF lo que compraste, vendiste, "
    "pagaste o las cajas que te regresaron. Yo lo registro.\n\n"
    "Usa /ayuda para ver los comandos."
)

NO_AUTORIZADO = "Este bot es privado."

PROCESANDO = "Procesando..."

NO_ENTENDI = (
    "No alcance a entender la operacion. Puedes decirmelo de otra forma? "
    'Por ejemplo: "compramos 220 cajas de frambuesa a Los Pinos a 385".'
)

FALTAN_DATOS = "Me falta: {campos}"

GUARDADO = "Guardado. Folio {folio}."
CANCELADO = "Cancelado. No guarde nada."
EXPIRADO = "Ese borrador ya expiro. Mandame la operacion de nuevo."

ALERTA_SALDO_NEGATIVO = (
    "Ojo: el saldo de {nombre} quedaria en {saldo} cajas. Fue de un embarque anterior?"
)
ALERTA_SIN_INVENTARIO = (
    "Ojo: faltan {cajas} cajas de inventario para cubrir esta venta. "
    "La registro y la marco para revisar?"
)
DUPLICADO = "Esta operacion ya esta registrada (folio {folio})."

IA_NO_DISPONIBLE = (
    "El motor de extraccion no esta configurado (falta OPENAI_API_KEY). "
    "Pide al administrador que lo active."
)
ERROR_INTERNO = "Algo fallo de mi lado. Intenta de nuevo en un momento."
MEDIO_NO_DISPONIBLE = (
    "Todavia no puedo procesar {medio}. Mandame la operacion por texto mientras tanto."
)
MARCADA_REVISION = "La marque para revisar."

ELIGE_CAMPO = "Que campo quieres corregir?"
MANDA_VALOR = "Mandame el nuevo valor para: {campo}"
EDICION_LISTA = "Listo, actualice la tarjeta."
CONTRAPARTE_NUEVA_PENDIENTE = (
    "El alta de contrapartes nuevas desde el chat todavia no esta lista. "
    "Registrala primero y vuelve a mandar la operacion."
)

SIN_PENDIENTES = "No hay borradores pendientes."
DAME_NOMBRE = "Dime el nombre. Ejemplo: {ejemplo}"
NO_CONTRAPARTE = "No encontre a {nombre}."
SALDO_DINERO = "{nombre}\nFacturado: ${facturado}\nPagado:    ${pagado}\nPendiente: ${pendiente}"

BOTON_GUARDAR = "Guardar"
BOTON_EDITAR = "Editar"
BOTON_CANCELAR = "Cancelar"
BOTON_SI = "Si, registrar"
BOTON_CORREGIR = "Corregir"
BOTON_ES_NUEVO = "Es nuevo"
BOTON_VOLVER = "Volver"

AYUDA = """Comandos disponibles:

/saldo [nombre]   cajas pendientes
/cajas            tablero de cajas por devolver
/compras [hoy|semana|mes]
/ventas [periodo]
/utilidad [periodo]
/debo [nombre]    cuentas por pagar
/medeben [nombre] cuentas por cobrar
/contraparte <nombre>
/pendientes       borradores sin confirmar
/corregir         ultimas operaciones
/anular <folio>
/reporte <periodo>
"""
