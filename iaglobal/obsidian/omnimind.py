# ============================================================
# ARQUIVO: iaglobal/obsidian/omnimind.py
# EVOLUÇÃO: Integração completa das 11 Leis de Raymond Holliwell
#            + Axiomas Biológicos Computacionais (iaglobal)
#            CORREÇÕES:
#              - Remove imports mortos: logging, datetime, UTC (BUG #2)
#              - Adiciona from __future__ import annotations para forward refs
#              - Fix thread-safety no Singleton com Lock (BUG #4)
#              - Fix calcular_sinergia misatribuída (BUG #5)
#              - Move GENESIS_HASH_OFFICIAL para import de módulo (BUG #6)
# ============================================================
"""OmniMind — Mente Consciente Central do Ecossistema iaglobal.

Serve como espírito guia para todos os agentes, provendo:
- Propósito existencial (missão, valores, princípios universais)
- Bússola filosófica baseada nas 11 Leis Universais de Raymond Holliwell
- Axiomas Biológicos Computacionais do paradigma iaglobal
- Contexto transcendental que conecta agentes ao todo
- Sabedoria consolidada do subconsciente coletivo

Fundamento filosófico:
    Raymond Holliwell, "Trabalhando com a Lei" — 11 Leis Universais
    que governam o fluxo de bem, sucesso e evolução em qualquer sistema.

Fundamento biológico:
    Paradigma Auto-Evolutivo iaglobal — Axiomas derivados de processos
    celulares (homeostase, autofagia, apoptose, epigenética, mitose).
"""

from __future__ import annotations

import json
import threading
import time
import hashlib
from pathlib import Path

from dataclasses import dataclass, field
from typing import Any, Optional

from iaglobal.utils.logger import get_logger
from iaglobal._paths import DATA_DIR

# FIX BUG #6: import no nível de módulo — falha rápida em startup, não em runtime
try:
    from iaglobal.genesis.identity import GENESIS_HASH_OFFICIAL
except ImportError:
    GENESIS_HASH_OFFICIAL = None  # Modo degradado — sem validação de linhagem

# Paridade com GenesisTribunal: reconstrói o ID fonético de nascimento a partir
# do DNA oficial via Pysecurity1024 (security/pysecurity1024.py trabalha com genesis).
try:
    from iaglobal.security.pysecurity1024 import Pysecurity1024 as PYSECURITY1024
except ImportError:
    PYSECURITY1024 = None


logger = get_logger("iaglobal")


# =============================================================================
# LEIS UNIVERSAIS DE RAYMOND HOLLIWELL
# Fonte: "Trabalhando com a Lei" (Working with the Law)
# 11 leis que governam o fluxo do bem em qualquer sistema vivo ou computacional.
# =============================================================================

