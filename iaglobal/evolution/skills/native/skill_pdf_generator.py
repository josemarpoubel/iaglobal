# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Skill nativa para geração de PDF com jsPDF (client-side).
Gera app web completo: HTML + CSS (dark theme) + JS (jsPDF infinite canvas + markdown parsing).
"""

from typing import Dict, Any

# Template HTML completo com jsPDF via CDN
from iaglobal.evolution.skills.native.skill_registry import skill_registry

JSPDF_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Gerador PDF Infinito - Tema Escuro</title>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eaeaea;
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 900px;
            margin: 0 auto;
            background: #16213e;
            border-radius: 16px;
            padding: 32px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            border: 1px solid #0f3460;
        }
        h1 {
            text-align: center;
            margin-bottom: 8px;
            color: #e94560;
            font-size: 2rem;
        }
        .subtitle {
            text-align: center;
            color: #888;
            margin-bottom: 32px;
            font-size: 1rem;
        }
        .editor-section { margin-bottom: 24px; }
        label {
            display: block;
            margin-bottom: 8px;
            font-weight: 600;
            color: #e0e0e0;
        }
        textarea {
            width: 100%;
            min-height: 350px;
            padding: 16px;
            background: #0f3460;
            color: #eaeaea;
            border: 2px solid #0f3460;
            border-radius: 8px;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 14px;
            line-height: 1.6;
            resize: vertical;
            transition: border-color 0.2s;
        }
        textarea:focus {
            outline: none;
            border-color: #e94560;
        }
        .btn-group {
            display: flex;
            gap: 12px;
            margin-top: 16px;
            flex-wrap: wrap;
        }
        button {
            padding: 14px 28px;
            border: none;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        .btn-primary {
            background: #e94560;
            color: white;
        }
        .btn-primary:hover {
            background: #d63a55;
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(233, 69, 96, 0.4);
        }
        .btn-primary:disabled {
            opacity: 0.6;
            cursor: not-allowed;
            transform: none;
        }
        .btn-secondary {
            background: #0f3460;
            color: #e0e0e0;
            border: 1px solid #e94560;
        }
        .btn-secondary:hover {
            background: #1a3c5e;
        }
        .toast {
            position: fixed;
            bottom: 24px;
            right: 24px;
            padding: 16px 24px;
            border-radius: 8px;
            font-weight: 500;
            transform: translateY(100px);
            opacity: 0;
            transition: all 0.3s ease;
            z-index: 1000;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
        }
        .toast.show {
            transform: translateY(0);
            opacity: 1;
        }
        .toast.success { background: #10b981; color: white; }
        .toast.error { background: #ef4444; color: white; }
        .toast.info { background: #3b82f6; color: white; }
        .markdown-hint {
            font-size: 0.85rem;
            color: #888;
            margin-top: 8px;
            padding: 12px;
            background: #0f3460;
            border-radius: 6px;
            font-family: monospace;
            white-space: pre-wrap;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>\ud83d\udcc4 Gerador PDF Infinito</h1>
        <p class="subtitle">Tema escuro \u2022 jsPDF \u2022 Markdown \u2022 Pagina\u00e7\u00e3o autom\u00e1tica</p>

        <div class="editor-section">
            <label for="text-input">Digite seu texto (suporta Markdown b\u00e1sico)</label>
            <textarea id="text-input" placeholder="# T\u00edtulo\n\nDigite seu conte\u00fado aqui...\n\n**Negrito** \u2022 *It\u00e1lico* \u2022 \`C\u00f3digo\`\n\n---\n\n## Subt\u00edtulo\n\nPar\u00e1grafos longos viram p\u00e1ginas automaticamente."></textarea>
            <div class="markdown-hint">
<strong>Markdown suportado:</strong>
# T\u00edtulo 1  \u2022  ## T\u00edtulo 2  \u2022  **Negrito**  \u2022  *It\u00e1lico*  \u2022  \`C\u00f3digo\`  \u2022  --- (linha horizontal)
</div>
        </div>

        <div class="btn-group">
            <button class="btn-primary" id="generate-btn" onclick="generatePDF()">
                <span id="btn-text">\ud83d\udcc4 Criar PDF</span>
                <span id="btn-loader" style="display:none;">\u23f3 Gerando...</span>
            </button>
            <button class="btn-secondary" onclick="clearText()">\ud83d\udd91\ufe0f Limpar</button>
        </div>
    </div>

    <div class="toast" id="toast"></div>

    <script>
        const { jsPDF } = window.jspdf;

        function showToast(message, type = 'info') {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast show ' + type;
            setTimeout(() => toast.classList.remove('show'), 3000);
        }

        function parseMarkdown(text) {
            const lines = text.split('\n');
            const formatted = [];

            for (let line of lines) {
                if (line.startsWith('### ')) {
                    formatted.push({type: 'h3', text: line.slice(4), size: 14, style: 'bold'});
                } else if (line.startsWith('## ')) {
                    formatted.push({type: 'h2', text: line.slice(3), size: 16, style: 'bold'});
                } else if (line.startsWith('# ')) {
                    formatted.push({type: 'h1', text: line.slice(2), size: 20, style: 'bold'});
                } else if (line.trim() === '---' || line.trim() === '***') {
                    formatted.push({type: 'hr'});
                } else if (line.includes('`')) {
                    formatted.push({type: 'code', text: line});
                } else {
                    formatted.push({type: 'p', text: line});
                }
            }
            return formatted;
        }

        function addTextToPDF(doc, text, x, y, maxWidth, fontSize = 12, style = 'normal') {
            doc.setFontSize(fontSize);
            doc.setFont('helvetica', style);

            const lines = doc.splitTextToSize(text, maxWidth);
            let currentY = y;

            for (let line of lines) {
                if (currentY + fontSize > doc.internal.pageSize.getHeight() - 20) {
                    doc.addPage();
                    currentY = 20;
                }
                doc.text(line, x, currentY);
                currentY += fontSize * 0.6;
            }
            return currentY;
        }

        async function generatePDF() {
            const btn = document.getElementById('generate-btn');
            const btnText = document.getElementById('btn-text');
            const btnLoader = document.getElementById('btn-loader');
            const text = document.getElementById('text-input').value.trim();

            if (!text) {
                showToast('Digite algum texto primeiro!', 'error');
                return;
            }

            btn.disabled = true;
            btnText.style.display = 'none';
            btnLoader.style.display = 'inline';

            try {
                const { jsPDF } = window.jspdf;
                const doc = new jsPDF({
                    orientation: 'portrait',
                    unit: 'mm',
                    format: 'a4'
                });

                const margin = 20;
                const pageHeight = doc.internal.pageSize.getHeight();
                const pageWidth = doc.internal.pageSize.getWidth();
                const maxWidth = pageWidth - 2 * margin;
                let y = margin;

                const totalPagesEstimate = Math.ceil(text.length / 1800) + 1;
                for (let p = 1; p <= totalPagesEstimate; p++) {
                    if (p > 1) doc.addPage();
                    doc.setFillColor(26, 26, 46);
                    doc.rect(0, 0, pageWidth, pageHeight, 'F');
                }
                doc.setPage(1);
                y = margin;

                const elements = parseMarkdown(text);

                for (let el of elements) {
                    if (el.type === 'hr') {
                        if (y > pageHeight - 30) { doc.addPage(); y = margin; }
                        doc.setDrawColor(233, 69, 96);
                        doc.setLineWidth(0.5);
                        doc.line(margin, y, pageWidth - margin, y);
                        y += 8;
                        continue;
                    }

                    if (el.type === 'h1') {
                        if (y > pageHeight - 40) { doc.addPage(); y = margin; }
                        y = addTextToPDF(doc, el.text, margin, y, pageWidth - 2*margin, el.size, 'bold');
                        y += 4;
                        continue;
                    }
                    if (el.type === 'h2') {
                        if (y > pageHeight - 30) { doc.addPage(); y = margin; }
                        y = addTextToPDF(doc, el.text, margin, y, pageWidth - 2*margin, el.size, 'bold');
                        y += 3;
                        continue;
                    }
                    if (el.type === 'h3') {
                        if (y > pageHeight - 30) { doc.addPage(); y = margin; }
                        y = addTextToPDF(doc, el.text, margin, y, pageWidth - 2*margin, el.size, 'bold');
                        y += 2;
                        continue;
                    }

                    if (el.type === 'code') {
                        doc.setFont('courier', 'normal');
                        doc.setFontSize(10);
                        doc.setFillColor(15, 52, 96);
                        const lines = doc.splitTextToSize(el.text, maxWidth - 10);
                        for (let line of lines) {
                            if (y > pageHeight - 20) { doc.addPage(); y = margin; }
                            doc.rect(margin - 2, y - 2, maxWidth + 4, lines.length * 5 + 4, 'F');
                            doc.text(line, margin + 3, y + 3);
                            y += 5;
                        }
                        y += 2;
                    } else {
                        y = addTextToPDF(doc, el.text, margin, y, maxWidth, 12, 'normal');
                    }

                    y += 3;
                }

                const pageCount = doc.getNumberOfPages();
                for (let i = 1; i <= pageCount; i++) {
                    doc.setPage(i);
                    doc.setFontSize(8);
                    doc.setTextColor(128);
                    doc.text(
                        `P\u00e1gina ${i} de ${pageCount}`,
                        pageWidth / 2,
                        pageHeight - 10,
                        { align: 'center' }
                    );
                }

                doc.save('documento-infinito.pdf');
                showToast('\u2705 PDF gerado com sucesso!', 'success');

            } catch (err) {
                console.error(err);
                showToast('\u274c Erro ao gerar PDF: ' + err.message, 'error');
            } finally {
                btn.disabled = false;
                btnText.style.display = 'inline';
                btnLoader.style.display = 'none';
            }
        }

        function clearText() {
            document.getElementById('text-input').value = '';
            showToast('Texto limpo', 'info');
        }

        function showToast(message, type = 'info') {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast show ' + type;
            setTimeout(() => toast.classList.remove('show'), 3000);
        }

        function parseMarkdown(text) {
            const lines = text.split('\n');
            const formatted = [];

            for (let line of lines) {
                if (line.startsWith('### ')) {
                    formatted.push({type: 'h3', text: line.slice(4), size: 14, style: 'bold'});
                } else if (line.startsWith('## ')) {
                    formatted.push({type: 'h2', text: line.slice(3), size: 16, style: 'bold'});
                } else if (line.startsWith('# ')) {
                    formatted.push({type: 'h1', text: line.slice(2), size: 20, style: 'bold'});
                } else if (line.trim() === '---' || line.trim() === '***') {
                    formatted.push({type: 'hr'});
                } else if (line.includes('`')) {
                    formatted.push({type: 'code', text: line});
                } else {
                    formatted.push({type: 'p', text: line});
                }
            }
            return formatted;
        }

        function addTextToPDF(doc, text, x, y, maxWidth, fontSize = 12, style = 'normal') {
            doc.setFontSize(fontSize);
            doc.setFont('helvetica', style);

            const lines = doc.splitTextToSize(text, maxWidth);
            let currentY = y;

            for (let line of lines) {
                if (currentY + fontSize > doc.internal.pageSize.getHeight() - 20) {
                    doc.addPage();
                    currentY = 20;
                    doc.setFillColor(26, 26, 46);
                    doc.rect(0, 0, doc.internal.pageSize.getWidth(), doc.internal.pageSize.getHeight(), 'F');
                }
                doc.text(line, x, currentY);
                currentY += fontSize * 0.6;
            }
            return currentY;
        }

        function showToast(message, type = 'info') {
            const toast = document.getElementById('toast');
            toast.textContent = message;
            toast.className = 'toast show ' + type;
            setTimeout(() => toast.classList.remove('show'), 3000);
        }

        function clearText() {
            document.getElementById('text-input').value = '';
            showToast('Texto limpo', 'info');
        }
    </script>
</body>
</html>
"""


