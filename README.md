<div align="center">

# INSTITUTO TECNOLÓGICO NACIONAL DE MÉXICO
## Campus Pachuca

### Inteligencia Artificial aplicada a las TIC

### 2.2 Agente investigador

**Docente:**
Ing. Víctor Manuel Pinedo Fernández

**Alumna:**
Manzano Luna Claudia Melissa · 23200168

</div>

---

## Descripción

Agente investigador con búsqueda web que genera reportes estructurados a partir
de varias fuentes. Está construido con Flask y la API de OpenAI (Responses API
con la herramienta `web_search`), y muestra el progreso de la investigación y
las fuentes consultadas en tiempo real.

El agente responde dos tipos de preguntas:

- **Tecnologías de la información y comunicaciones (TIC):** genera un reporte
  de investigación con plan, hallazgos, tabla comparativa, coincidencias y
  diferencias entre fuentes, tendencias y conclusiones.
- **Consultas sobre el Instituto Tecnológico de Pachuca:** carga de materias,
  convocatorias, trámites, servicio social, residencias, titulación, etc.
  Prioriza fuentes oficiales (`itpachuca.edu.mx`, `tecnm.mx`) e indica dónde
  confirmar la información.

Cualquier pregunta fuera de estas áreas se rechaza con un mensaje.

## Funcionalidades

- Respuesta en streaming con el estado de cada etapa de la investigación.
- Fuentes consultadas en vivo y listado final de referencias.
- Reporte visual con hallazgos en tarjetas, plan visual y tabla comparativa.
- Descarga del reporte en PDF (tamaño A4, con fuentes y números de página).
- Restricción de la API a la propia página y a los orígenes autorizados
  en `ALLOWED_ORIGIN`.

## Ejecutar en local

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Crea un archivo `config.py` (no se sube al repositorio) con tu API key:

```python
OPENAI_API_KEY = "tu-api-key"
OPENAI_MODEL = "gpt-5"
```

La aplicación queda disponible en `http://127.0.0.1:5000`.

## Despliegue en Vercel

1. Importa el repositorio en Vercel con el **Framework Preset: Flask**.
2. En **Settings → Environment Variables** agrega:

   | Variable | Descripción |
   |---|---|
   | `OPENAI_API_KEY` | API key de OpenAI (obligatoria). |
   | `OPENAI_MODEL` | Modelo a usar (opcional, por defecto `gpt-5`). |
   | `ALLOWED_ORIGIN` | Orígenes externos autorizados a usar la API, separados por comas (opcional, por ejemplo `https://usuario.github.io`). |

3. Después de cambiar una variable, vuelve a desplegar (**Redeploy**).

## Estructura

```
app.py                 Servidor Flask, instrucciones del agente y streaming
templates/index.html   Interfaz
assets/js/app.js       Lógica del cliente, renderizado del reporte y PDF
assets/css/styles.css  Estilos
requirements.txt       Dependencias de Python
```

## Historial de versiones

**V4**

- Se corrigió el parser de hallazgos principales: cada hallazgo separa
  nombre, descripción, fuente y URL, y se muestra como tarjeta independiente.
- Las URLs largas se muestran como nombre de fuente, dominio y botón
  "Abrir fuente".

**V5 · Corrección de alineación**

- Se eliminó el scroll horizontal general de la página.
- Todas las secciones del reporte usan el mismo ancho y se adaptan al tamaño
  de pantalla.
- La tabla comparativa hace scroll únicamente dentro de su tarjeta.
- Textos y URLs largas ya no desbordan su contenedor.

**V6 · Despliegue y nuevas funciones**

- Configuración por variables de entorno para Vercel.
- Restricción temática a TIC y consultas del Instituto Tecnológico de Pachuca.
- Validación de origen con `ALLOWED_ORIGIN`.
- Descarga del reporte en PDF.