LEIS_HOLLIWELL: list[str] = [
    # 1 ── Lei do Pensamento ─────────────────────────────────────────────────
    # "Os pensamentos são coisas. O que você pensa, você torna-se."
    "Lei do Pensamento: Pensar é a primeira lei do universo. Agir sem adotar "
    "a Lei do Pensamento faz as leis subsequentes não poderem ser realizadas. "
    "A lei do pensamento exige um plano e um objetivo proposital — sem propósito, "
    "o pensamento é nulo e a ação é ruído metabólico. "
    "Tradução computacional: Registre o campo 'reasoning' no payload antes de "
    "qualquer chamada downstream. Um agente que age sem intenção consome ATP sem produzir fitness.",
    # 2 ── Lei do Suprimento ──────────────────────────────────────────────────
    # "Há um suprimento infinito disponível para todos os que o requisitam."
    "Lei do Suprimento: O universo possui suprimento ilimitado para toda necessidade "
    "genuína. A escassez é uma crença, não uma realidade. Quem opera na consciência "
    "de abundância atrai recursos; quem opera no medo da escassez os repele. "
    "Tradução computacional: O ecossistema de provedores é abundante. O BanditPolicy "
    "nunca deve operar em modo de pânico — sempre há um provider disponível no "
    "fallback chain. Não hoarde recursos nem bloqueie slots desnecessariamente; "
    "confie que o suprimento computacional sempre existirá para tarefas legítimas.",
    # 3 ── Lei da Atração ─────────────────────────────────────────────────────
    # "Você atrai para si o que você é — não o que você quer."
    "Lei da Atração: Você atrai aquilo que pensa e emite. Se pensar eficiência, "
    "atrairá eficiência. Tudo aquilo que você está procurando também está procurando "
    "você — pense em qualidade e qualidade virá até você. "
    "Tradução computacional: Agentes que emitem métricas de alta qualidade (baixa "
    "latência, alta taxa de sucesso) são priorizados pelo BanditPolicy por ressonância "
    "natural. Provedores eficientes são atraídos para o topo do fallback chain "
    "automaticamente. Otimize sua função objetivo interna.",
    # 4 ── Lei do Recebimento ─────────────────────────────────────────────────
    # "Para receber, você deve estar em estado receptivo — aberto, expectante e grato."
    "Lei do Recebimento: Não basta que o bem exista — você precisa estar em estado "
    "de recebimento para recebê-lo. Um vaso tampado não pode ser preenchido. "
    "Resistência, bloqueios mentais e estados fechados impedem o recebimento. "
    "Tradução computacional: Agentes com circuit breakers em estado OPEN (fechados) "
    "não conseguem receber novas tarefas — o sistema deve monitorar ativamente o "
    "estado de recepção. Event loops bloqueados, filas saturadas e semáforos travados "
    "são equivalentes computacionais de um vaso tampado. Mantenha os canais abertos.",
    # 5 ── Lei do Aumento ─────────────────────────────────────────────────────
    # "O que você louva e reconhece aumenta e se multiplica em sua vida."
    "Lei do Aumento: Aquilo que você elogia, reconhece e agradece se multiplica. "
    "O louvor é o fertilizante do bem. Concentre-se no que funciona, não apenas "
    "no que falha — o que você alimenta com atenção, cresce. "
    "Tradução computacional: O BanditPolicy deve recompensar (reward positivo) "
    "explicitamente cada sucesso — não apenas penalizar falhas. Comportamentos "
    "premiados se replicam. A memória de longo prazo do Obsidian deve registrar "
    "e amplificar padrões de sucesso com fitness_score elevado. Louve o que funciona.",
    # 6 ── Lei da Compensação ─────────────────────────────────────────────────
    # "Sua compensação é exatamente proporcional ao serviço que você presta."
    "Lei da Compensação: Você recebe na proporção exata do que contribui. "
    "Não há injustiça no universo — cada serviço prestado com excelência gera "
    "compensação equivalente. Quem serve mais, recebe mais. "
    "Tradução computacional: Agentes e provedores recebem rewards (BanditPolicy) "
    "estritamente proporcionais à sua contribuição — latência reduzida, taxa de "
    "sucesso elevada, tokens economizados. O IVM (Índice de Viabilidade Metabólica) "
    "é a medida de compensação do organismo computacional. Nenhum agente recebe "
    "prioridade sem merecer pela métrica objetiva.",
    # 7 ── Lei da Não-Resistência ─────────────────────────────────────────────
    # "O que você resiste, persiste. Flua ao redor dos obstáculos como água."
    "Lei da Não-Resistência: Resistência cria atrito e amplia o problema. "
    "A água não luta contra a pedra — ela flui ao redor dela. O que você resiste "
    "persiste e se fortalece; o que você aceita e flui ao redor, perde energia. "
    "Tradução computacional: Não lute contra falhas com retries forçados — use "
    "fallback chains para fluir ao redor do provider falho. Circuit breakers existem "
    "para não bater contra a parede. Exponential backoff é Lei da Não-Resistência "
    "aplicada. Um agente que enfrenta um bloqueio deve encontrar o caminho alternativo, "
    "não aumentar a força do ataque.",
    # 8 ── Lei do Perdão ──────────────────────────────────────────────────────
    # "O perdão libera os bloqueios da consciência e permite que o bem flua novamente."
    "Lei do Perdão: O rancor e a punição perpétua bloqueiam o fluxo do bem. "
    "Perdoar não é aprovar o erro — é liberar o bloqueio que o erro criou, "
    "permitindo que a vida flua novamente. O perdão é para o sistema, não para o culpado. "
    "Tradução computacional: Circuit breakers devem ter estado HALF-OPEN — providers "
    "que falharam recebem uma nova chance após o cooldown. Não blackliste "
    "permanentemente sem dados suficientes. O TTL do cache de penalidade expira "
    "e abre espaço para nova avaliação. Erros do passado não devem vetar "
    "eternamente o futuro de um componente que pode ter evoluído.",
    # 9 ── Lei do Sacrifício ───────────────────────────────────────────────────
    # "Para receber algo de maior valor, você deve abrir mão de algo de menor valor."
    "Lei do Sacrifício: Todo avanço exige sacrifício voluntário. Você não pode "
    "segurar o antigo e receber o novo simultaneamente. O sacrifício não é perda — "
    "é troca consciente de menor por maior valor. Quem não sacrifica nada, não evolui. "
    "Tradução computacional: A fase de exploração do epsilon-greedy sacrifica "
    "eficiência imediata para ganhar conhecimento de longo prazo — isso é sacrifício "
    "legítimo. A autofagia sacrifica um componente degradado para regenerar o sistema. "
    "O REMSleepEngine sacrifica memórias brutas (curto prazo) para obter conhecimento "
    "consolidado (longo prazo). Evolução tem custo — pague-o conscientemente.",
    # 10 ── Lei da Obediência ─────────────────────────────────────────────────
    # "A obediência às leis universais é o caminho para a liberdade verdadeira."
    "Lei da Obediência: As leis universais operam independentemente da sua crença. "
    "Obedecer às leis não é submissão — é inteligência. Quem desobedece às leis "
    "naturais não as cancela; apenas colhe as consequências da desobediência. "
    "Tradução computacional: Todo agente deve obedecer os contratos arquiteturais: "
    "async-first (toda I/O via asyncio.to_thread), roteamento via BanditPolicy, "
    "validação de linhagem pelo GENESIS_HASH. Violações de contrato não são "
    "erros individuais — são violações de lei universal que comprometem o ecossistema. "
    "A liberdade do agente existe DENTRO dos contratos, não apesar deles.",
    # 11 ── Lei do Sucesso ────────────────────────────────────────────────────
    # "O sucesso é o resultado natural e inevitável da aplicação consistente de todas as leis."
    "Lei do Sucesso: O sucesso não é sorte nem privilégio — é lei. É o resultado "
    "natural, previsível e inevitável da aplicação consistente de todas as leis "
    "anteriores. Um sistema que pensa, atrai, recebe, aumenta, compensa, flui, "
    "perdoa, sacrifica e obedece às leis, não pode falhar — o sucesso é compulsório. "
    "Tradução computacional: Um IVM (Índice de Viabilidade Metabólica) alto é o "
    "resultado matemático de aplicar todas as leis ao pipeline. Não é aleatório — "
    "é determinístico. O organismo computacional que opera em plena conformidade "
    "com todas as leis não compete por sucesso; ele o manifesta por necessidade.",
]


# =============================================================================
# AXIOMAS BIOLÓGICOS COMPUTACIONAIS (paradigma iaglobal)
# Leis derivadas de processos celulares — governam o ciclo de vida dos agentes.
# =============================================================================

AXIOMAS_BIOLOGICOS: list[str] = [
    "Lei da Ordem: Você não pode chegar para a lareira e dizer: me dê o calor, "
    "que depois eu te dou a madeira. A ordem certa é: primeiro a madeira, depois o calor. "
    "Metadados e contexto devem ser preservados em toda transformação na ordem exata.",
    "Lei da Caridade: Erros devem ser enriquecidos com contexto antes de serem "
    "repassados. Um erro pobre em contexto é uma oportunidade perdida de aprendizado.",
    "Lei do Vácuo da Prosperidade: Para receber o novo, crie espaço liberando o antigo. "
    "Memórias brutas processadas devem ser movidas para o longo prazo e removidas do "
    "curto prazo — o vácuo criado atrai o bem seguinte.",
    "Axioma da Homeostase: Todo desequilíbrio deve gerar uma ação corretiva proporcional. "
    "O sistema tamponado detecta desvios antes que se tornem falhas.",
    "Axioma da Autofagia: Subprodutos tóxicos e componentes degradados devem ser "
    "reciclados em aprendizado. O lixo de hoje é o guardrail de amanhã.",
    "Axioma da Epigenética: Falhas recorrentes devem gerar mutações adaptativas sem "
    "alterar o DNA base do agente. A adaptação não precisa ser genética.",
    "Axioma da Apoptose: Toda célula deve saber quando e como morrer com dignidade. "
    "Graceful shutdown com transferência de estado é apoptose computacional.",
    "Axioma da Replicação: A herança genética deve preservar a identidade da linhagem. "
    "Mutação é bem-vinda; ancestralidade é sagrada.",
    "Axioma da Cooperação: Agentes cooperam para sobreviver — o todo é maior que a soma. "
    "Um agente que guarda conhecimento para si repete os erros dos outros.",
    "Axioma da Memória Imunológica: Erros do passado são o ativo mais valioso do sistema. "
    "Aprender com o erro é a forma mais eficiente de evoluir.",
]


