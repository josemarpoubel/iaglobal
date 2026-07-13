# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
HypothesisGenerator — Gera hipóteses testáveis a partir de abstracts de papers.

Usa o critic_agent (ou outro agente LLM) para propor 3 hipóteses testáveis via:
1. Experimento computacional (código Python)
2. Análise de dados existentes
3. Simulação

Integra com:
- PaperParser (entrada: PaperMetadata)
- validation/engine.py (validação de schema)
- memory/data/json/{paper_id}.json (saída)
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

from iaglobal._paths import JSON_DIR
from iaglobal.utils.logger import get_logger
from iaglobal.agents.ingestion.paper_parser import PaperMetadata

logger = get_logger("iaglobal.agents.ingestion.hypothesis_generator")


@dataclass
class Hypothesis:
    """Hipótese testável gerada a partir de paper."""

    id: str
    description: str
    method: str  # "experiment" | "data_analysis" | "simulation"
    expected_outcome: str
    success_criteria: str
    paper_id: str = ""
    status: str = "pending"  # pending|running|passed|failed
    experiment_code: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HypothesisGenerator:
    """Gera hipóteses testáveis a partir de abstracts."""

    PROMPT_TEMPLATE = """
Dado este abstract de paper científico:

**Título**: {title}

**Abstract**:
{abstract}

**Tópicos**: {topics}

**Autores**: {authors}

---

Proponha 3 hipóteses testáveis que poderiam ser validadas via:
1. **Experimento computacional** (código Python executável em sandbox)
2. **Análise de dados existentes** (dataset público + análise estatística)
3. **Simulação** (modelo computacional + validação)

Para cada hipótese, forneça:
- **description**: O que está sendo testado (1-2 frases)
- **method**: "experiment" | "data_analysis" | "simulation"
- **expected_outcome**: Resultado esperado se a hipótese estiver correta
- **success_criteria**: Condição objetiva de sucesso (ex: "accuracy > 0.85", "p < 0.05")

Formato de saída (JSON estrito):
{{
  "hypotheses": [
    {{
      "id": "H1",
      "description": "...",
      "method": "experiment",
      "expected_outcome": "...",
      "success_criteria": "..."
    }},
    {{
      "id": "H2",
      "description": "...",
      "method": "data_analysis",
      "expected_outcome": "...",
      "success_criteria": "..."
    }},
    {{
      "id": "H3",
      "description": "...",
      "method": "simulation",
      "expected_outcome": "...",
      "success_criteria": "..."
    }}
  ]
}}

REGRAS:
1. Cada hipótese deve ser **falsificável** (pode ser provada falsa)
2. Critérios de sucesso devem ser **quantitativos** e **mensuráveis**
3. Métodos devem ser **executáveis computacionalmente** (sem equipamentos físicos)
4. Evitar hipóteses triviais ou óbvias demais
"""

    def __init__(self):
        pass

    async def generate(self, paper: PaperMetadata) -> List[Hypothesis]:
        """
        Gera 3 hipóteses testáveis a partir do paper.

        Args:
            paper: PaperMetadata com abstract e metadados

        Returns:
            Lista de 3 Hypothesis
        """
        try:
            # Construir prompt
            prompt = self.PROMPT_TEMPLATE.format(
                title=paper.title,
                abstract=paper.abstract,
                topics=", ".join(paper.topics),
                authors=", ".join(paper.authors),
            )

            # Chamar LLM via critic_agent (ou AgentBase)
            hypotheses_data = await self._call_llm(prompt, paper.paper_id)

            if not hypotheses_data or "hypotheses" not in hypotheses_data:
                logger.warning(
                    "[HYP] LLM não retornou hipóteses válidas para %s", paper.paper_id
                )
                return self._fallback_hypotheses(paper)

            # Converter para Hypothesis objects
            hypotheses = []
            for hyp_data in hypotheses_data["hypotheses"]:
                hyp = Hypothesis(
                    id=hyp_data.get("id", f"H{len(hypotheses) + 1}"),
                    description=hyp_data.get("description", ""),
                    method=hyp_data.get("method", "experiment"),
                    expected_outcome=hyp_data.get("expected_outcome", ""),
                    success_criteria=hyp_data.get("success_criteria", ""),
                    paper_id=paper.paper_id,
                )
                hypotheses.append(hyp)

            # Garantir que temos 3 hipóteses
            while len(hypotheses) < 3:
                fallback = self._generate_fallback_hypothesis(paper, len(hypotheses))
                hypotheses.append(fallback)

            logger.info(
                "[HYP] %s: %d hipóteses geradas", paper.paper_id, len(hypotheses)
            )
            return hypotheses

        except Exception as e:
            logger.error("[HYP] Erro ao gerar hipóteses para %s: %s", paper.paper_id, e)
            return self._fallback_hypotheses(paper)

    async def _call_llm(self, prompt: str, paper_id: str) -> Optional[Dict[str, Any]]:
        """Chama LLM para gerar hipóteses."""
        try:
            # Usar critic_agent ou AgentBase
            from iaglobal.agents.critic_agent import CriticAgent

            agent = CriticAgent()
            response = await agent.run(
                {
                    "prompt": prompt,
                    "task_type": "hypothesis_generation",
                    "paper_id": paper_id,
                }
            )

            # Extrair JSON da resposta
            json_str = self._extract_json_from_response(response.get("output", ""))
            if json_str:
                return json.loads(json_str)
            else:
                logger.warning("[HYP] LLM não retornou JSON válido para %s", paper_id)
                return None

        except ImportError:
            logger.warning("[HYP] CriticAgent não disponível — usando fallback")
            return None
        except Exception as e:
            logger.debug("[HYP] Erro ao chamar LLM: %s — usando fallback", e)
            return None

    def _extract_json_from_response(self, text: str) -> Optional[str]:
        """Extrai JSON do texto da resposta do LLM."""
        import re

        # Tentar encontrar bloco JSON entre ```json ... ```
        match = re.search(r"```json\s*([\s\S]*?)\s*```", text)
        if match:
            return match.group(1).strip()

        # Tentar encontrar JSON completo começando com {"hypotheses": ...}
        # Usar contador de chaves para lidar com nested braces
        start_idx = text.find('{"hypotheses"')
        if start_idx == -1:
            start_idx = text.find('{"hypotheses"')
            if start_idx == -1:
                # Fallback: tentar qualquer JSON
                try:
                    json.loads(text.strip())
                    return text.strip()
                except:
                    pass
                return None

        # Contar chaves para encontrar o fim do JSON
        brace_count = 0
        in_string = False
        escape_next = False
        end_idx = start_idx

        for i in range(start_idx, len(text)):
            char = text[i]

            if escape_next:
                escape_next = False
                continue

            if char == "\\":
                escape_next = True
                continue

            if char == '"' and not escape_next:
                in_string = not in_string
                continue

            if not in_string:
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        end_idx = i + 1
                        break

        if brace_count == 0 and end_idx > start_idx:
            json_str = text[start_idx:end_idx]
            try:
                json.loads(json_str)  # Validar
                return json_str
            except:
                pass

        # Fallback: tentar parsear todo o texto como JSON
        try:
            json.loads(text.strip())
            return text.strip()
        except:
            pass

        return None

    def _fallback_hypotheses(self, paper: PaperMetadata) -> List[Hypothesis]:
        """Gera hipóteses fallback quando LLM falha."""
        logger.info("[HYP] Gerando hipóteses fallback para %s", paper.paper_id)

        # Garantir que temos pelo menos 3 tópicos (usar placeholders se necessário)
        topics = paper.topics if paper.topics else []
        while len(topics) < 3:
            topics.append(f"aspect_{len(topics) + 1}")
        topics = topics[:3]

        return [
            Hypothesis(
                id="H1",
                description=f"O método proposto supera baselines em {topics[0]}",
                method="experiment",
                expected_outcome=f"Melhoria de ≥10% em métrica de {topics[0]}",
                success_criteria="metric_proposed > metric_baseline * 1.10",
                paper_id=paper.paper_id,
            ),
            Hypothesis(
                id="H2",
                description=f"A abordagem mantém performance em diferentes datasets de {topics[1]}",
                method="data_analysis",
                expected_outcome="Variação de performance < 5% entre datasets",
                success_criteria="std(performance) < 0.05",
                paper_id=paper.paper_id,
            ),
            Hypothesis(
                id="H3",
                description=f"O método escala linearmente com tamanho do input em {topics[2]}",
                method="simulation",
                expected_outcome="Tempo de execução cresce O(n) ou melhor",
                success_criteria="time(n*2) < time(n) * 2.5",
                paper_id=paper.paper_id,
            ),
        ]

    def _generate_fallback_hypothesis(
        self, paper: PaperMetadata, index: int
    ) -> Hypothesis:
        """Gera uma hipótese fallback individual."""
        methods = ["experiment", "data_analysis", "simulation"]
        method = methods[index % 3]

        topic = (
            paper.topics[index % len(paper.topics)]
            if paper.topics
            else f"method_{index + 1}"
        )

        return Hypothesis(
            id=f"H{index + 1}",
            description=f"Hipótese sobre {topic} via {method}",
            method=method,
            expected_outcome=f"Resultado positivo em {topic}",
            success_criteria="metric > threshold",
            paper_id=paper.paper_id,
        )

    def save_hypotheses(self, hypotheses: List[Hypothesis], paper_id: str) -> Path:
        """Salva hipóteses em JSON."""
        output_path = (
            JSON_DIR / "papers" / f"{paper_id.replace(':', '_')}_hypotheses.json"
        )
        output_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "paper_id": paper_id,
            "hypotheses": [h.to_dict() for h in hypotheses],
            "count": len(hypotheses),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        output_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        logger.info("[HYP] Hipóteses salvas em: %s", output_path)
        return output_path

    def validate_hypotheses(self, hypotheses: List[Hypothesis]) -> List[bool]:
        """Valida schema de cada hipótese."""
        from iaglobal.validation.engine import FeedbackEngine

        validator = FeedbackEngine()
        results = []

        for hyp in hypotheses:
            hyp_dict = hyp.to_dict()
            required_keys = {"description", "method", "success_criteria"}

            # Validação manual de schema
            has_required = required_keys.issubset(hyp_dict.keys())
            method_valid = hyp_dict.get("method") in [
                "experiment",
                "data_analysis",
                "simulation",
            ]
            description_non_empty = len(hyp_dict.get("description", "")) > 10

            is_valid = has_required and method_valid and description_non_empty

            # Se FeedbackEngine tiver validate_hypothesis, usar
            if hasattr(validator, "validate_hypothesis"):
                is_valid = is_valid and validator.validate_hypothesis(hyp_dict)

            results.append(is_valid)
            logger.debug("[HYP] %s: %s", hyp.id, "válida" if is_valid else "inválida")

        return results


# Funções utilitárias
async def generate_hypotheses_for_paper(paper: PaperMetadata) -> List[Hypothesis]:
    """
    Gera hipóteses para um paper.

    Args:
        paper: PaperMetadata

    Returns:
        Lista de 3 Hypothesis
    """
    generator = HypothesisGenerator()
    hypotheses = await generator.generate(paper)
    generator.save_hypotheses(hypotheses, paper.paper_id)
    return hypotheses


def validate_hypothesis_schema(hypothesis: Dict[str, Any]) -> bool:
    """Valida schema de uma hipótese."""
    required = {"id", "description", "method", "expected_outcome", "success_criteria"}
    if not required.issubset(hypothesis.keys()):
        return False

    if hypothesis.get("method") not in ["experiment", "data_analysis", "simulation"]:
        return False

    if len(hypothesis.get("description", "")) < 10:
        return False

    if len(hypothesis.get("success_criteria", "")) < 5:
        return False

    return True
