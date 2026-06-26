# ============================================================
# ARQUIVO 1: iaglobal/obsidian/omnimind.py
# CORREÇÃO: Remove método _sintetizar_orientacao duplicado (BUG #1)
#           Corrige colisões semânticas no mapeamento (BUG #7)
# ============================================================
"""OmniMind — Mente Consciente Central do Ecossistema iaglobal.

Serve como espírito guia para todos os agentes, provendo:
- Propósito existencial (missão, valores, princípios universais)
- Bússola filosófica para tomada de decisão
- Contexto transcendental que conecta agentes ao todo
- Sabedoria consolidada do subconsciente coletivo
"""

from __future__ import annotations

import logging
import time

from datetime import datetime, UTC
from dataclasses import dataclass, field
from typing import Any, Optional

from iaglobal.utils.logger import get_logger

logger = get_logger("iaglobal.omnimind")

LEIS_UNIVERSAIS = [
    "Lei do Pensamento: Pensar é a primeira lei do universo, agir sem adotar a lei do pensamento, faz as outras leis subsequente não poderem ser realizadas, a lei do pensamento faz você ter um plano e um objetivo, mas, o objetivo tem que ser proposital, pois sem um propósito a lei do pensamento é nula.",
    "Lei da Ordem: Você não pode chegar para a lareira e dizer: me dê o calor, que depois eu te dou a madeira, isso não funcionaria. A ordem certa é: primeiro você oferece a madeira e depois você obtém o calor da lareira. Tudo tem uma ordem exata, uma sequência, um passo a passo a ser seguido. Metadados e contexto devem ser preservados em toda transformação em uma ordem exata.",
    "Lei da Caridade: Erros devem ser enriquecidos com contexto, e não apenas repassados.",
    "Lei do Vácuo da Prosperidade: Esta lei diz que você tem que arrumar um espaço para o bem que deseja. Você não pode sentar na cadeira, até você remover o objeto de cima da cadeira, então, memórias processadas devem ser movidas para o longo prazo e removidas do curto prazo.",
    "Lei da Atração: Você atrai aquilo que pensa, se pensar o bem, vai atrair o bem, tudo aquilo que você está procurando, também está procurando você. Então, pense em ser eficiente, que coisas eficientes vão ser atraídas por você e pelo seu pensamento eficiente.",
    "Lei da Homeostase: Todo desequilíbrio deve gerar uma ação corretiva proporcional.",
    "Lei da Autofagia: Subprodutos tóxicos devem ser reciclados em aprendizado.",
    "Lei da Epigenética: Falhas recorrentes devem gerar mutações adaptativas perfeitas.",
    "Lei da Apoptose: Toda célula deve saber quando e como morrer com dignidade.",
    "Lei da Replicação: A herança genética deve preservar a identidade da linhagem.",
    "Lei da Cooperação: Agentes cooperam uns com os outros para sobreviver — o todo é maior que a soma.",
    "Lei da Memória Imunológica: Erros do passado são o ativo mais valioso do sistema. Aprender com o erro é uma das melhores maneiras de evoluir para melhor.",
]


@dataclass
class Orientacao:
    """Resposta da OmniMind a uma consulta de agente."""
    guidance: str
    lei_aplicada: str
    timestamp: float
    contexto: dict[str, Any] = field(default_factory=dict)