async def run_pdf_generator(ctx: Dict[str, Any]) -> Dict[str, Any]:
    """
    Skill nativa: gera app web completo para PDF infinito com jsPDF + tema escuro + markdown parsing.
    """
    task = str(ctx.get("input", {}).get("task", ""))

    # Detecta se a task pede PDF/web/jsPDF
    task_lower = task.lower()
    pdf_keywords = [
        "pdf",
        "jspdf",
        "página infinita",
        "infinite canvas",
        "gerar pdf",
        "criar pdf",
        "dark theme",
        "tema escuro",
    ]

    if not any(kw in task_lower for kw in pdf_keywords):
        return {
            "success": False,
            "code": "",
            "error": "Task não é sobre geração de PDF com jsPDF",
            "metadata": {"skill": "pdf_generator"},
        }

    # Retorna o template HTML completo
    return {
        "success": True,
        "code": JSPDF_HTML_TEMPLATE,
        "metadata": {
            "skill": "pdf_generator",
            "type": "html",
            "description": "App web completo: HTML + CSS dark theme + jsPDF (infinite canvas + markdown parsing + page numbers)",
        },
    }


# Registra skill no registry global (chamado no import)
def register_skill():
    from iaglobal.evolution.skills.native.skill_registry import skill_registry
    from iaglobal.evolution.skills.native.skill import Skill

    PDF_SKILL = Skill(
        name="pdf_generator",
        description="Gera app web HTML+JS para PDF infinito com jsPDF, tema escuro, markdown parsing, paginação automática",
        inputs=["task"],
        outputs=["code"],
        constraints=["html", "javascript", "jspdf", "markdown", "dark-theme"],
        execution_policy="SINGLE_RUN",
        version="v1",
        tags=[
            "pdf",
            "jspdf",
            "html",
            "javascript",
            "dark-theme",
            "markdown",
            "infinite-canvas",
        ],
        template_type="deterministic",
        template_prompt=None,
    )

    # Define run_fn após criação
    PDF_SKILL.run_fn = run_pdf_generator

    from iaglobal.evolution.skills.native.skill_registry import skill_registry

    skill_registry.register(PDF_SKILL)
    print("[SKILL] pdf_generator registrada no SkillRegistry")


# Auto-registra ao importar
register_skill()


# Export for lazy loader

skill_pdf_generator = skill_registry.get("pdf_generator")
