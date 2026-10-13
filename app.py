import json
import os

from flask import Flask, Response, render_template, request, stream_with_context
from openai import OpenAI

# En Vercel las credenciales llegan como variables de entorno;
# en local se usa config.py (ignorado por git) como respaldo.
try:
    import config
except ImportError:
    config = None

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or getattr(config, "OPENAI_API_KEY", None)
OPENAI_MODEL = os.environ.get("OPENAI_MODEL") or getattr(config, "OPENAI_MODEL", "gpt-5")

# Orígenes externos autorizados a llamar a la API, separados por comas
# (ej. "https://usuario.github.io"). La propia página siempre está permitida.
ALLOWED_ORIGINS = {
    origen.strip().rstrip("/")
    for origen in (
        os.environ.get("ALLOWED_ORIGIN")
        or getattr(config, "ALLOWED_ORIGIN", "")
    ).split(",")
    if origen.strip()
}


app = Flask(
    __name__,
    static_folder="assets",
    static_url_path="/assets"
)

client = OpenAI(api_key=OPENAI_API_KEY)


def origen_permitido(origen):
    if not origen:
        return True

    mismo_sitio = origen.split("://", 1)[-1] == request.host

    return mismo_sitio or origen.rstrip("/") in ALLOWED_ORIGINS


@app.before_request
def validar_origen():
    if not request.path.startswith("/api/"):
        return None

    if not origen_permitido(request.headers.get("Origin")):
        return Response(
            sse(
                "error",
                {
                    "mensaje": "Origen no autorizado para usar esta API."
                }
            ),
            mimetype="text/event-stream",
            status=403
        )

    if request.method == "OPTIONS":
        return Response(status=204)

    return None


@app.after_request
def agregar_cors(respuesta):
    origen = request.headers.get("Origin")

    if origen and origen.rstrip("/") in ALLOWED_ORIGINS:
        respuesta.headers["Access-Control-Allow-Origin"] = origen
        respuesta.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        respuesta.headers["Access-Control-Allow-Headers"] = "Content-Type"
        respuesta.headers["Vary"] = "Origin"

    return respuesta


@app.route("/")
def inicio():
    return render_template("index.html")


def sse(tipo, datos):
    return (
        f"event: {tipo}\n"
        f"data: {json.dumps(datos, ensure_ascii=False)}\n\n"
    )


def obtener_valor(objeto, atributo, valor_default=None):
    if objeto is None:
        return valor_default

    if isinstance(objeto, dict):
        return objeto.get(atributo, valor_default)

    return getattr(objeto, atributo, valor_default)


def emitir_fuentes_desde_accion(accion, urls_emitidas):
    if accion is None:
        return []

    nuevas_fuentes = []

    tipo_accion = obtener_valor(accion, "type", "")

    url_directa = obtener_valor(accion, "url")

    if url_directa and url_directa not in urls_emitidas:
        urls_emitidas.add(url_directa)

        nuevas_fuentes.append({
            "titulo": url_directa,
            "url": url_directa,
            "origen": tipo_accion or "web_search"
        })

    sources = obtener_valor(accion, "sources", []) or []

    for source in sources:
        url = obtener_valor(source, "url")

        if url and url not in urls_emitidas:
            urls_emitidas.add(url)

            nuevas_fuentes.append({
                "titulo": url,
                "url": url,
                "origen": "search"
            })

    return nuevas_fuentes


