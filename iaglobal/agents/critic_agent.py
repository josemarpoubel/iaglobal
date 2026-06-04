"""CriticAgent — Sensor de qualidade dentro do CognitiveProxy.

Contrato RESTRITO (leiame.md):
- NÃO executar busca web
- NÃO escolher modelo
- NÃO reescrever prompt livremente
- NÃO tomar decisão final sozinho
- NÃO substituir resultado do pipeline

PODE SOMENTE:
- Avaliar saída gerada pelo modelo
- Emitir score estruturado (JSON)
- Sinalizar falhas
- Sugerir correções (opcional)
"""

import re
import json
from typing import Dict, Any, List

from iaglobal.validation.engine import ValidationEngine
from iaglobal.providers.provider_router import route_generate
from iaglobal.providers.provider_config import ProviderConfig
from iaglobal.utils.logger import logger


class CriticAgent:

    def __init__(self):
        self.DANGEROUS_PATTERNS = [
            "eval(", "exec(", "os.system(", "subprocess.run(shell=True"
        ]
        self.validator = ValidationEngine()
        self._critic_degraded = False

    # =========================================================================
    # API PÚBLICA — CONTRATO OBRIGATÓRIO
    # =========================================================================

    def avaliar(self, task: str, prompt: str, output: str) -> Dict[str, Any]:
        """Avalia saída do modelo. Retorna JSON conforme contrato.

        Contrato de saída (OBRIGATÓRIO):
        {
            "approved": bool,
            "score": float (0-100),
            "issues": [str],
            "fix_suggestions": [str]
        }
        """
        logger.info(f"[CRITIC] Avaliando: task_len={len(task)} output_len={len(output)}")
        try:
            issues = []
            suggestions = []

            # 1. Auditoria estática (código)
            if "```" in output or "def " in output:
                static = self._auditar_codigo(output)
                if static["issues"]:
                    issues.extend(static["issues"])
                    suggestions.extend(static["suggestions"])

            # 2. Avaliação via LLM (apenas score, sem decisão)
            scores = self._avaliar_multidimensional(task, output)

            # 3. Calcular score agregado
            score = self._calcular_score_agregado(scores)

            # 4. Detectar problemas comuns
            if not output or len(output.strip()) < 10:
                issues.append("Resposta vazia ou muito curta")
                score = min(score, 10)
            if "UNKNOWN" in output:
                issues.append("Modelo reportou UNKNOWN — pode ser insuficiente")
                score = min(score, 30)
            if re.search(r"Error:|Traceback|SyntaxError", output):
                issues.append("Output contém erro de execução")
                suggestions.append("Corrigir erro antes de usar")
                score = max(0, score - 20)

            approved = score >= 60

            result = {
                "approved": approved,
                "score": round(score, 1),
                "issues": issues[:5],
                "fix_suggestions": suggestions[:3],
                "_critic_degraded": self._critic_degraded,
            }

            if approved:
                logger.info(f"[CRITIC] Aprovado: score={score:.1f}")
            else:
                logger.info(f"[CRITIC] Rejeitado: score={score:.1f} issues={issues}")

            return result

        except Exception as e:
            logger.warning(f"[CRITIC] Falha na avaliação: {e}")
            self._critic_degraded = True
            return {
                "approved": False,
                "score": 0.0,
                "issues": [f"Erro interno do Critic: {e}"],
                "fix_suggestions": [],
                "_critic_degraded": True,
            }

    def avaliar_solucao(self, task: str, codigo: str) -> str:
        """Wrapper compatibilidade — retorna string JSON."""
        result = self.avaliar(task, "", codigo)
        return json.dumps(result)

    def avaliar_com_scores(self, task: str, codigo: str) -> Dict[str, Any]:
        """Wrapper compatibilidade — retorna dict."""
        return self.avaliar(task, "", codigo)

    # =========================================================================
    # MÉTODOS INTERNOS (APENAS AVALIAÇÃO, SEM DECISÃO)
    # =========================================================================

    def _auditar_codigo(self, codigo: str) -> Dict:
        """Auditoria estática — apenas detecta problemas, sem decidir."""
        issues = []
        suggestions = []

        if not codigo or not codigo.strip():
            issues.append("Código vazio")
            return {"issues": issues, "suggestions": suggestions}

        if codigo.strip().startswith("<!DOCTYPE") or codigo.strip().startswith("<html"):
            return {"issues": [], "suggestions": []}

        try:
            self.validator.validate(codigo)
        except SyntaxError as e:
            issues.append(f"Erro de sintaxe: {e}")
            suggestions.append("Corrigir sintaxe do código")

        for pattern in self.DANGEROUS_PATTERNS:
            if pattern in codigo:
                issues.append(f"Padrão perigoso detectado: {pattern}")
                suggestions.append(f"Substituir {pattern} por alternativa segura")

        return {"issues": issues, "suggestions": suggestions}

    def _avaliar_multidimensional(self, task: str, codigo: str) -> Dict[str, Any]:
        """Avalia código via LLM — retorna scores, NÃO toma decisão."""
        prompt = self._montar_prompt_avaliacao(task, codigo)

        modelos = self._get_modelos()

        for model in modelos:
            try:
                resultado = route_generate(model, prompt, task_type="critic")
                if resultado:
                    scores = self._parse_json_response(resultado.strip())
                    if scores:
                        self._critic_degraded = False
                        return scores
                    logger.debug(f"[CRITIC] {model} retornou JSON inválido")
            except Exception as e:
                logger.debug(f"[CRITIC] {model} falhou: {e}")

        self._critic_degraded = True
        logger.warning("[CRITIC] Todos os modelos falharam — scores degradados")
        return self._fallback_scores()

    def _get_modelos(self) -> List[str]:
        """Retorna lista de modelos para avaliação (sem decisão de roteamento)."""
        return [
            "ollama/" + ProviderConfig.DEFAULT_OLLAMA_MODEL,
        ]

    def _montar_prompt_avaliacao(self, task: str, codigo: str) -> str:
        """Prompt de avaliação — APENAS solicita JSON de score, sem ação."""
        return f"""
Você é um validador técnico. Avalie a solução abaixo.

TAREFA: {task}

CÓDIGO:
{codigo}

Retorne APENAS um JSON válido neste formato exato:
{{"correctness": <0-100>, "completeness": <0-100>, "security": <0-100>, "spec_match": <0-100>, "summary": "<breve motivo>"}}

Critérios:
- correctness: O código funciona?
- completeness: Cobre todos requisitos?
- security: Código seguro?
- spec_match: Segue a especificação?
"""

    def _parse_json_response(self, resposta: str) -> Dict[str, Any]:
        """Extrai JSON da resposta do modelo."""
        try:
            inicio = resposta.find("{")
            fim = resposta.rfind("}")
            if inicio != -1 and fim != -1 and fim > inicio:
                json_str = resposta[inicio:fim + 1]
                data = json.loads(json_str)
                if all(k in data for k in ["correctness", "completeness", "security", "spec_match"]):
                    return {
                        "correctness": max(0, min(100, float(data["correctness"]))),
                        "completeness": max(0, min(100, float(data["completeness"]))),
                        "security": max(0, min(100, float(data["security"]))),
                        "spec_match": max(0, min(100, float(data["spec_match"]))),
                        "summary": data.get("summary", ""),
                    }
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        return {}

    def _fallback_scores(self) -> Dict[str, Any]:
        return {
            "correctness": 50.0,
            "completeness": 50.0,
            "security": 50.0,
            "spec_match": 50.0,
            "summary": "Fallback: avaliação indisponível",
        }

    def _calcular_score_agregado(self, scores: Dict[str, Any]) -> float:
        return (
            scores.get("correctness", 0) * 0.35 +
            scores.get("completeness", 0) * 0.25 +
            scores.get("security", 0) * 0.25 +
            scores.get("spec_match", 0) * 0.15
        )
