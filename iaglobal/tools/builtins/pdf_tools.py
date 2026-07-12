import os
import tempfile
from pathlib import Path
from typing import Optional

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.tools.pdf")


def generate_dark_pdf(
    markdown_text: str,
    output_path: Optional[str] = None,
) -> str:
    if output_path is None:
        output_path = str(Path(tempfile.mkdtemp()) / "output_dark.pdf")

    from fpdf import FPDF

    class DarkPDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(150, 150, 150)
            self.cell(0, 5, "iaglobal", align="R", new_x="LMARGIN", new_y="NEXT")
            self.line(10, 12, 200, 12)
            self.set_draw_color(60, 60, 60)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(100, 100, 100)
            self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}}", align="C")

    pdf = DarkPDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    pdf.set_fill_color(30, 30, 30)
    pdf.rect(0, 0, 210, 297, "F")

    pdf.set_text_color(220, 220, 220)
    pdf.set_draw_color(60, 60, 60)
    pdf.set_font("Helvetica", "B", 16)
    pdf.ln(5)

    lines = markdown_text.split("\n")
    in_code_block = False
    code_buffer = []

    for line in lines:
        stripped = line.strip()

        if stripped.startswith("```"):
            if in_code_block:
                in_code_block = False
                code_text = "\n".join(code_buffer)
                pdf.set_fill_color(20, 20, 20)
                pdf.set_text_color(180, 230, 120)
                pdf.set_font("Courier", "", 8)
                for cline in code_text.split("\n"):
                    if cline:
                        pdf.cell(0, 4.5, cline, new_x="LMARGIN", new_y="NEXT")
                    else:
                        pdf.ln(3)
                pdf.set_text_color(220, 220, 220)
                code_buffer = []
            else:
                in_code_block = True
            continue

        if in_code_block:
            code_buffer.append(line)
            continue

        if stripped.startswith("# "):
            pdf.set_font("Helvetica", "B", 18)
            pdf.set_text_color(100, 180, 255)
            pdf.cell(0, 10, stripped[2:], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

        elif stripped.startswith("## "):
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_text_color(150, 200, 255)
            pdf.cell(0, 8, stripped[3:], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

        elif stripped.startswith("### "):
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(180, 210, 255)
            pdf.cell(0, 7, stripped[4:], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)

        elif stripped.startswith("- ") or stripped.startswith("* "):
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(220, 220, 220)
            x = pdf.get_x()
            pdf.cell(5, 5, chr(8226), new_x="END", new_y="NEXT")
            pdf.set_x(x + 5)
            pdf.multi_cell(0, 5, stripped[2:])

        elif stripped.startswith("> "):
            pdf.set_fill_color(40, 40, 50)
            pdf.set_text_color(180, 180, 200)
            pdf.set_font("Helvetica", "I", 10)
            pdf.multi_cell(0, 5, stripped[2:], fill=True)

        elif stripped == "---":
            pdf.set_draw_color(60, 60, 60)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(3)

        elif stripped:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(220, 220, 220)
            pdf.multi_cell(0, 5, stripped)

        else:
            pdf.ln(3)

    pdf.output(output_path)
    logger.info("[PDF_TOOL] PDF escuro gerado: %s", output_path)
    return output_path


def generate_light_pdf(
    markdown_text: str,
    output_path: Optional[str] = None,
) -> str:
    if output_path is None:
        output_path = str(Path(tempfile.mkdtemp()) / "output_light.pdf")

    from fpdf import FPDF

    class LightPDF(FPDF):
        def header(self):
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(100, 100, 100)
            self.cell(0, 5, "iaglobal", align="R", new_x="LMARGIN", new_y="NEXT")
            self.line(10, 12, 200, 12)

        def footer(self):
            self.set_y(-15)
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(150, 150, 150)
            self.cell(0, 10, f"Pagina {self.page_no()}/{{nb}}", align="C")

    pdf = LightPDF(orientation="P", unit="mm", format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.add_page()

    pdf.set_text_color(50, 50, 50)
    pdf.set_draw_color(200, 200, 200)
    pdf.set_font("Helvetica", "B", 16)
    pdf.ln(5)

    for line in markdown_text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# "):
            pdf.set_font("Helvetica", "B", 18)
            pdf.set_text_color(0, 80, 160)
            pdf.cell(0, 10, stripped[2:], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)
        elif stripped.startswith("## "):
            pdf.set_font("Helvetica", "B", 14)
            pdf.set_text_color(0, 100, 180)
            pdf.cell(0, 8, stripped[3:], new_x="LMARGIN", new_y="NEXT")
            pdf.ln(1)
        elif stripped:
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(50, 50, 50)
            pdf.multi_cell(0, 5, stripped)
        else:
            pdf.ln(3)

    pdf.output(output_path)
    logger.info("[PDF_TOOL] PDF claro gerado: %s", output_path)
    return output_path


from iaglobal.tools.tool_library import tool_library

tool_library.register(
    name="generate_dark_pdf",
    fn=generate_dark_pdf,
    tags=["pdf", "dark", "escuro", "tema escuro", "elegante", "documento", "gerar pdf", "converter pdf"],
    description="Gera um PDF com tema escuro elegante a partir de texto markdown",
)
tool_library.register(
    name="generate_light_pdf",
    fn=generate_light_pdf,
    tags=["pdf", "light", "claro", "tema claro", "documento", "gerar pdf"],
    description="Gera um PDF com tema claro a partir de texto markdown",
)
