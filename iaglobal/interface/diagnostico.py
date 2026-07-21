# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""
iaglobal/interface/diagnostico.py

Schemas de diagnóstico de falhas e métricas de recuperação — o mRNA que o
FailureAnalyzer usa como template para sintetizar planos de correção.

Isolado em módulo próprio para evitar ciclos de importação com chat_agent,
evo_agent, e o resto do ecossistema.
"""

from typing import Optional
from pydantic import BaseModel, Field


class DiagnosticoFalha(BaseModel):
    """
    Diagnóstico estruturado de uma falha de execução.

    Gerado pelo FailureAnalyzer a partir do output bruto do code_executor.
    """

    tipo_erro: str = Field(
        "Unknown",
        description="Classe do erro: SyntaxError, TimeoutError, AssertionError, ImportError, RuntimeError, Unknown",
    )
    mensagem: str = Field(
        "", description="Mensagem principal do erro (primeira linha significativa)"
    )
    linha: Optional[int] = Field(
        None, description="Linha onde o erro ocorreu, se extraível"
    )
    arquivo: Optional[str] = Field(
        None, description="Arquivo onde o erro ocorreu, se disponível"
    )
    fingerprint: str = Field(
        "",
        description="SHA256 do traceback sanitizado (sem paths absolutos) — chave da vacina",
    )
    codigo_original: str = Field("", description="Código que falhou, para referência")
    output_bruto: str = Field(
        "", description="Output completo do code_executor (stdout + stderr)"
    )


class RecoveryMetrics(BaseModel):
    """
    Métricas de recuperação após falha — alimentam o JointOptimizationLoop
    com o delta de aprendizado.
    """

    tentativas: int = Field(0, description="Número de tentativas até sucesso")
    delta_segundos: float = Field(
        0.0, description="Tempo entre primeiro erro e correção bem-sucedida"
    )
    vacina_aplicada: bool = Field(
        False, description="Se a correção usou uma vacina pré-existente"
    )
    fingerprint_erro: str = Field(
        "", description="Fingerprint do erro original (para deduplicação no JOL)"
    )
