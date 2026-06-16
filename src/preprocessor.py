"""
Preprocessor module — Conversión a Markdown + Detección de PII.

Pipeline:
1. MarkItDown: PDF/DOCX/XLSX → Markdown limpio
2. Presidio: Detecta + pseudoanonimiza PII (emails, DNI, SSN, etc.)

El texto que entra al vector store NUNCA contiene PII en claro.
"""

import re
from typing import Tuple, List, Dict
from pathlib import Path

try:
    from markitdown import MarkItDown
    MARKITDOWN_AVAILABLE = True
except ImportError:
    MARKITDOWN_AVAILABLE = False
    print("⚠️ MarkItDown no instalado. Instalalo con: pip install markitdown")

try:
    import pymupdf
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False

try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_analyzer.nlp_engine import NlpEngineProvider
    from presidio_anonymizer import AnonymizerEngine
    PRESIDIO_AVAILABLE = True
except ImportError:
    PRESIDIO_AVAILABLE = False
    print("⚠️ Presidio no instalado. Instalalo con: pip install presidio-analyzer presidio-anonymizer")


class Preprocessor:
    """
    Preprocesa documentos: conversión a Markdown + anonimización de PII.

    Attributes:
        markdown_converter: Conversor MarkItDown (si disponible)
        analyzer: Presidio analyzer para detectar PII
        anonymizer: Presidio anonymizer para reemplazar PII
    """

    def __init__(self):
        """Inicializa el preprocessor con MarkItDown y Presidio."""
        self.markdown_converter = None
        self.analyzer = None
        self.anonymizer = None

        if MARKITDOWN_AVAILABLE:
            self.markdown_converter = MarkItDown()

        if PRESIDIO_AVAILABLE:
            # Configurar Presidio para usar el modelo español de spaCy
            # (por defecto busca en_core_web_lg que no tenemos instalado).
            nlp_config = {
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "es", "model_name": "es_core_news_lg"}],
            }
            provider = NlpEngineProvider(nlp_configuration=nlp_config)
            nlp_engine = provider.create_engine()

            self.analyzer = AnalyzerEngine(
                nlp_engine=nlp_engine,
                supported_languages=["es"],
            )
            self.anonymizer = AnonymizerEngine()

    def convert_to_markdown(self, file_path: str) -> str:
        """
        Convierte archivos (PDF, DOCX, XLSX, etc.) a Markdown.

        Args:
            file_path: Ruta del archivo

        Returns:
            str: Contenido en formato Markdown

        Raises:
            FileNotFoundError: Si el archivo no existe
            ValueError: Si el tipo de archivo no es soportado
        """
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {file_path}")

        # Si es texto plano, retorna tal cual
        if path.suffix.lower() == ".txt":
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

        if path.suffix.lower() == ".md":
            with open(path, "r", encoding="utf-8") as f:
                return f.read()

        # PDF: pymupdf produce texto limpio (pdfminer/pdfplumber pegan palabras)
        if path.suffix.lower() == ".pdf":
            if PYMUPDF_AVAILABLE:
                try:
                    doc = pymupdf.open(str(path))
                    pages = [page.get_text() for page in doc]
                    doc.close()
                    return "\n\n".join(pages)
                except Exception as e:
                    raise ValueError(f"Error extrayendo PDF {path.name}: {e}") from e
            elif MARKITDOWN_AVAILABLE:
                result = self.markdown_converter.convert(str(path))
                return result.text_content
            else:
                raise ImportError("Ni pymupdf ni MarkItDown disponibles para PDF")

        # DOCX, XLSX, etc.: MarkItDown
        if MARKITDOWN_AVAILABLE:
            try:
                result = self.markdown_converter.convert(str(path))
                return result.text_content
            except Exception as e:
                raise ValueError(f"Error convirtiendo {path.name}: {e}") from e
        else:
            raise ImportError(
                f"MarkItDown no disponible. No puedo procesar {path.suffix}"
            )

    def detect_pii(self, text: str) -> List[Dict]:
        """
        Detecta información personal identificable (PII).

        Args:
            text: Texto a analizar

        Returns:
            List[Dict]: Lista de PII encontrados con tipo y posición

        Raises:
            ImportError: Si Presidio no está disponible
        """
        if not PRESIDIO_AVAILABLE:
            print("⚠️ Presidio no disponible. PII detection desactivada.")
            return []

        try:
            results = self.analyzer.analyze(text, language="es")
            return [
                {
                    "type": result.entity_type,
                    "start": result.start,
                    "end": result.end,
                    "text": text[result.start:result.end],
                    "score": result.score
                }
                for result in results
            ]
        except Exception as e:
            print(f"⚠️ Error en Presidio: {e}")
            return []

    def anonymize_pii(self, text: str, method: str = "replace") -> Tuple[str, List[Dict]]:
        """
        Anonimiza PII en el texto.

        Args:
            text: Texto a anonimizar
            method: "replace" (reemplaza con <TIPO_ENTIDAD>), "redact" (borra)

        Returns:
            Tuple[str, List[Dict]]: (texto anonimizado, lista de PII encontrados)

        Raises:
            ImportError: Si Presidio no está disponible
        """
        if not PRESIDIO_AVAILABLE:
            print("⚠️ Presidio no disponible. Retornando texto original.")
            return text, []

        try:
            from presidio_anonymizer.entities import OperatorConfig

            results = self.analyzer.analyze(text, language="es")
            if not results:
                return text, []

            if method == "replace":
                operators = {"DEFAULT": OperatorConfig("replace", {"new_value": "<REDACTED>"})}
            elif method == "redact":
                operators = {"DEFAULT": OperatorConfig("redact", {})}
            else:
                raise ValueError(f"Método desconocido: {method}")

            anonymized_result = self.anonymizer.anonymize(
                text=text,
                analyzer_results=results,
                operators=operators,
            )

            pii_found = [
                {
                    "type": r.entity_type,
                    "start": r.start,
                    "end": r.end,
                    "score": r.score,
                }
                for r in results
            ]

            return anonymized_result.text, pii_found

        except Exception as e:
            print(f"⚠️ Error anonimizando: {e}. Retornando texto original.")
            return text, []

    def clean_text(self, text: str) -> str:
        """
        Limpia el texto preservando la estructura de párrafos.

        Args:
            text: Texto a limpiar

        Returns:
            str: Texto limpio
        """
        text = "".join(char for char in text if ord(char) >= 32 or char in "\n\t")
        text = re.sub(r"[^\S\n]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = text.strip()

        return text

    def process_document(self, file_path: str, anonymize: bool = True) -> Tuple[str, Dict]:
        """
        Pipeline completo: conversión + anonimización.

        Args:
            file_path: Ruta del archivo
            anonymize: Si debe anonimizar PII (default: True)

        Returns:
            Tuple[str, Dict]: (contenido procesado, metadata)

        Raises:
            FileNotFoundError: Si el archivo no existe
            ValueError: Si hay error en procesamiento
        """
        path = Path(file_path)

        # 1. Convertir a Markdown
        markdown_text = self.convert_to_markdown(file_path)

        # 2. Limpiar
        cleaned_text = self.clean_text(markdown_text)

        # 3. Anonimizar PII
        if anonymize:
            processed_text, pii_found = self.anonymize_pii(cleaned_text)
        else:
            processed_text = cleaned_text
            pii_found = []

        # Metadata
        metadata = {
            "filename": path.name,
            "file_size": path.stat().st_size,
            "char_count": len(processed_text),
            "pii_found": len(pii_found),
            "pii_types": list(set(p["type"] for p in pii_found)),
            "anonymized": anonymize
        }

        return processed_text, metadata


# Singleton
_preprocessor = None


def get_preprocessor() -> Preprocessor:
    """
    Obtiene o crea la instancia global del Preprocessor.

    Returns:
        Preprocessor: Instancia del preprocessor
    """
    global _preprocessor
    if _preprocessor is None:
        _preprocessor = Preprocessor()
    return _preprocessor


if __name__ == "__main__":
    # Test simple
    preprocessor = get_preprocessor()

    # Crear documento de prueba
    test_file = "/tmp/test_document.md"
    test_content = """
    # Clínica Delos

    ## Paciente: Juan García
    Email: juan.garcia@email.com
    DNI: 12345678-A
    Teléfono: 555-1234

    Diagnóstico: Hipertensión
    Tratamiento: Enalapril 10mg

    Contacto de emergencia: María García (555-5678)
    """

    with open(test_file, "w") as f:
        f.write(test_content)

    # Procesar
    processed, meta = preprocessor.process_document(test_file, anonymize=True)

    print("Original:")
    print(test_content)
    print("\n\nProcesado:")
    print(processed)
    print(f"\n\nMetadata: {meta}")