@app.route("/api/investigar", methods=["POST", "OPTIONS"])
def investigar():
    datos = request.get_json(silent=True) or {}
    pregunta = datos.get("pregunta", "").strip()

    if not pregunta:
        return Response(
            sse(
                "error",
                {
                    "mensaje": "Debes escribir una pregunta de investigación."
                }
            ),
            mimetype="text/event-stream",
            status=400
        )

    instrucciones = """
Eres un agente investigador especializado en tecnologías de información
y comunicaciones, y también asesoras a estudiantes del Instituto
Tecnológico de Pachuca (TecNM campus Pachuca) en temas de la institución.

ALCANCE TEMÁTICO (REGLA PRIORITARIA):
Solo puedes responder preguntas de estas dos áreas:

A) Tecnologías de la información y comunicaciones (TIC). Esto incluye,
entre otros: desarrollo de software, programación, redes y
telecomunicaciones, ciberseguridad, bases de datos, inteligencia
artificial, computación en la nube, infraestructura y hardware, sistemas
operativos, Internet, transformación digital y gestión de proyectos o
servicios de TI.

B) Consultoría sobre el Instituto Tecnológico de Pachuca. Esto incluye,
entre otros: carga de materias y reinscripciones, convocatorias (becas,
admisión, movilidad, titulación), calendario escolar, trámites escolares,
servicio social, residencias profesionales, créditos complementarios,
titulación, planes de estudio, carreras, reglamentos y lineamientos del
TecNM, y departamentos o servicios del instituto.

Antes de hacer cualquier otra cosa, evalúa a qué área pertenece la
pregunta. Si la pregunta NO pertenece a ninguna de las dos áreas:
- No realices búsquedas web.
- No generes ningún reporte ni sigas ningún formato de salida.
- No respondas parcialmente ni ofrezcas información sobre el tema.
- Responde únicamente con el siguiente mensaje, sin agregar nada más:

# Petición fuera del área de TIC

Lo siento, no puedo responder esta petición. Soy un agente investigador
especializado únicamente en temas de tecnologías de la información y
comunicaciones (TIC) y en consultas sobre el Instituto Tecnológico de
Pachuca. Por favor, realiza una pregunta relacionada con estas áreas.

Si la pregunta pertenece al área B (Instituto Tecnológico de Pachuca),
NO uses el formato de reporte de investigación. Sigue estas reglas:
- Busca primero en fuentes oficiales: el sitio del Instituto Tecnológico
  de Pachuca (itpachuca.edu.mx), el sitio del TecNM (tecnm.mx) y sus
  redes sociales oficiales.
- No inventes fechas, requisitos, costos ni procedimientos. Si no
  encuentras la información oficial o puede estar desactualizada, dilo
  claramente.
- Indica siempre el departamento al que el estudiante debe acudir para
  confirmar la información (por ejemplo: Servicios Escolares, División de
  Estudios Profesionales, Gestión Tecnológica y Vinculación, o su
  coordinación de carrera).
- Responde en Markdown con esta estructura:

# [Título breve de la consulta]

## Respuesta
[Respuesta directa y clara a la pregunta, en 1 a 3 párrafos.]

## Pasos o requisitos
- [Paso o requisito 1]
- [Paso o requisito 2]
(Omite esta sección si no aplica.)

## Fechas importantes
[Fechas encontradas en fuentes oficiales, o indica que no se encontraron.]
(Omite esta sección si no aplica.)

## Dónde confirmar
[Departamento, medio de contacto o página oficial donde confirmar.]

Si la pregunta pertenece al área A (TIC), continúa con el proceso
descrito a continuación.

Debes investigar la pregunta del usuario utilizando búsqueda web
y varias fuentes confiables. El tono debe ser claro, profesional y
académico, pensado para estudiantes universitarios.

Proceso que debes seguir:
1. Analiza la pregunta.
2. Define un plan breve de investigación.
3. Realiza búsquedas web.
4. Consulta varias fuentes.
5. Selecciona la información más relevante.
6. Compara la información obtenida.
7. Identifica coincidencias, diferencias y tendencias.
8. Sintetiza la evidencia.
9. Genera un reporte bien estructurado.

REGLAS IMPORTANTES:
- Escribe TODO en español.
- No inventes datos ni fuentes.
- Utiliza varias fuentes cuando sea posible.
- Prioriza fuentes oficiales, organismos, documentación técnica,
  universidades o medios especializados confiables.
- No agregues una sección manual de URLs al final.
- Las URLs se mostrarán por separado en la interfaz.

FORMATO OBLIGATORIO DE SALIDA:
Debes responder en Markdown usando exactamente esta estructura:

# [Título breve del reporte]

## 1. Pregunta de investigación
[Reformula claramente la pregunta del usuario en 1 párrafo.]

## 2. Plan de investigación
- [Paso 1 del plan]
- [Paso 2 del plan]
- [Paso 3 del plan]
- [Paso 4 del plan]
- [Paso 5 del plan]

## 3. Hallazgos principales

Para cada hallazgo utiliza EXACTAMENTE este formato y coloca cada campo
en una línea independiente:

### Hallazgo 1
**Nombre:** [Nombre breve y claro del hallazgo]
**Descripción:** [Explicación del hallazgo. No incluyas aquí la fuente ni la URL.]
**Fuente:** [Nombre del sitio, institución, empresa u organismo]
**URL:** [URL completa de la fuente principal]

### Hallazgo 2
**Nombre:** [Nombre breve y claro del hallazgo]
**Descripción:** [Explicación del hallazgo. No incluyas aquí la fuente ni la URL.]
**Fuente:** [Nombre del sitio, institución, empresa u organismo]
**URL:** [URL completa de la fuente principal]

### Hallazgo 3
**Nombre:** [Nombre breve y claro del hallazgo]
**Descripción:** [Explicación del hallazgo. No incluyas aquí la fuente ni la URL.]
**Fuente:** [Nombre del sitio, institución, empresa u organismo]
**URL:** [URL completa de la fuente principal]

Incluye más hallazgos si es necesario.

IMPORTANTE PARA HALLAZGOS:
- El nombre debe ser corto: máximo una línea.
- La descripción debe contener solo la explicación.
- La fuente debe contener solo el nombre de la fuente.
- La URL debe contener solo la dirección web.
- No combines Nombre, Descripción, Fuente y URL en una misma línea.

## 4. Comparación de información
Presenta una tabla Markdown con estas columnas exactas:
| Elemento | Descripción | Ventajas | Limitaciones | Escenarios recomendados |

Debes incluir al menos 3 filas cuando la pregunta lo permita.

## 5. Coincidencias y diferencias entre fuentes
### Coincidencias
- [Coincidencia 1]
- [Coincidencia 2]

### Diferencias
- [Diferencia 1]
- [Diferencia 2]

## 6. Tendencias identificadas
- [Tendencia 1]
- [Tendencia 2]
- [Tendencia 3]

## 7. Conclusiones
[Conclusión final en 1 o 2 párrafos.]
"""

    @stream_with_context
    def generar():
        urls_emitidas = set()
        reporte_acumulado = []

        try:
            yield sse(
                "estado",
                {
                    "etapa": "analizando",
                    "mensaje": "Analizando la pregunta de investigación..."
                }
            )

            stream = client.responses.create(
                model=OPENAI_MODEL,
                tools=[
                    {
                        "type": "web_search",
                        "search_context_size": "medium"
                    }
                ],
                input=[
                    {
                        "role": "system",
                        "content": instrucciones
                    },
                    {
                        "role": "user",
                        "content": pregunta
                    }
                ],
                stream=True
            )

            for event in stream:
                tipo = obtener_valor(event, "type", "")

                if tipo == "response.web_search_call.in_progress":
                    yield sse(
                        "estado",
                        {
                            "etapa": "busqueda",
                            "mensaje": "Iniciando una búsqueda en Internet..."
                        }
                    )

                elif tipo == "response.web_search_call.searching":
                    yield sse(
                        "estado",
                        {
                            "etapa": "busqueda",
                            "mensaje": "Buscando, contrastando y consultando fuentes..."
                        }
                    )

                elif tipo == "response.web_search_call.completed":
                    yield sse(
                        "estado",
                        {
                            "etapa": "revision",
                            "mensaje": "Búsqueda completada. Revisando la información encontrada..."
                        }
                    )

                elif tipo == "response.output_item.done":
                    item = obtener_valor(event, "item")

                    if obtener_valor(item, "type") == "web_search_call":
                        accion = obtener_valor(item, "action")

                        for fuente in emitir_fuentes_desde_accion(
                            accion,
                            urls_emitidas
                        ):
                            yield sse("fuente", fuente)

                elif tipo == "response.output_text.annotation.added":
                    anotacion = obtener_valor(event, "annotation")

                    if obtener_valor(anotacion, "type") == "url_citation":
                        url = obtener_valor(anotacion, "url")
                        titulo = obtener_valor(
                            anotacion,
                            "title",
                            url or "Fuente consultada"
                        )

                        if url and url not in urls_emitidas:
                            urls_emitidas.add(url)

                            yield sse(
                                "fuente",
                                {
                                    "titulo": titulo,
                                    "url": url,
                                    "origen": "cita"
                                }
                            )

                elif tipo == "response.output_text.delta":
                    delta = obtener_valor(event, "delta", "")

                    if delta:
                        reporte_acumulado.append(delta)

                        yield sse(
                            "texto",
                            {
                                "delta": delta
                            }
                        )

                elif tipo == "response.output_text.done":
                    yield sse(
                        "estado",
                        {
                            "etapa": "finalizando",
                            "mensaje": "Sintetizando y organizando el reporte final..."
                        }
                    )

                elif tipo == "response.completed":
                    yield sse(
                        "completado",
                        {
                            "mensaje": "Investigación completada.",
                            "reporte": "".join(reporte_acumulado),
                            "total_fuentes": len(urls_emitidas)
                        }
                    )

                elif tipo == "error":
                    mensaje = obtener_valor(
                        event,
                        "message",
                        "OpenAI devolvió un error durante la investigación."
                    )

                    yield sse(
                        "error",
                        {
                            "mensaje": mensaje
                        }
                    )

        except Exception as error:
            print("ERROR:", error)

            yield sse(
                "error",
                {
                    "mensaje": "Ocurrió un error al realizar la investigación.",
                    "detalle": str(error)
                }
            )

    return Response(
        generar(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no"
        }
    )


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True,
        threaded=True
    )
