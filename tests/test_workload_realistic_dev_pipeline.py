#!/usr/bin/env python3
"""
Teste de workload real para pipeline de desenvolvimento de software (planner -> coder -> tester -> critic -> enhancement).
Objetivo: Validar integração do motor com carga real de handlers e provedores via provider cascade e Fallback.
"""

import asyncio
import os
import sys
import time
import json
from pathlib import Path

# Garantir resolução de imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from iaglobal.core.globals import G
from iaglobal import pipeline
from iaglobal.graphs.execution_graph import ExecutionGraph
from iaglobal.agents.planner_agent import PlannerAgent
from iaglobal.agents.coder_agent import CoderAgent
from iaglobal.agents.tester_agent import TesterAgent
from iaglobal.agents.critic_agent import CriticAgent
from iaglobal.agents.enhancement_agent import EnhancementAgent

# Configuração de ambiente
os.environ.setdefault("SEQUENTIAL_FALLBACK", "0")
os.environ.setdefault("OLLAMA_ONLY", "0")
os.environ.setdefault("RACE_SIZE", "3")

output_dir = Path("/tmp/realistic_workload_logs")
output_dir.mkdir(exist_ok=True, parents=True)

TASK = (
    "Como engenheiro de software fullstack, desenvolva um CRUD completo para uma API RESTful em Python usando FastAPI e SQLite. "
    "Adicione também documentação Swagger, testes unitários com pytest e coverage report. "
    "Requisitos: endpoints para criar, ler, atualizar e deletar users; autenticação JWT básica; testes com pytest; coverage >= 90%. "
    "Quero que crie os arquivos: main.py, models.py, schemas.py, tests/test_api.py, requirements.txt, README.md. "
    "Implemente também um script para popular o banco com 5 users de teste na inicialização da aplicação."
)


class RealisticDevPipeline:
    def __init__(self):
        self.log_path = str(output_dir / f"workload_run_{int(time.time())}.json")
        self.metrics = {
            "agents": {},
            "handlers": {},
            "total_latency_sec": None,
            "success": False,
            "output_artifacts": []
        }

    def _log_handler(self, agent_name: str, stage: str, latency: float, result: dict | None = None):
        entry = {
            "agent": agent_name,
            "stage": stage,
            "latency_sec": round(latency, 3),
            "timestamp": time.time(),
        }
        if result and result.get("status") == "success":
            entry["files_created"] = result.get("artifacts")
        self.metrics["agents"][agent_name] = entry
        return entry

    async def run(self):
        start_total = time.time()

        # Inicializar agentes (simulando injeção via mailbox no DAG)
        planner = PlannerAgent()
        coder = CoderAgent()
        tester = TesterAgent()
        critic = CriticAgent()
        enhancer = EnhancementAgent()

        results = {}

        # Fase 1: Planner
        try:
            t0 = time.time()
            resp = await planner.arun(TASK)
            latency = time.time() - t0
            self._log_handler("planner", "plan", latency, resp)
            results["plan"] = resp.get("plan", [])
            results["prd"] = resp.get("prd", "")
            results["architecture"] = resp.get("architecture", "")
        except Exception as e:
            t0_err = time.time() - t0 if "t0" in locals() else time.time()
            self._log_handler("planner", "error", t0_err, None)
            raise

        # Fase 2: Coder
        try:
            t0 = time.time()
            resp = await coder.arun(TASK, context={"plan": results["plan"]})
            latency = time.time() - t0
            self._log_handler("coder", "coding", latency, resp)
            results["artifacts"] = resp.get("artifacts", {})
        except Exception as e:
            t0_err = time.time() - t0 if "t0" in locals() else time.time()
            self._log_handler("coder", "error", t0_err, None)
            raise

        # Salvar artefatos gerados (FastAPI CRUD)
        artifacts_dir = Path(output_dir) / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        base_readme = f"# CRUD FastAPI + SQLite\n\n{results['prd']}\n\n## Arquitetura\n\n{results['architecture']}"
        base_readme_path = artifacts_dir / "README_base.md"
        base_readme_path.write_text(base_readme)

        if results["artifacts"]:
            for fn, content in results["artifacts"].items():
                (artifacts_dir / fn).write_text(content)

        # Fase 3: Tester
        try:
            test_task = (
                f"Execute testes pytest nos artefatos criados pelo CoderAgent e gere um relatório de coverage. "
                f"Use Python 3.11+ e pytest-cov. "
                f"Artefatos disponíveis: {list((artifacts_dir).glob('*'))}"
            )
            t0 = time.time()
            resp = await tester.arun(test_task, context={"artifacts_dir": str(artifacts_dir)})
            latency = time.time() - t0
            self._log_handler("tester", "testing", latency, resp)
            results["test_report"] = resp
        except Exception as e:
            t0_err = time.time() - t0 if "t0" in locals() else time.time()
            self._log_handler("tester", "error", t0_err, None)
            raise

        # Fase 4: Critic
        try:
            critic_task = (
                "Revise os artefatos gerados para garantir que atendem aos requisitos: "
                "CRUD completo, endpoints RESTful, autenticação JWT, documentação Swagger, testes pytest, coverage >= 90%, "
                "Requisitos anteriores: FastAPI + SQLite + users CRUD."
            )
            t0 = time.time()
            resp = await critic.arun(critic_task, context={"artifacts": str(artifacts_dir)})
            latency = time.time() - t0
            self._log_handler("critic", "critique", latency, resp)
            results["critique"] = resp
        except Exception as e:
            t0_err = time.time() - t0 if "t0" in locals() else time.time()
            self._log_handler("critic", "error", t0_err, None)
            raise

        # Fase 5: Enhancement (opcional, apenas se critic sugerir)
        try:
            enh_task = "Melhore os artefatos com base no feedback do critique. Mantenha compatibilidade."
            t0 = time.time()
            resp = await enhancer.handle(enh_task, context={"critique": results["critique"], "artifacts": str(artifacts_dir)})
            latency = time.time() - t0
            self._log_handler("enhancer", "enhance", latency, resp)
            results["enhancement"] = resp
        except Exception:
            # Enhancer pode falhar; não bloqueia teste principal
            t0_err = time.time() - t0 if "t0" in locals() else time.time()
            self._log_handler("enhancer", "error", t0_err, None)

        self.metrics["total_latency_sec"] = round(time.time() - start_total, 3)
        self.metrics["success"] = all(k in results for k in ["plan", "artifacts", "test_report"])
        self.metrics["output_artifacts"] = [p.name for p in artifacts_dir.glob("*") if p.is_file()]

        with open(self.log_path, "w") as f:
            json.dump(self.metrics, f, indent=2, ensure_ascii=False)

        return self.metrics


async def main():
    print("🧪 Iniciando teste de workload real para pipeline de desenvolvimento de software...")
    pipeline = RealisticDevPipeline()
    try:
        metrics = await pipeline.run()
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
        print(f"\n✅ Teste concluído. Log salvo em: {pipeline.log_path}")
        if metrics["success"]:
            print("✔️ Pipeline executou com sucesso para carga real.")
        else:
            print("⚠️ Pipeline executou, mas algumas fases falharam.")
        return 0
    except Exception as e:
        print(f"\n❌ Teste falhou: {e}")
        with open(pipeline.log_path.replace(".json", "_error.log"), "w") as f:
            f.write(str(e) + "\n" + traceback.format_exc())
        return 1

if __name__ == "__main__":
    import sys
    sys.exit(asyncio.run(main()))