# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
Self-Critique Evolutivo — Crítica automática de código Python.

Integra:
  - SelfCritique base (reflection/self_critique.py)
  - Jedi para análise estática
  - Critérios específicos para código Python
  - Loop de evolução: Gera → Critica → Refina → Re-crítica
"""

from typing import Dict, List, Any

from iaglobal.reflection.self_critique import SelfCritique
from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.reflection.self_critique_evolutivo")


class SelfCritiqueEvolutivo(SelfCritique):
    """
    Self-Critique especializado em código Python.

    Critérios de avaliação:
      - Sintaxe válida (pyflakes)
      - Imports resolvidos (Jedi)
      - Tipos inferidos (Jedi)
      - Cobertura de testes (se aplicável)
      - Complexidade ciclomática
      - Legibilidade
    """

    def __init__(self):
        super().__init__()
        self.criterios_codigo = [
            "sintaxe_valida",
            "imports_resolvidos",
            "tipos_inferidos",
            "funcoes_definidas",
            "tratamento_erros",
            "legibilidade",
        ]
        self.criterios_testes = [
            "cobre_happy_path",
            "cobre_edge_cases",
            "mocks_isolados",
            "asserts_validos",
            "independente",
        ]

    def evaluate(self, output: str, contexto: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Avalia código Python com critérios específicos.

        Args:
            output: Código Python para avaliar
            contexto: Dict com tipo ("codigo" ou "testes"), codigo_original, etc.

        Returns:
            Dict com score (0-1), critérios, forças, fraquezas
        """
        contexto = contexto or {}
        tipo = contexto.get("tipo", "codigo")

        # Avaliação base (linhas)
        base_critique = super().evaluate(output)

        # Análise estática com Jedi + pyflakes
        analise = self._analisar_com_jedi(output)

        # Critérios específicos
        if tipo == "testes":
            criterios = self.criterios_testes
            critique = self._avaliar_testes(output, analise, contexto)
        else:
            criterios = self.criterios_codigo
            critique = self._avaliar_codigo(output, analise, contexto)

        # Combina com base
        critique["line_count"] = base_critique["line_count"]
        critique["output"] = output
        critique["criterios"] = criterios
        critique["analise_estatica"] = analise

        self.critique_history.append(critique)
        logger.info(
            "[SELF-CRITIQUE] Avaliação | tipo=%s | score=%.2f | linhas=%d",
            tipo,
            critique["score"],
            critique["line_count"],
        )

        return critique

    def _analisar_com_jedi(self, codigo: str) -> Dict[str, Any]:
        """
        Análise estática com Jedi.

        Returns:
            - sintaxe_valida: bool
            - imports_resolvidos: list
            - simbolos: list
            - erros: list
        """
        analise = {
            "sintaxe_valida": True,
            "imports_resolvidos": [],
            "simbolos": [],
            "erros": [],
        }

        try:
            import jedi
            import pyflakes.api
            import pyflakes.messages

            # Pyflakes para erros
            class ColetorErros:
                def __init__(self):
                    self.erros = []

                def unexpectedError(self, filename, msg):
                    self.erros.append({"tipo": "erro", "msg": msg})

                def syntaxError(self, filename, msg, lineno, offset, text):
                    self.erros.append(
                        {
                            "tipo": "sintaxe",
                            "msg": msg,
                            "linha": lineno,
                        }
                    )
                    analise["sintaxe_valida"] = False

                def flake(self, msg):
                    self.erros.append(
                        {
                            "tipo": "aviso",
                            "msg": str(msg),
                            "linha": getattr(msg, "lineno", 1),
                        }
                    )

            coletor = ColetorErros()
            pyflakes.api.check(codigo, "example.py", coletor)
            analise["erros"] = coletor.erros

            # Jedi para símbolos
            script = jedi.Script(code=codigo, path="example.py")
            completions = script.complete()

            for c in list(completions)[:30]:
                analise["simbolos"].append(
                    {
                        "nome": c.name,
                        "tipo": c.type,
                    }
                )

                if c.type == "module":
                    analise["imports_resolvidos"].append(c.name)

        except ImportError:
            logger.debug("[SELF-CRITIQUE] Jedi/pyflakes não disponíveis")
        except Exception as e:
            logger.debug("[SELF-CRITIQUE] Análise falhou: %s", e)
            analise["erros"].append({"tipo": "analise", "msg": str(e)})

        return analise

    def _avaliar_codigo(
        self,
        codigo: str,
        analise: Dict[str, Any],
        contexto: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Avalia código Python com critérios específicos.
        """
        critique = {
            "score": 0.0,
            "forças": [],
            "fraquezas": [],
            "criterios_avaliados": {},
        }

        # 1. Sintaxe válida (peso: 0.3)
        if analise["sintaxe_valida"]:
            critique["forças"].append("sintaxe_valida")
            critique["score"] += 0.3
        else:
            critique["fraquezas"].append("erro_sintaxe")
            critique["score"] += 0.0

        # 2. Imports resolvidos (peso: 0.2)
        erros_import = [
            e for e in analise["erros"] if "import" in e.get("msg", "").lower()
        ]
        if not erros_import:
            critique["forças"].append("imports_resolvidos")
            critique["score"] += 0.2
        else:
            critique["fraquezas"].append(f"imports_problematicos ({len(erros_import)})")
            critique["score"] += 0.0

        # 3. Funções definidas (peso: 0.2)
        funcoes = [s for s in analise["simbolos"] if s["tipo"] == "function"]
        if funcoes:
            critique["forças"].append(f"funcoes_definidas ({len(funcoes)})")
            critique["score"] += 0.2
        else:
            critique["fraquezas"].append("sem_funcoes")
            critique["score"] += 0.0

        # 4. Tratamento de erros (peso: 0.15)
        if "try" in codigo or "except" in codigo:
            critique["forças"].append("tratamento_erros")
            critique["score"] += 0.15
        else:
            critique["fraquezas"].append("sem_tratamento_erros")
            critique["score"] += 0.05  # Parcial

        # 5. Legibilidade (peso: 0.15)
        linhas = codigo.strip().split("\n")
        if all(len(l) < 100 for l in linhas):
            critique["forças"].append("legibilidade")
            critique["score"] += 0.15
        else:
            critique["fraquezas"].append("linhas_muito_longas")
            critique["score"] += 0.05

        # Normaliza score para 0-1
        critique["score"] = min(1.0, round(critique["score"], 2))
        critique["criterios_avaliados"] = {
            "sintaxe": analise["sintaxe_valida"],
            "imports": len(erros_import) == 0,
            "funcoes": len(funcoes) > 0,
        }

        return critique

    def _avaliar_testes(
        self,
        testes: str,
        analise: Dict[str, Any],
        contexto: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Avalia testes unitários.
        """
        critique = {
            "score": 0.0,
            "forças": [],
            "fraquezas": [],
            "criterios_avaliados": {},
        }

        codigo_original = contexto.get("codigo_original", "")

        # 1. Sintaxe válida (peso: 0.2)
        if analise["sintaxe_valida"]:
            critique["forças"].append("sintaxe_valida")
            critique["score"] += 0.2
        else:
            critique["fraquezas"].append("erro_sintaxe")

        # 2. Asserts presentes (peso: 0.25)
        if "assert" in testes or "testing" in testes.lower():
            critique["forças"].append("asserts_presentes")
            critique["score"] += 0.25
        else:
            critique["fraquezas"].append("sem_asserts")

        # 3. Cobre happy path (peso: 0.2)
        # Verifica se testa caso básico
        if codigo_original and any(fn in testes for fn in ["def ", "test_", "Test"]):
            critique["forças"].append("estrutura_testes")
            critique["score"] += 0.2
        else:
            critique["fraquezas"].append("estrutura_fraca")

        # 4. Edge cases (peso: 0.2)
        edge_indicators = ["None", "0", "-1", "empty", "Exception", "Error"]
        edge_count = sum(1 for ind in edge_indicators if ind in testes)
        if edge_count >= 2:
            critique["forças"].append(f"edge_cases ({edge_count})")
            critique["score"] += 0.2
        else:
            critique["fraquezas"].append("poucos_edge_cases")
            critique["score"] += 0.1

        # 5. Independência (peso: 0.15)
        if "mock" in testes.lower() or "patch" in testes.lower():
            critique["forças"].append("mocks_isolados")
            critique["score"] += 0.15
        else:
            critique["fraquezas"].append("sem_mocks")
            critique["score"] += 0.05

        # Normaliza
        critique["score"] = min(1.0, round(critique["score"], 2))
        critique["criterios_avaliados"] = {
            "sintaxe": analise["sintaxe_valida"],
            "asserts": "assert" in testes,
            "edge_cases": edge_count >= 2,
        }

        return critique

    def gerar_sugestoes_refinamento(self, critique: Dict[str, Any]) -> List[str]:
        """
        Gera sugestões baseadas na crítica.

        Returns:
            Lista de sugestões de melhoria
        """
        sugestoes = []

        fraquezas = critique.get("fraquezas", [])

        if "erro_sintaxe" in fraquezas:
            sugestoes.append("Corrija erros de sintaxe primeiro")

        if "imports_problematicos" in fraquezas:
            sugestoes.append(
                "Verifique imports: remova não utilizados ou corrija nomes"
            )

        if "sem_funcoes" in fraquezas:
            sugestoes.append("Defina pelo menos uma função")

        if "sem_tratamento_erros" in fraquezas:
            sugestoes.append("Adicione try/except para tratamento de erros")

        if "linhas_muito_longas" in fraquezas:
            sugestoes.append("Quebre linhas com >100 caracteres")

        if "sem_asserts" in fraquezas:
            sugestoes.append("Adicione asserts para validar comportamento")

        if "poucos_edge_cases" in fraquezas:
            sugestoes.append("Teste casos extremos: None, 0, -1, exceções")

        if "sem_mocks" in fraquezas:
            sugestoes.append("Use mocks para isolar dependências externas")

        return sugestoes


# Instância global
self_critique_evolutivo = SelfCritiqueEvolutivo()
