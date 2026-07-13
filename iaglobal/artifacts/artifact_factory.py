import json
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime, timezone

from iaglobal._paths import RESULTS_DIR
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.artifacts.factory")


class ArtifactFactory:
    FORMAT_HANDLERS = {}

    @classmethod
    def render(
        cls,
        obj: Any,
        fmt: str = "pdf",
        params: Optional[Dict] = None,
        filename: Optional[str] = None,
    ) -> str:
        params = params or {}
        if fmt in cls.FORMAT_HANDLERS:
            return cls.FORMAT_HANDLERS[fmt](obj, params)

        if fmt == "pdf":
            return cls._render_pdf(obj, params)
        elif fmt == "html":
            return cls._render_html(obj, params)
        elif fmt == "json":
            return cls._render_json(obj, params)
        elif fmt == "txt":
            return cls._render_txt(obj, params)
        else:
            return cls._render_txt(obj, params)

    @classmethod
    def _resolve_path(cls, fmt: str, filename: Optional[str] = None) -> str:
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        if not filename:
            filename = f"artifact_{ts}.{fmt}"
        elif not filename.endswith(f".{fmt}"):
            filename = f"{filename}.{fmt}"
        path = RESULTS_DIR / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        return str(path)

    @classmethod
    def _render_pdf(cls, obj: Any, params: Dict) -> str:
        markdown_text = obj if isinstance(obj, str) else str(obj)
        dark = params.get("dark", True)
        output = cls._resolve_path("pdf", params.get("filename"))
        if dark:
            from iaglobal.tools.builtins.pdf_tools import generate_dark_pdf

            return generate_dark_pdf(markdown_text, output)
        else:
            from iaglobal.tools.builtins.pdf_tools import generate_light_pdf

            return generate_light_pdf(markdown_text, output)

    @classmethod
    def _render_html(cls, obj: Any, params: Dict) -> str:
        content = obj if isinstance(obj, str) else str(obj)
        dark = params.get("dark", True)
        bg = "#1e1e1e" if dark else "#ffffff"
        fg = "#dcdcdc" if dark else "#333333"
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>body{{background:{bg};color:{fg};font-family:Helvetica,Arial;padding:40px;max-width:800px;margin:auto}}
h1{{color:#64b5f6}} h2{{color:#90caf9}} pre{{background:{"#2d2d2d" if dark else "#f5f5f5"};padding:15px;border-radius:5px;overflow-x:auto}}
code{{background:{"#2d2d2d" if dark else "#f5f5f5"};padding:2px 5px;border-radius:3px}}
blockquote{{border-left:4px solid #64b5f6;padding-left:15px;margin-left:0;color:{"#aaa" if dark else "#666"}}}
</style></head><body>{content}</body></html>"""
        path = cls._resolve_path("html", params.get("filename"))
        Path(path).write_text(html, encoding="utf-8")
        logger.info("[ARTIFACT] HTML gerado: %s", path)
        return path

    @classmethod
    def _render_json(cls, obj: Any, params: Dict) -> str:
        if isinstance(obj, str):
            try:
                data = json.loads(obj)
            except json.JSONDecodeError:
                data = {"content": obj}
        else:
            data = obj
        path = cls._resolve_path("json", params.get("filename"))
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info("[ARTIFACT] JSON gerado: %s", path)
        return path

    @classmethod
    def _render_txt(cls, obj: Any, params: Dict) -> str:
        text = obj if isinstance(obj, str) else str(obj)
        path = cls._resolve_path("txt", params.get("filename"))
        Path(path).write_text(text, encoding="utf-8")
        logger.info("[ARTIFACT] TXT gerado: %s", path)
        return path


artifact_factory = ArtifactFactory()
