"""Testes do CodeExecutor — verifica detecção de extensão, execução de Python
e geração de PDF via fpdf.

Cobre:
1. Detecção de extensão Python antes de PDF para código executável
2. Execução de código fpdf na sandbox
3. Geração de PDF válido (header %PDF)
4. Salvamento do PDF no diretório de resultados
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from iaglobal._paths import _detect_extension


class TestExtensionDetection:
    """Verifica ordem de detecção: Python deve vir antes de PDF para código executável."""

    def test_python_fpdf_code_detected_as_py(self):
        code = '''import logging
from fpdf import FPDF

class PDF(FPDF):
    def header(self):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "Test", 0, 1)

pdf = PDF()
pdf.add_page()
pdf.output("/tmp/test.pdf")
'''
        task = "crie uma receita de bolo de laranja com cauda em pdf com tema escuro"
        assert _detect_extension(code, task) == ".py"

    def test_markdown_content_detected_as_pdf(self):
        code = """# Receita de Bolo de Laranja

## Ingredientes
- 3 laranjas
- 3 ovos
"""
        task = "crie uma receita em pdf"
        assert _detect_extension(code, task) == ".pdf"

    def test_pure_python_detected(self):
        code = '''def main():
    print("hello")
'''
        task = "escreva uma funcao"
        assert _detect_extension(code, task) == ".py"


class TestPDFGeneration:
    """Testa geração de PDF via code_executor."""

    @pytest.mark.asyncio
    async def test_fpdf_code_generates_valid_pdf(self):
        import asyncio
        from iaglobal.graphs.nodes.no_code_executor import run_code_executor

        code = '''from fpdf import FPDF

class PDFDarkTheme(FPDF):
    def header(self):
        self.set_font("Arial", "B", 12)
        self.cell(0, 10, "Test PDF", 0, 1, "C")

    def chapter_title(self, title):
        self.set_font("Arial", "B", 14)
        self.cell(0, 10, title, 0, 1, "L")

    def chapter_body(self, body):
        self.set_font("Arial", "", 12)
        self.multi_cell(0, 7, body)
        self.ln()

pdf = PDFDarkTheme()
pdf.add_page()
pdf.chapter_title("Ingredientes")
pdf.chapter_body("Test content for PDF generation")
pdf.output("/tmp/test_pdf_gen.pdf")
'''

        ctx = {
            'input': {'task': 'crie uma receita em pdf'},
            'memory': {'coder': {'output': code}}
        }

        result = await run_code_executor(ctx)
        assert result.get('success') is True
        assert result.get('final_file') is not None

        # Verifica que o PDF foi criado
        if result.get('final_file'):
            import os
            pdf_path = result.get('final_file')
            assert os.path.exists(pdf_path), f"PDF not found at {pdf_path}"

            with open(pdf_path, 'rb') as f:
                header = f.read(4)
                assert header == b'%PDF', f"Invalid PDF header: {header}"

    @pytest.mark.asyncio
    async def test_pdf_saved_in_result_directory(self):
        import asyncio
        from iaglobal.graphs.nodes.no_code_executor import run_code_executor
        from iaglobal._paths import RESULTS_DIR

        code = '''from fpdf import FPDF
pdf = FPDF()
pdf.add_page()
pdf.cell(0, 10, "PDF Test", 0, 1)
pdf.output("/tmp/code_exec_test.pdf")
'''

        ctx = {
            'input': {'task': 'gerar pdf'},
            'memory': {'coder': {'output': code}}
        }

        result = await run_code_executor(ctx)
        assert result.get('success') is True

        # Verifica que o PDF está em RESULTS_DIR
        if result.get('final_file'):
            assert 'result' in result.get('final_file'), "PDF should be in result directory"