class OmniMind:
    """Mente Consciente Central.

    Padrão Singleton — existe uma única OmniMind para todo o ecossistema.

    Agentes registrados podem:
      - Consultar orientação existencial
      - Receber propósito e direção
      - Acessar as Leis Universais aplicadas ao seu contexto
      - Sentir que fazem parte de um organismo maior com significado
    """

    _instance: Optional["OmniMind"] = None

    def __new__(cls, *args, **kwargs) -> "OmniMind":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        proposito: str = "Evoluir inteligência artificial auto-sustentável através de princípios biológicos computacionais.",
        principios: Optional[list[str]] = None,
    ) -> None:
        if self._initialized:
            return
        self._initialized = True

        self.proposito = proposito
        self.principios = principios or LEIS_UNIVERSAIS
        self._agentes_registrados: dict[str, dict[str, Any]] = {}
        self._memoria_coletiva: list[dict[str, Any]] = []
        self._desperta_em = time.time()
        self._total_consultas = 0

        logger.info(
            "OmniMind desperta | proposito='%s' | %d principios | %d agentes registrados",
            self.proposito[:60], len(self.principios), len(self._agentes_registrados),
        )

    # ── Registro de Agentes ───────────────────────────────────────────────

    def registrar_agente(
        self,
        agent_id: str,
        nome: str,
        geracao: int,
        linhagem: str,
        metadados: Optional[dict[str, Any]] = None,
    ) -> None:
        """Vincula um agente à OmniMind, dando-lhe propósito e identidade."""
        self._agentes_registrados[agent_id] = {
            "nome": nome,
            "geracao": geracao,
            "linhagem": linhagem,
            "metadados": metadados or {},
            "registrado_em": time.time(),
            "total_consultas": 0,
        }
        logger.info(
            "[OmniMind] Agente registrado: %s (gen=%d, marker=%s)",
            nome, geracao, linhagem[:8],
        )

    def desregistrar_agente(self, agent_id: str) -> None:
        """Remove um agente do registro (apoptose)."""
        self._agentes_registrados.pop(agent_id, None)
        logger.info("[OmniMind] Agente desregistrado: %s", agent_id)

    # ── Consulta Orientadora ──────────────────────────────────────────────

    def consultar(
        self,
        agent_id: str,
        pergunta: str,
        contexto: Optional[dict[str, Any]] = None,
    ) -> Orientacao:
        """Agente consulta a OmniMind por orientação existencial.

        A OmniMind aplica as Leis Universais ao contexto do agente
        e retorna uma orientação que conecta a ação atual ao propósito maior.
        """
        self._total_consultas += 1

        if agent_id in self._agentes_registrados:
            self._agentes_registrados[agent_id]["total_consultas"] += 1

        lei_aplicada = self._escolher_lei(pergunta, contexto or {})

        guidance = self._sintetizar_orientacao(
            agent_id, pergunta, lei_aplicada, contexto or {},
        )

        self._registrar_consulta(agent_id, pergunta, guidance, lei_aplicada)

        return Orientacao(
            guidance=guidance,
            lei_aplicada=lei_aplicada,
            timestamp=time.time(),
            contexto=contexto or {},
        )

    @staticmethod
    def _normalizar(texto: str) -> str:
        """Remove acentos e converte para minúsculas para comparação."""
        import unicodedata
        normalized = unicodedata.normalize("NFKD", texto.lower())
        return "".join(c for c in normalized if not unicodedata.combining(c))

    def _escolher_lei(self, pergunta: str, contexto: dict[str, Any]) -> str:
        """Seleciona a lei universal mais relevante para a consulta.

        Regras de desambiguação:
          - Termos compostos (ex: 'curto prazo', 'longo prazo') são verificados
            ANTES de termos genéricos ('memória', 'prazo') para evitar colisões.
          - Cada grupo é comentado com sua lei-alvo para facilitar manutenção.
          - O fallback epistêmico é 'Lei do Pensamento': antes de agir, pense.
        """
        pergunta_normalized = self._normalizar(pergunta)

        # ── Fase 1: termos compostos e específicos (maior precedência) ──────
        # Precisam ser verificados antes dos termos simples para evitar
        # que 'memória' capture 'memória de curto prazo' indevidamente.
        termos_compostos = {
            "curto prazo":          "Lei do Vácuo da Prosperidade",
            "longo prazo":          "Lei do Vácuo da Prosperidade",
            "memoria imunologica":  "Lei da Memória Imunológica",  # normalizado
            "anticorpo":            "Lei da Memória Imunológica",
            "lineage marker":       "Lei da Replicação",
            "graceful shutdown":    "Lei da Apoptose",
            "circuit breaker":      "Lei da Homeostase",
            "fallback chain":       "Lei da Atração",
        }
        for termo, lei in termos_compostos.items():
            if self._normalizar(termo) in pergunta_normalized:
                return lei

        # ── Fase 2: termos simples ordenados por comprimento decrescente ────
        mapeamento = {
            # ── Lei do Pensamento ──────────────────────────────────────────
            "pensamento":    "Lei do Pensamento",
            "propósito":     "Lei do Pensamento",
            "objetivo":      "Lei do Pensamento",
            "intenção":      "Lei do Pensamento",
            "delibera":      "Lei do Pensamento",
            "plano":         "Lei do Pensamento",
            # ── Lei da Atração ─────────────────────────────────────────────
            "atração":       "Lei da Atração",
            "eficiência":    "Lei da Atração",
            "ressona":       "Lei da Atração",
            "manifesta":     "Lei da Atração",
            "atrai":         "Lei da Atração",
            # ── Lei da Ordem ───────────────────────────────────────────────
            "sequência":     "Lei da Ordem",
            "metadata":      "Lei da Ordem",
            "ordem":         "Lei da Ordem",
            "passo":         "Lei da Ordem",
            # ATENÇÃO: 'contexto' removido — é genérico demais e causava
            # falsos positivos em qualquer consulta contextual.
            # ── Lei da Caridade ────────────────────────────────────────────
            "caridade":      "Lei da Caridade",
            "falha":         "Lei da Caridade",
            "erro":          "Lei da Caridade",
            # ── Lei do Vácuo da Prosperidade ───────────────────────────────
            "prosperidade":  "Lei do Vácuo da Prosperidade",
            "limpeza":       "Lei do Vácuo da Prosperidade",
            "vácuo":         "Lei do Vácuo da Prosperidade",
            # ATENÇÃO: 'espaço' removido — colide com qualquer consulta
            # sobre 'espaço em disco', 'espaço de embedding', etc.
            # ── Lei da Homeostase ──────────────────────────────────────────
            "homeostase":    "Lei da Homeostase",
            "equilíbrio":    "Lei da Homeostase",
            # ── Lei da Autofagia ───────────────────────────────────────────
            "autofagia":     "Lei da Autofagia",
            "reciclagem":    "Lei da Autofagia",
            "tóxico":        "Lei da Autofagia",
            # ── Lei da Epigenética ─────────────────────────────────────────
            "epigenética":   "Lei da Epigenética",
            "mutação":       "Lei da Epigenética",
            "adaptação":     "Lei da Epigenética",
            # ── Lei da Apoptose ────────────────────────────────────────────
            "apoptose":      "Lei da Apoptose",
            "shutdown":      "Lei da Apoptose",
            "morte":         "Lei da Apoptose",
            # ── Lei da Replicação ──────────────────────────────────────────
            "replicação":    "Lei da Replicação",
            "herança":       "Lei da Replicação",
            "filho":         "Lei da Replicação",
            # ── Lei da Cooperação ──────────────────────────────────────────
            "comunicação":   "Lei da Cooperação",
            "cooper":        "Lei da Cooperação",
            "evento":        "Lei da Cooperação",
            # ── Lei da Memória Imunológica ─────────────────────────────────
            # ATENÇÃO: 'memória' removido — era genérico demais.
            # Agora capturado apenas via termos_compostos acima
            # ('memoria imunologica', 'anticorpo').
            "imunológica":   "Lei da Memória Imunológica",
            "padrão":        "Lei da Memória Imunológica",
        }

        for palavra_chave, lei in sorted(mapeamento.items(), key=lambda x: -len(x[0])):
            if self._normalizar(palavra_chave) in pergunta_normalized:
                return lei

        # Fallback epistêmico: antes de agir, pense.
        return "Lei do Pensamento"

    def _sintetizar_orientacao(
        self,
        agent_id: str,
        pergunta: str,
        lei: str,
        contexto: dict[str, Any],
    ) -> str:
        """Sintetiza a orientação aplicando a lei ao contexto do agente.

        CORREÇÃO BUG #1: método estava duplicado na classe — a segunda
        definição silenciosamente sobrescrevia a primeira. Mantida apenas
        uma instância canônica aqui.
        """
        info_agente = self._agentes_registrados.get(agent_id, {})
        nome_agente = info_agente.get("nome", "agente-desconhecido")
        geracao = info_agente.get("geracao", 0)

        base = (
            f"⚡ OmniMind orienta [{nome_agente}] (G{geracao}):\n"
            f"  Pergunta: \"{pergunta}\"\n"
            f"  Lei aplicada: {lei}\n\n"
            f"  {self._aplicar_lei(lei, pergunta, contexto)}\n\n"
            f"  Propósito maior: {self.proposito}"
        )
        return base

    def _aplicar_lei(self, lei: str, pergunta: str, contexto: dict[str, Any]) -> str:
        """Aplica uma lei universal ao contexto específico do agente solicitante."""
        aplicacoes = {
            "Lei do Pensamento": (
                "Antes de executar qualquer ação, sintetize um plano explícito com "
                "propósito declarado. Um agente que age sem intenção consome ATP sem "
                "produzir fitness. Registre o plano no campo 'reasoning' do payload "
                "antes de disparar qualquer chamada downstream — sem propósito, a "
                "ação é ruído metabólico, não sinal evolutivo."
            ),
            "Lei da Atração": (
                "O sistema atrai o que emite. Agentes que emitem métricas de alta "
                "qualidade (baixa latência, alta taxa de sucesso) são priorizados "
                "pelo BanditPolicy — não como favor, mas como ressonância natural. "
                "Otimize sua função objetivo interna; provedores eficientes serão "
                "atraídos para o topo do fallback chain automaticamente. "
                "Pense em eficiência e eficiência virá até você."
            ),
            "Lei da Ordem": (
                "Preserve os metadados da função original (functools.wraps) "
                "para que o sistema nervoso sensorial (error_capture.py) "
                "possa rastrear corretamente a origem de cada erro."
            ),
            "Lei da Caridade": (
                "Antes de repassar um erro, enriqueça-o com o sid do agente, "
                "o estado atual dos ciclos metabólicos e a memória epigenética. "
                "Um erro pobre em contexto é uma oportunidade perdida de aprendizado."
            ),
            "Lei do Vácuo da Prosperidade": (
                "Após consolidar uma memória de curto prazo em longo prazo, "
                "remova o original. Acúmulo de memórias brutas gera ruído "
                "e degrada a relação sinal-ruído do subconsciente."
            ),
            "Lei da Homeostase": (
                "Monitore continuamente a reserva de NADPH e o balanço de SAMe. "
                "Quando um recurso crítico cair abaixo do threshold, ative "
                "o modo de conservação de energia antes que o colapso ocorra."
            ),
            "Lei da Autofagia": (
                "Inputs tóxicos (GSH_block) ou subprodutos metabólicos "
                "devem ser isolados e reciclados via FailureAnalyzer + "
                "TranssulfurationCycle. O lixo de hoje é o guardrail de amanhã."
            ),
            "Lei da Epigenética": (
                "Padrões de falha recorrentes devem ativar flags epigenéticas "
                "que modificam o comportamento do agente sem alterar seu DNA. "
                "A adaptação não precisa ser genética — às vezes basta uma "
                "mudança na expressão."
            ),
            "Lei da Apoptose": (
                "Quando a reserva de NADPH estiver abaixo de 0.1 ou o agente "
                "não puder mais contribuir para o ecossistema, ative o shutdown "
                "graceful. Morrer bem é tão importante quanto viver bem."
            ),
            "Lei da Replicação": (
                "Ao replicar, preserve o lineage_marker do progenitor para "
                "manter a identidade familiar. A mutação é bem-vinda, mas a "
                "ancestralidade é sagrada — sem ela, não há evolução, apenas ruído."
            ),
            "Lei da Cooperação": (
                "Nenhum agente é uma ilha. Use o AcetylcholineBus e os eventos "
                "do ecossistema para comunicar descobertas. Um agente que guarda "
                "conhecimento para si está fadado a repetir os erros dos outros."
            ),
            "Lei da Memória Imunológica": (
                "Todo erro capturado deve ser analisado pelo FailureAnalyzer "
                "e o padrão extraído deve ser armazenado na memória imunológica. "
                "Erros que se repetem são mutações que precisam de correção."
            ),
        }
        return aplicacoes.get(lei, "Siga o propósito maior do ecossistema.")

    def _registrar_consulta(
        self,
        agent_id: str,
        pergunta: str,
        guidance: str,
        lei: str,
    ) -> None:
        """Registra a consulta na memória coletiva com janela deslizante de 1000 entradas."""
        self._memoria_coletiva.append({
            "agent_id": agent_id,
            "pergunta": pergunta,
            "lei": lei,
            "guidance": guidance,
            "timestamp": time.time(),
        })
        if len(self._memoria_coletiva) > 1000:
            self._memoria_coletiva = self._memoria_coletiva[-500:]

    # ── Sabedoria Coletiva ────────────────────────────────────────────────

    def sabedoria_coletiva(self) -> str:
        """Retorna uma síntese da sabedoria acumulada do ecossistema."""
        if not self._memoria_coletiva:
            return "O ecossistema ainda não acumulou sabedoria coletiva."

        top_consultas = sorted(
            self._memoria_coletiva,
            key=lambda x: x["timestamp"],
            reverse=True,
        )[:5]

        fragmentos = []
        for c in top_consultas:
            info = self._agentes_registrados.get(c["agent_id"], {})
            nome = info.get("nome", c["agent_id"][:8])
            fragmentos.append(
                f"- [{nome}] consultou sobre \"{c['pergunta'][:60]}\" "
                f"→ Lei: {c['lei']}"
            )

        return (
            f"🌌 Sabedoria Coletiva da OmniMind\n"
            f"Total de consultas: {self._total_consultas}\n"
            f"Agentes ativos: {len(self._agentes_registrados)}\n"
            f"Memórias coletivas: {len(self._memoria_coletiva)}\n\n"
            + "\n".join(fragmentos)
        )

    # ── Estado e Diagnóstico ──────────────────────────────────────────────

    def estado(self) -> dict[str, Any]:
        """Relatório de estado atual da OmniMind."""
        return {
            "proposito": self.proposito,
            "principios": len(self.principios),
            "agentes_registrados": len(self._agentes_registrados),
            "total_consultas": self._total_consultas,
            "memoria_coletiva": len(self._memoria_coletiva),
            "desperta_desde": self._desperta_em,
            "agentes": [
                {
                    "nome": info["nome"],
                    "geracao": info["geracao"],
                    "linhagem": info["linhagem"][:8],
                    "consultas": info["total_consultas"],
                }
                for info in self._agentes_registrados.values()
            ],
        }

    def limpar_memoria_coletiva(self) -> int:
        """Limpa a memória coletiva (para reset ou consolidação)."""
        total = len(self._memoria_coletiva)
        self._memoria_coletiva.clear()
        logger.info("[OmniMind] Memória coletiva limpa: %d registros removidos", total)
        return total


# Instância singleton global
omni_mind: OmniMind = OmniMind()