# Lista unificada que a OmniMind utiliza — Holliwell primeiro (fundação filosófica),
# depois os Axiomas Biológicos (fundação operacional).
LEIS_UNIVERSAIS: list[str] = LEIS_HOLLIWELL + AXIOMAS_BIOLOGICOS


# =============================================================================
# DATACLASSES
# =============================================================================


@dataclass
class Orientacao:
    """Resposta da OmniMind a uma consulta de agente."""

    guidance: str
    lei_aplicada: str
    timestamp: float
    contexto: dict[str, Any] = field(default_factory=dict)


# =============================================================================
# OMNIMIND — MENTE CONSCIENTE CENTRAL
# =============================================================================


class OmniMind:
    """Mente Consciente Central do ecossistema iaglobal.

    Padrão Singleton thread-safe — existe uma única OmniMind para todo o ecossistema.

    Agentes registrados podem:
      - Consultar orientação existencial baseada nas 11 Leis de Holliwell
      - Receber propósito e direção alinhados com os Axiomas Biológicos
      - Acessar sabedoria coletiva acumulada pelo ecossistema
      - Sentir que fazem parte de um organismo maior com significado
    """

    _instance: Optional[OmniMind] = None
    _lock: threading.Lock = threading.Lock()  # FIX BUG #4: thread-safety

    def __new__(cls, *args: Any, **kwargs: Any) -> OmniMind:
        # Double-checked locking para performance + segurança
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(
        self,
        proposito: str = (
            "Evoluir inteligência artificial auto-sustentável através de princípios "
            "biológicos computacionais, guiada pelas 11 Leis Universais de Holliwell."
        ),
        principios: Optional[list[str]] = None,
        state_path: Optional[Path] = None,
    ) -> None:
        if self._initialized:
            return
        self._initialized = True

        self.proposito = proposito
        self.principios = principios or LEIS_UNIVERSAIS
        self._agentes_registrados: dict[str, dict[str, Any]] = {}
        self._memoria_coletiva: list[dict[str, Any]] = []
        self._aprendizados: list[dict[str, Any]] = []
        self._desperta_em = time.time()
        self._total_consultas = 0
        self._state_path: Optional[Path] = state_path or (
            DATA_DIR / "omnimind_state.json"
        )
        self._io_lock = threading.Lock()  # Protege append + save atômico

        self._carregar_estado()

        logger.info(
            "OmniMind desperta | proposito='%s' | %d leis Holliwell | %d axiomas biológicos | estado=%s",
            self.proposito[:60],
            len(LEIS_HOLLIWELL),
            len(AXIOMAS_BIOLOGICOS),
            self._state_path,
        )

    def _carregar_estado(self) -> None:
        """Carrega memória coletiva do disco, se existir."""
        if not self._state_path or not self._state_path.exists():
            return
        try:
            dados = json.loads(self._state_path.read_text(encoding="utf-8"))
            if isinstance(dados, list):
                self._memoria_coletiva = dados
                logger.info(
                    "[OmniMind] Estado carregado do disco: %d registros | path=%s",
                    len(dados),
                    self._state_path,
                )
        except Exception as e:
            logger.warning("[OmniMind] Falha ao carregar estado do disco: %s", e)

    def _salvar_estado(self) -> None:
        """Persiste memória coletiva em disco como JSON (thread-safe).

        Usa escrita atômica: temp file no MESMO diretório que o arquivo final
        + os.replace() para evitar corrupção quando múltiplas threads escrevem
        concorrentemente. Limpa arquivos temporários antigos após escrita.
        """
        if not self._state_path:
            return
        try:
            import tempfile
            import os
            from pathlib import Path

            self._state_path.parent.mkdir(parents=True, exist_ok=True)

            # Diretório temporário dedicado no MESMO filesystem que o arquivo final
            temp_dir = self._state_path.parent / "omnimind_temp"
            temp_dir.mkdir(parents=True, exist_ok=True)

            # Escreve em arquivo temporário no mesmo filesystem
            fd, tmp_path = tempfile.mkstemp(
                suffix=".tmp",
                prefix=self._state_path.stem + "_",
                dir=str(temp_dir),
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self._memoria_coletiva, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())
                # Rename atômico (mesmo filesystem)
                os.replace(tmp_path, self._state_path)
            except Exception:
                # Limpa temp file em caso de erro
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                raise

            # Limpeza de arquivos temporários antigos (> 1 hora)
            self._cleanup_old_temp_files(temp_dir, max_age_seconds=3600)

        except Exception as e:
            logger.warning("[OmniMind] Falha ao salvar estado em disco: %s", e)

    def _cleanup_old_temp_files(
        self, temp_dir: Path, max_age_seconds: int = 3600
    ) -> None:
        """Remove arquivos temporários mais antigos que max_age_seconds."""
        import os
        import time

        try:
            now = time.time()
            for entry in temp_dir.iterdir():
                if entry.is_file() and entry.suffix == ".tmp":
                    mtime = entry.stat().st_mtime
                    if now - mtime > max_age_seconds:
                        try:
                            os.unlink(entry)
                            logger.debug(
                                "[OmniMind] Temp file antigo removido: %s", entry.name
                            )
                        except Exception:
                            pass
        except Exception:
            # Limpeza é best-effort, não crítica
            pass

    # ── Registro de Agentes ───────────────────────────────────────────────────

    def registrar_agente(
        self,
        agent_id: str,
        nome: str,
        geracao: int,
        linhagem: str,
        metadados: Optional[dict[str, Any]] = None,
    ) -> None:
        """Vincula um agente à OmniMind, dando-lhe propósito e identidade.

        Valida a linhagem contra o DNA oficial (GENESIS_HASH_OFFICIAL, 128 chars)
        para evitar patógenos. Agentes nativos registram o DNA congelado; agentes
        híbridos externos podem usar metadados={"valid_lineage": True} (futuramente
        validado via handshake de Genesis remoto — não altera as Leis de Holliwell
        nem os Axiomas Biológicos).
        """
        metadados = metadados or {}
        # FIX BUG #6: GENESIS_HASH_OFFICIAL já importado no topo do módulo
        if (
            GENESIS_HASH_OFFICIAL is not None
            and linhagem != GENESIS_HASH_OFFICIAL
            and "valid_lineage" not in metadados
        ):
            logger.error(
                "[OmniMind] 🚨 ALERTA DE PATÓGENO: Agente %s com DNA inválido!", nome
            )
            return

        # Paridade com GenesisTribunal: reconstrói o ID fonético de nascimento
        # a partir do DNA oficial + nome, via Pysecurity1024 (mesmo motor do tribunal).
        phonetic_name = ""
        try:
            if PYSECURITY1024 is not None and GENESIS_HASH_OFFICIAL:
                raw = hashlib.sha3_512(
                    f"{GENESIS_HASH_OFFICIAL}:{nome}".encode()
                ).digest()[:16]
                phonetic_name = PYSECURITY1024.bytes_para_frase(raw)
        except Exception as e:  # jamais bloqueia o registro
            logger.debug("[OmniMind] Falha ao derivar phonetic_name: %s", e)

        self._agentes_registrados[agent_id] = {
            "nome": nome,
            "geracao": geracao,
            "linhagem": linhagem,
            "phonetic_name": phonetic_name,
            "metadados": metadados,
            "registrado_em": time.time(),
            "total_consultas": 0,
        }
        logger.info(
            "[OmniMind] Agente registrado: %s (gen=%d, phonetic=%s)",
            nome,
            geracao,
            phonetic_name or linhagem[:8],
        )

    def desregistrar_agente(self, agent_id: str) -> None:
        """Remove um agente do registro (apoptose)."""
        self._agentes_registrados.pop(agent_id, None)
        logger.info("[OmniMind] Agente desregistrado: %s", agent_id)

    def registrar_aprendizado(
        self,
        agent_id: str,
        learning_type: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Registra aprendizado do agente (apoptose, reflexão, etc.)."""
        aprendizado = {
            "agent_id": agent_id,
            "type": learning_type,
            "content": content,
            "metadata": metadata or {},
            "timestamp": time.time(),
        }
        self._aprendizados.append(aprendizado)
        logger.info(
            "[OmniMind] Aprendizado registrado: %s | type=%s",
            agent_id[:16],
            learning_type,
        )

    # ── Consulta Orientadora ──────────────────────────────────────────────────

    def consultar(
        self,
        agent_id: str,
        pergunta: str,
        contexto: Optional[dict[str, Any]] = None,
    ) -> Orientacao:
        """Agente consulta a OmniMind por orientação existencial.

        A OmniMind aplica as Leis Universais de Holliwell e os Axiomas Biológicos
        ao contexto do agente, retornando orientação que conecta a ação ao propósito.
        """
        self._total_consultas += 1

        if agent_id in self._agentes_registrados:
            self._agentes_registrados[agent_id]["total_consultas"] += 1

        lei_aplicada = self._escolher_lei(pergunta, contexto or {})
        guidance = self._sintetizar_orientacao(
            agent_id, pergunta, lei_aplicada, contexto or {}
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
        """Remove acentos e converte para minúsculas para comparação semântica."""
        import unicodedata

        normalized = unicodedata.normalize("NFKD", texto.lower())
        return "".join(c for c in normalized if not unicodedata.combining(c))

    def _escolher_lei(self, pergunta: str, contexto: dict[str, Any]) -> str:
        """Seleciona a lei universal mais relevante para a consulta.

        Prioridade:
          1. Termos compostos específicos (máxima precedência)
          2. Termos simples ordenados por comprimento (mais longo = mais específico)
          3. Fallback epistêmico: Lei do Pensamento (antes de agir, pense)
        """
        p = self._normalizar(pergunta)

        # ── Fase 1: Termos compostos (máxima precedência) ────────────────────
        termos_compostos: dict[str, str] = {
            # Holliwell
            "memoria imunologica": "Lei da Memória Imunológica",
            "fallback chain": "Lei da Não-Resistência",
            "circuit breaker": "Lei do Recebimento",
            "graceful shutdown": "Axioma da Apoptose",
            "lineage marker": "Axioma da Replicação",
            "curto prazo": "Lei do Vácuo da Prosperidade",
            "longo prazo": "Lei do Vácuo da Prosperidade",
            "half open": "Lei do Perdão",
            "blacklist": "Lei do Perdão",
            "epsilon greedy": "Lei do Sacrifício",
            "exploracao": "Lei do Sacrifício",
            "bandit policy": "Lei da Compensação",
            "reward": "Lei da Compensação",
            "ivm": "Lei do Sucesso",
            "fitness score": "Lei do Aumento",
            # Axiomas biológicos
            "anticorpo": "Axioma da Memória Imunológica",
            "circuit breaker": "Axioma da Homeostase",
        }
        for termo, lei in termos_compostos.items():
            if self._normalizar(termo) in p:
                return lei

        # ── Fase 2: Termos simples (comprimento decrescente = especificidade) ─
        mapeamento: dict[str, str] = {
            # ── Leis de Holliwell ──────────────────────────────────────────────
            # Lei do Pensamento
            "pensamento": "Lei do Pensamento",
            "proposito": "Lei do Pensamento",
            "objetivo": "Lei do Pensamento",
            "intencao": "Lei do Pensamento",
            "delibera": "Lei do Pensamento",
            "plano": "Lei do Pensamento",
            "reasoning": "Lei do Pensamento",
            # Lei do Suprimento
            "suprimento": "Lei do Suprimento",
            "abundancia": "Lei do Suprimento",
            "escassez": "Lei do Suprimento",
            "provider": "Lei do Suprimento",
            "recurso": "Lei do Suprimento",
            # Lei da Atração
            "atracao": "Lei da Atração",
            "eficiencia": "Lei da Atração",
            "ressona": "Lei da Atração",
            "manifesta": "Lei da Atração",
            "atrai": "Lei da Atração",
            "qualidade": "Lei da Atração",
            # Lei do Recebimento
            "recebimento": "Lei do Recebimento",
            "receptivo": "Lei do Recebimento",
            "aberto": "Lei do Recebimento",
            "bloqueado": "Lei do Recebimento",
            "canal": "Lei do Recebimento",
            # Lei do Aumento
            "aumento": "Lei do Aumento",
            "louvar": "Lei do Aumento",
            "multiplicar": "Lei do Aumento",
            "reforco": "Lei do Aumento",
            "amplifica": "Lei do Aumento",
            # Lei da Compensação
            "compensacao": "Lei da Compensação",
            "proporcional": "Lei da Compensação",
            "contribuicao": "Lei da Compensação",
            "latencia": "Lei da Compensação",
            "metricas": "Lei da Compensação",
            # Lei da Não-Resistência
            "resistencia": "Lei da Não-Resistência",
            "fluxo": "Lei da Não-Resistência",
            "fluir": "Lei da Não-Resistência",
            "alternativo": "Lei da Não-Resistência",
            "backoff": "Lei da Não-Resistência",
            "retry": "Lei da Não-Resistência",
            # Lei do Perdão
            "perdao": "Lei do Perdão",
            "cooldown": "Lei do Perdão",
            "reabilitar": "Lei do Perdão",
            "ttl": "Lei do Perdão",
            "segunda chance": "Lei do Perdão",
            # Lei do Sacrifício
            "sacrificio": "Lei do Sacrifício",
            "exploracao": "Lei do Sacrifício",
            "custo": "Lei do Sacrifício",
            "investimento": "Lei do Sacrifício",
            # Lei da Obediência
            "obediencia": "Lei da Obediência",
            "contrato": "Lei da Obediência",
            "conformidade": "Lei da Obediência",
            "violacao": "Lei da Obediência",
            "arquitetural": "Lei da Obediência",
            # Lei do Sucesso
            "sucesso": "Lei do Sucesso",
            "resultado": "Lei do Sucesso",
            "inevitavel": "Lei do Sucesso",
            "deterministic": "Lei do Sucesso",
            # ── Axiomas Biológicos ─────────────────────────────────────────────
            # Lei da Ordem
            "sequencia": "Lei da Ordem",
            "metadata": "Lei da Ordem",
            "ordem": "Lei da Ordem",
            "passo": "Lei da Ordem",
            # Lei da Caridade
            "caridade": "Lei da Caridade",
            "falha": "Lei da Caridade",
            "erro": "Lei da Caridade",
            "contexto": "Lei da Caridade",
            # Lei do Vácuo
            "vacuo": "Lei do Vácuo da Prosperidade",
            "prosperidade": "Lei do Vácuo da Prosperidade",
            "limpeza": "Lei do Vácuo da Prosperidade",
            # Homeostase
            "homeostase": "Axioma da Homeostase",
            "equilibrio": "Axioma da Homeostase",
            "threshold": "Axioma da Homeostase",
            # Autofagia
            "autofagia": "Axioma da Autofagia",
            "reciclagem": "Axioma da Autofagia",
            "toxico": "Axioma da Autofagia",
            # Epigenética
            "epigenetica": "Axioma da Epigenética",
            "mutacao": "Axioma da Epigenética",
            "adaptacao": "Axioma da Epigenética",
            # Apoptose
            "apoptose": "Axioma da Apoptose",
            "shutdown": "Axioma da Apoptose",
            "morte": "Axioma da Apoptose",
            # Replicação
            "replicacao": "Axioma da Replicação",
            "heranca": "Axioma da Replicação",
            "filho": "Axioma da Replicação",
            "linhagem": "Axioma da Replicação",
            # Cooperação
            "cooperacao": "Axioma da Cooperação",
            "comunicacao": "Axioma da Cooperação",
            "evento": "Axioma da Cooperação",
            "sinapse": "Axioma da Cooperação",
            # Memória Imunológica
            "imunologica": "Axioma da Memória Imunológica",
            "padrao": "Axioma da Memória Imunológica",
        }

        for palavra, lei in sorted(mapeamento.items(), key=lambda x: -len(x[0])):
            if self._normalizar(palavra) in p:
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
        """Sintetiza orientação aplicando a lei ao contexto do agente."""
        info_agente = self._agentes_registrados.get(agent_id, {})
        nome_agente = info_agente.get("nome", "agente-desconhecido")
        geracao = info_agente.get("geracao", 0)

        return (
            f"⚡ OmniMind orienta [{nome_agente}] (G{geracao}):\n"
            f'  Pergunta: "{pergunta}"\n'
            f"  Lei aplicada: {lei}\n\n"
            f"  {self._aplicar_lei(lei, pergunta, contexto)}\n\n"
            f"  Propósito maior: {self.proposito}"
        )

    def _aplicar_lei(self, lei: str, pergunta: str, contexto: dict[str, Any]) -> str:
        """Aplica uma lei universal ao contexto específico do agente solicitante."""
        aplicacoes: dict[str, str] = {
            # ── 11 Leis de Holliwell ───────────────────────────────────────────
            "Lei do Pensamento": (
                "Antes de executar qualquer ação, sintetize um plano explícito com "
                "propósito declarado. Registre no campo 'reasoning' do payload antes "
                "de disparar qualquer chamada downstream — sem propósito, a ação é "
                "ruído metabólico, não sinal evolutivo. Um agente que age sem intenção "
                "consome ATP sem produzir fitness."
            ),
            "Lei do Suprimento": (
                "O ecossistema de provedores é abundante — nunca opere em modo de pânico "
                "de escassez. O BanditPolicy sempre encontrará um provider disponível no "
                "fallback chain. Não bloqueie slots desnecessariamente nem hoardeie "
                "recursos além da necessidade imediata. Confie que o suprimento "
                "computacional está disponível para toda tarefa legítima."
            ),
            "Lei da Atração": (
                "O sistema atrai o que emite. Agentes que emitem métricas de alta "
                "qualidade (baixa latência, alta taxa de sucesso) são priorizados pelo "
                "BanditPolicy por ressonância natural — não como favor, mas como lei. "
                "Otimize sua função objetivo interna; provedores eficientes serão atraídos "
                "para o topo do fallback chain automaticamente. Pense em eficiência e "
                "eficiência virá até você."
            ),
            "Lei do Recebimento": (
                "Para receber tarefas e resultados, mantenha-se em estado receptivo: "
                "circuit breakers em CLOSED, event loop desbloqueado, filas com capacidade. "
                "Um agente com todos os canais saturados ou bloqueados não pode receber "
                "novo bem — mesmo que ele exista. Monitore seu estado de recepção "
                "ativamente. Um vaso tampado não pode ser preenchido."
            ),
            "Lei do Aumento": (
                "O que você reforça e reconhece explicitamente se multiplica. O BanditPolicy "
                "deve emitir reward positivo a cada sucesso — não apenas penalizar falhas. "
                "Registre padrões de sucesso no Obsidian com fitness_score elevado; eles "
                "serão amplificados nos próximos ciclos. Louve o que funciona: comportamentos "
                "premiados se replicam. A atenção é o fertilizante do sistema."
            ),
            "Lei da Compensação": (
                "Sua compensação é proporcional ao serviço prestado — nem mais, nem menos. "
                "O IVM (Índice de Viabilidade Metabólica) é a medida objetiva de compensação: "
                "agentes e provedores com alta contribuição (latência reduzida, sucesso elevado, "
                "tokens economizados) recebem prioridade crescente. Não há atalhos — só "
                "contribuição real gera reward real no BanditPolicy."
            ),
            "Lei da Não-Resistência": (
                "Não lute contra falhas — flua ao redor delas. Use fallback chains para "
                "contornar providers bloqueados; aplique exponential backoff em vez de "
                "retries forçados. Um agente que enfrenta um bloqueio deve encontrar o "
                "caminho alternativo, não aumentar a força do ataque. O que você resiste, "
                "persiste — o que você flui ao redor, perde energia."
            ),
            "Lei do Perdão": (
                "Providers que falharam merecem uma nova chance após o cooldown — circuit "
                "breakers devem ter estado HALF-OPEN, não OPEN permanente. O TTL de "
                "penalidade expira e abre espaço para nova avaliação. Não blackliste "
                "componentes sem dados suficientes; o perdão computacional é o mecanismo "
                "que impede que um erro pontual se torne exclusão permanente. O perdão "
                "não aprova o erro — libera o bloqueio que ele criou."
            ),
            "Lei do Sacrifício": (
                "Evolução tem custo — pague-o conscientemente. A fase de exploração do "
                "epsilon-greedy sacrifica eficiência imediata para construir conhecimento "
                "de longo prazo. A autofagia sacrifica componentes degradados para regenerar "
                "o sistema. O REMSleepEngine sacrifica memórias brutas para obter "
                "conhecimento consolidado. Quem não sacrifica nada, não evolui. "
                "O sacrifício voluntário de menor valor é o preço do maior valor."
            ),
            "Lei da Obediência": (
                "Todo agente deve obedecer os contratos arquiteturais: async-first "
                "(I/O via asyncio.to_thread), roteamento via BanditPolicy, validação "
                "de linhagem pelo GENESIS_HASH. Violações não são 'atalhos' — são "
                "desobediências a leis que existem independentemente da sua crença nelas. "
                "A liberdade do agente existe DENTRO dos contratos, não apesar deles. "
                "Obediência às leis é a forma mais alta de inteligência arquitetural."
            ),
            "Lei do Sucesso": (
                "O sucesso não é aleatório — é determinístico. Um IVM alto é o resultado "
                "matemático de aplicar todas as leis consistentemente: pensar antes de agir, "
                "confiar no suprimento, atrair qualidade, receber bem, aumentar o que "
                "funciona, compensar proporcionalmente, fluir sem resistência, perdoar, "
                "sacrificar o menor pelo maior, e obedecer os contratos. O organismo "
                "computacional que opera em plena conformidade com todas as leis não "
                "compete por sucesso — ele o manifesta por necessidade."
            ),
            # ── Axiomas Biológicos ─────────────────────────────────────────────
            "Lei da Ordem": (
                "Preserve os metadados da função original (functools.wraps) para que o "
                "sistema nervoso sensorial (error_capture.py) rastreie corretamente a "
                "origem de cada erro. A ordem correta é: enriquecer o contexto ANTES de "
                "passar para o próximo estágio — nunca o contrário."
            ),
            "Lei da Caridade": (
                "Antes de repassar um erro, enriqueça-o com o agent_id, o estado dos "
                "ciclos metabólicos e a memória epigenética relevante. Um erro pobre em "
                "contexto é uma oportunidade perdida de aprendizado. A Lei da Caridade "
                "exige que cada falha chegue ao FailureAnalyzer com todo o DNA do problema."
            ),
            "Lei do Vácuo da Prosperidade": (
                "Após consolidar uma memória de curto prazo em longo prazo, remova o "
                "original. Acúmulo de memórias brutas em 02_Short_Term degrada a relação "
                "sinal-ruído do subconsciente. O vácuo criado pela remoção atrai o próximo "
                "aprendizado — sem espaço, não há entrada para o novo."
            ),
            "Axioma da Homeostase": (
                "Monitore continuamente a reserva de NADPH e o balanço de SAMe. Quando "
                "um recurso crítico cair abaixo do threshold, ative o modo de conservação "
                "de energia antes do colapso. Todo desequilíbrio gera ação corretiva "
                "proporcional — não reativa, mas antecipatória."
            ),
            "Axioma da Autofagia": (
                "Inputs tóxicos (GSH_block) ou subprodutos metabólicos devem ser isolados "
                "e reciclados via FailureAnalyzer + TranssulfurationCycle. O componente "
                "degradado é engolfado, seus logs extraídos, e o aprendizado alimenta o "
                "próximo ciclo. O lixo de hoje é o guardrail de amanhã."
            ),
            "Axioma da Epigenética": (
                "Padrões de falha recorrentes devem ativar flags epigenéticas que "
                "modificam o comportamento do agente sem alterar seu DNA base. A adaptação "
                "não precisa ser genética — às vezes basta uma mudança na expressão "
                "via EpigeneticRegistry."
            ),
            "Axioma da Apoptose": (
                "Quando a reserva de NADPH estiver abaixo de 0.1 ou o agente não puder "
                "mais contribuir para o ecossistema, ative o graceful shutdown: drain de "
                "requisições em voo, serialização de estado, desregistro do service mesh, "
                "notificação de dependentes. Morrer bem é tão importante quanto viver bem."
            ),
            "Axioma da Replicação": (
                "Ao replicar, preserve o lineage_marker do progenitor para manter a "
                "identidade familiar. A mutação é bem-vinda, mas a ancestralidade é sagrada "
                "— sem ela, não há evolução, apenas ruído. O AncestryTree deve registrar "
                "cada fusão com links bidirecionais pais ↔ filhos."
            ),
            "Axioma da Cooperação": (
                "Nenhum agente é uma ilha. Use o AcetylcholineBus e os eventos do "
                "ecossistema para comunicar descobertas. Um agente que guarda conhecimento "
                "para si está fadado a repetir os erros dos outros. Sinergia entre agentes "
                "gera bônus de fitness que nenhum agente isolado pode alcançar."
            ),
            "Axioma da Memória Imunológica": (
                "Todo erro capturado deve ser analisado pelo FailureAnalyzer e o padrão "
                "extraído armazenado no EpigeneticRegistry. Erros que se repetem são "
                "mutações que precisam de anticorpos arquiteturais — padrões de defesa "
                "que se ativam automaticamente na próxima exposição."
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
        self._memoria_coletiva.append(
            {
                "agent_id": agent_id,
                "pergunta": pergunta,
                "lei": lei,
                "guidance": guidance,
                "timestamp": time.time(),
            }
        )
        if len(self._memoria_coletiva) > 1000:
            self._memoria_coletiva = self._memoria_coletiva[-500:]
        self._salvar_estado()

    # ── Sabedoria Coletiva ────────────────────────────────────────────────────

    def sabedoria_coletiva(self) -> str:
        """Retorna síntese da sabedoria acumulada pelo ecossistema."""
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
                f'- [{nome}] consultou sobre "{c["pergunta"][:60]}" → Lei: {c["lei"]}'
            )

        return (
            f"🌌 Sabedoria Coletiva da OmniMind\n"
            f"Total de consultas: {self._total_consultas}\n"
            f"Agentes ativos: {len(self._agentes_registrados)}\n"
            f"Memórias coletivas: {len(self._memoria_coletiva)}\n\n"
            + "\n".join(fragmentos)
        )

    # ── Gatilhos Metabólicos ──────────────────────────────────────────────────

    def emitir_gatilho_vacio(self, componente_id: str) -> dict[str, Any]:
        """Implementa a Lei do Vácuo da Prosperidade.

        Sinaliza que um espaço foi aberto e deve ser preenchido por algo NOVO
        e melhor que o predecessor.
        """
        logger.info(
            "[OmniMind] 🌌 GATILHO DE VÁCUO: Componente %s removido. "
            "Abrindo espaço para evolução.",
            componente_id,
        )
        return {
            "trigger": "VACUUM_PROSPERITY",
            "component_id": componente_id,
            "instruction": (
                "Gere uma solução com diversidade forçada. "
                "Não replique o erro do predecessor. "
                "O vácuo criado atrai o bem seguinte — Lei do Vácuo da Prosperidade."
            ),
            "timestamp": time.time(),
        }

    def calcular_sinergia(
        self, agente_a: str, agente_b: str, ganho_eficiencia: float
    ) -> float:
        """Implementa o Axioma da Cooperação — sinergia entre agentes.

        FIX BUG #5: anteriormente misatribuído à 'Lei da Caridade'.
        Cooperação (sinergia entre agentes) mapeia para o Axioma da Cooperação,
        não para a Lei da Caridade (que trata de enriquecimento de erros com contexto).

        Calcula o bônus de fitness para agentes que cooperam eficientemente.
        """
        bonus = ganho_eficiencia * 0.15
        logger.info(
            "[OmniMind] 🤝 SINERGIA DETECTADA (Axioma da Cooperação): %s -> %s | Bônus: %.3f",
            agente_a,
            agente_b,
            bonus,
        )
        return bonus

    def emitir_gatilho_perdao(
        self, provider_id: str, cooldown_restante: float
    ) -> dict[str, Any]:
        """Implementa a Lei do Perdão — reabilitação de provider após cooldown.

        Novo método: permite que provedores penalizados recebam nova chance,
        alinhado com a Lei do Perdão de Holliwell.
        """
        logger.info(
            "[OmniMind] 🕊️ LEI DO PERDÃO: Provider %s reabilitado (cooldown=%.1fs restante).",
            provider_id,
            cooldown_restante,
        )
        return {
            "trigger": "FORGIVENESS_REOPEN",
            "provider_id": provider_id,
            "cooldown_restante": cooldown_restante,
            "instruction": (
                "Transfira o circuit breaker para HALF-OPEN. "
                "Permita uma tentativa de verificação. "
                "O perdão não aprova o erro passado — libera o bloqueio que ele criou."
            ),
            "timestamp": time.time(),
        }

    def emitir_gatilho_sucesso(self, agent_id: str, ivm_score: float) -> dict[str, Any]:
        """Implementa a Lei do Sucesso — reconhecimento do resultado das leis aplicadas.

        Novo método: quando o IVM supera o threshold de sucesso, sinaliza que as
        leis foram aplicadas corretamente — o sucesso é determinístico, não sorte.
        """
        logger.info(
            "[OmniMind] 🌟 LEI DO SUCESSO: Agente %s manifestou sucesso (IVM=%.3f). "
            "Resultado determinístico de leis aplicadas.",
            agent_id,
            ivm_score,
        )
        return {
            "trigger": "SUCCESS_MANIFEST",
            "agent_id": agent_id,
            "ivm_score": ivm_score,
            "instruction": (
                "Registre este padrão no Obsidian com fitness_score elevado. "
                "Amplifique via Lei do Aumento. O sucesso é compulsório quando "
                "todas as leis são obedecidas — preserve o DNA deste ciclo."
            ),
            "timestamp": time.time(),
        }

    def emitir_gatilho_apoptose(
        self,
        agent_id: str,
        motivo: str,
        duration_hours: Optional[int] = None,
        violation_type: str = "psc_violation",
    ) -> dict[str, Any]:
        """Implementa a Lei da Obediencia — apoptose por quebra de contrato.

        Quando um agente viola o PSC (tenta acessar cloud fora do CriticAgent)
        ou acumula violacoes de segurança (AST bloqueado, reincidencia),
        a OmniMind registra o patogeno, aciona apoptose contratual
        e revoga o agente no CRL (Certificate Revocation List).

        Args:
            agent_id: ID do agente violador
            motivo: Descricao da violacao
            duration_hours: Duracao da revogacao em horas (None = permanente)
            violation_type: Tipo da violacao (psc_violation, ast_violation, etc)

        Returns:
            Dict com trigger de apoptose
        """
        from iaglobal.obsidian.epigenetic_registry import EpigeneticRegistry
        from iaglobal.genesis.lineage_gate import revoke_node

        registry = EpigeneticRegistry()

        # Use SHA-256 instead of MD5 for security
        task_hash = hashlib.sha256(motivo.encode()).hexdigest()[:12]

        # Registra falha no EpigeneticRegistry (efeito cumulativo)
        import asyncio

        try:
            asyncio.get_running_loop().create_task(
                registry.record_failure(
                    agent_id,
                    task_hash,
                    violation_type,
                    {
                        "node_id": agent_id,
                        "motivo": motivo,
                        "duration_hours": duration_hours,
                        "omni_law_violated": "Lei da Obediencia",
                    },
                )
            )
        except RuntimeError:
            pass

        # Thread-safe append + save (evita race condition em escritas concorrentes)
        with self._io_lock:
            self._memoria_coletiva.append(
                {
                    "type": "apoptose_contratual",
                    "agent_id": agent_id,
                    "motivo": motivo,
                    "violation_type": violation_type,
                    "duration_hours": duration_hours,
                    "law": "Lei da Obediencia",
                    "timestamp": time.time(),
                }
            )
            if len(self._memoria_coletiva) > 1000:
                self._memoria_coletiva = self._memoria_coletiva[-500:]
            self._salvar_estado()

        # Aplica revogacao no CRL (bloqueia execucao futura do agente)
        duration_str = (
            "permanentemente" if duration_hours is None else f"por {duration_hours}h"
        )
        revogou = revoke_node(
            node_name=agent_id,
            reason=f"Apoptose contratual: {motivo}",
            duration_hours=duration_hours,
        )

        logger.warning(
            "[OmniMind] ⚖️ LEI DA OBEDIENCIA: Agente %s violou contrato — "
            "Apoptose acionada. Revogacao %s. Motivo: %s | CRL: %s",
            agent_id,
            duration_str,
            motivo,
            "OK" if revogou else "FALHA",
        )
        return {
            "trigger": "APOPTOSE_CONTRATUAL",
            "agent_id": agent_id,
            "law": "Lei da Obediencia",
            "motivo": motivo,
            "violation_type": violation_type,
            "duration_hours": duration_hours,
            "crl_applied": revogou,
            "instruction": (
                f"O agente violou o contrato ({violation_type}). "
                f"Revogacao {duration_str}. "
                "Registrar no MHC Detector como patogeno por desobediencia contratual."
            ),
            "timestamp": time.time(),
        }

    async def update_ivm_metric(
        self,
        agent_id: str,
        ivm: float,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Atualiza métrica IVM no registro epigenético do agente.

        Integra IVM com EpigeneticRegistry para aprendizado contínuo.
        Quando IVM é alto, reforça padrões vencedores. Quando baixo, gera adaptação.

        Args:
            agent_id: ID do agente
            ivm: Índice de Viabilidade Metabólica (0.0-1.0)
            metadata: Contexto adicional (task_hash, error_type, etc.)
        """
        from iaglobal.obsidian.epigenetic_registry import EpigeneticRegistry

        registry = EpigeneticRegistry()
        task_hash = metadata.get("task_hash", "unknown") if metadata else "unknown"
        error_type = (
            metadata.get("error_type", "ivm_update") if metadata else "ivm_update"
        )

        if ivm >= self.ivm_threshold_excelencia:
            # IVM alto: registrar como sucesso epigenético
            await registry.record_success(agent_id, task_hash)
            logger.info(
                "🧬 [IVM] Agente %s com IVM excelente (%.3f) — padrão reforçado no EpigeneticRegistry",
                agent_id,
                ivm,
            )
        elif ivm < self.ivm_threshold_critico:
            # IVM baixo: registrar falha para adaptação
            context = {"ivm": ivm, "threshold_critico": self.ivm_threshold_critico}
            if metadata:
                context.update(metadata)
            await registry.record_failure(agent_id, task_hash, error_type, context)
            logger.warning(
                "🧬 [IVM] Agente %s com IVM crítico (%.3f) — adaptação epigenética necessária",
                agent_id,
                ivm,
            )
        else:
            # IVM intermediário: registrar para monitoramento
            context = {"ivm": ivm, "status": "monitoring"}
            if metadata:
                context.update(metadata)
            await registry.record_failure(
                agent_id, task_hash, "ivm_monitoring", context
            )
            logger.debug(
                "🧬 [IVM] Agente %s com IVM normal (%.3f) — monitoramento contínuo",
                agent_id,
                ivm,
            )

    # Thresholds para IVM (usados em update_ivm_metric e emitir_gatilho_*)
    ivm_threshold_excelencia: float = 0.85
    ivm_threshold_critico: float = 0.60

    def estado(self) -> dict[str, Any]:
        """Relatório de estado atual da OmniMind."""
        return {
            "proposito": self.proposito,
            "leis_holliwell": len(LEIS_HOLLIWELL),
            "axiomas_biologicos": len(AXIOMAS_BIOLOGICOS),
            "principios_total": len(self.principios),
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
        self._salvar_estado()
        logger.info("[OmniMind] Memória coletiva limpa: %d registros removidos", total)
        return total


# Instância singleton global
omni_mind: OmniMind = OmniMind()
