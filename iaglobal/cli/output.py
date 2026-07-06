# iaglobal/cli/output.py

import json

class OutputRenderer:

    @staticmethod
    def render(result):
        script_path = None
        response_text = None
        success = getattr(result, "success", False)

        if hasattr(result, "script_path") and result.script_path:
            script_path = result.script_path
            response_text = result.response
        elif isinstance(result, dict):
            raw = result.get("raw_results", {})
            if isinstance(raw, dict):
                aw = raw.get("artifact_writer", {})
                if isinstance(aw, dict):
                    art = aw.get("artifact")
                    if hasattr(art, "path") and art.path:
                        script_path = art.path
                    elif aw.get("path"):
                        script_path = aw.get("path")
                    if not response_text:
                        response_text = aw.get("artifact_code", "")
            if not script_path:
                art = result.get("artifact")
                if hasattr(art, "path") and art.path:
                    script_path = art.path
            if not script_path:
                script_path = result.get("path")

        if success and script_path:
            print(f"\n✅ Seu script ficou pronto na pasta {script_path}")
            if response_text:
                print(f"\n📄 Código gerado ({len(response_text)} caracteres)")
            return

        if hasattr(result, "response") and result.response:
            print("\n" + result.response)
            return

        if hasattr(result, "error") and result.error:
            print(f"\n❌ Erro: {result.error}")
            return

        if hasattr(result, "errors") and result.errors:
            for e in result.errors:
                print(f"\n❌ {e}")
            return

        if isinstance(result, dict):
            final_output = result.get("final_output")
            if final_output:
                art = result.get("artifact")
                if hasattr(art, "path") and art.path:
                    print(f"\n✅ Seu script ficou pronto na pasta {art.path}")
                    return
                print("\n" + str(final_output))
                return

            raw = result.get("raw_results", {})
            if isinstance(raw, dict) and raw:
                for name in ("artifact_writer", "final_gatekeeper", "debugger", "tester"):
                    nr = raw.get(name, {})
                    if isinstance(nr, dict):
                        out = nr.get("output")
                        if hasattr(out, "code") and out.code:
                            p = nr.get("path")
                            if p:
                                print(f"\n✅ Seu script ficou pronto na pasta {p}")
                            else:
                                print("\n" + out.code[:2000])
                            return

            error = result.get("error")
            if error:
                print(f"\n❌ Erro: {error}")
                return

        print(result)


class HistoryRenderer:

    @staticmethod
    def render_execution(events: list, execution_id: str):
        print(f"\n{'='*60}")
        print(f"  📜 DECISION TRACE: {execution_id}")
        print(f"{'='*60}")
        if not events:
            print("  (nenhum evento encontrado)")
            print(f"{'='*60}\n")
            return

        for i, ev in enumerate(events):
            try:
                data = json.loads(ev["event_data"]) if isinstance(ev.get("event_data"), str) else ev.get("event_data", {})
            except Exception:
                data = {}
            step = data.get("step", ev.get("step", "?"))
            ts = data.get("timestamp", ev.get("timestamp", ""))[11:19] if data.get("timestamp") else ""
            tag = HistoryRenderer._summary(data)
            print(f"  {i+1:2d}. [{ts}] {step:25s} {tag}")
        print(f"{'='*60}\n")

    @staticmethod
    def render_steps(events: list, step_filter: str):
        print(f"\n  📜 Eventos do tipo \"{step_filter}\":")
        if not events:
            print("  (nenhum)")
            print()
            return
        for ev in events:
            try:
                data = json.loads(ev["event_data"]) if isinstance(ev.get("event_data"), str) else {}
            except Exception:
                data = {}
            ts = data.get("timestamp", ev.get("timestamp", ""))[11:19] if data.get("timestamp") else ""
            eid = ev.get("execution_id", "?")[:16]
            tag = HistoryRenderer._summary(data)
            print(f"  [{ts}] {eid:16s} {tag}")

    @staticmethod
    def render_list(entries: list):
        print(f"\n  📜 Últimas execuções com DecisionEvents:\n")
        if not entries:
            print("  (nenhuma execução registrada)")
            print()
            return
        for eid, count, last_ts in entries:
            print(f"  {last_ts[11:19] if last_ts else '':8s}  {eid:36s}  {count:3d} eventos")

    @staticmethod
    def render_stats(stats: dict):
        print(f"\n  📊 DECISION EVENTS — Estatísticas\n")
        print(f"  Total no banco:  {stats['total']}")
        print(f"  Por step:")
        for step, count in sorted(stats.get("by_step", {}).items(), key=lambda x: -x[1]):
            print(f"    {step:30s} {count:4d}")
        print()

    @staticmethod
    def _summary(data: dict) -> str:
        for key in ("selected", "result", "status", "action", "reason", "triggered"):
            val = data.get(key)
            if val is not None and val is not False:
                if key == "triggered":
                    return "evoluiu" if val else "estável"
                return str(val)[:50]
        return "-"


class ReplayRenderer:

    @staticmethod
    def render_summary(summary: dict):
        print(f"\n{'='*60}")
        print(f"  🔄 REPLAY SUMMARY: {summary['execution_id']}")
        print(f"{'='*60}")
        print(f"  Eventos:       {summary.get('events', '?')}")
        print(f"  Modelo:        {summary.get('model', '?')}")
        print(f"  Cache:         {summary.get('cache', '?')}")
        print(f"  Task type:     {summary.get('task_type', '?')}")
        print(f"  Ambiguidade:   {summary.get('ambiguity', 0)}")
        print(f"  Small model:   {summary.get('small_model', '?')}")
        print(f"  Recompensa:    {summary.get('reward_signal', '?')}")
        print(f"  Latência:      {summary.get('latency_ms', '?')}ms")
        print(f"  Exploração:    {summary.get('exploration', '?')}")
        print(f"  Evolução:      {'sim' if summary.get('evolution_triggered') else 'não'}")
        print(f"{'='*60}\n")

    @staticmethod
    def render_what_if(result: dict):
        print(f"\n{'='*60}")
        print(f"  🔀 WHAT-IF: {result['execution_id']}")
        print(f"{'='*60}")
        print(f"  Modelo original:  {result['original_model']}")
        print(f"  Score original:   {result['original_score']}")
        print(f"  Recompensa real:  {result['original_reward']}")
        print()
        print(f"  Alternativa:      {result['alternative_model']}")
        print(f"  Score alternativo: {result['alternative_score']}")
        print(f"  Recompensa est.:  {result['estimated_reward']}")
        print(f"  Δ score:          {result['score_delta']:+.3f}")
        verdict = "✅ MELHOR" if result['would_be_better'] else "⚠️ PIOR" if result['score_delta'] < 0 else "➡️ IGUAL"
        print(f"  Veredito:         {verdict}")
        print(f"{'='*60}\n")

    @staticmethod
    def render_explain(result: dict):
        print(f"\n{'='*60}")
        print(f"  🤖 EXPLAIN: {result['execution_id']}")
        print(f"{'='*60}")
        print(f"\n  {result['analysis']}\n")
        print(f"{'='*60}\n")

    @staticmethod
    def render_train_result(result: dict):
        if not result.get("trained"):
            print(f"\n  ❌ Treinamento falhou: {result.get('reason', 'erro desconhecido')}\n")
            return
        print(f"\n{'='*60}")
        print(f"  🧠 BANDIT TRAINED com histórico real")
        print(f"{'='*60}")
        print(f"  Modelo:      {result['model']}")
        print(f"  Recompensa:  {result['reward']}")
        print(f"  Novo score:  {result['new_score']:.4f}")
        print(f"  Estratégia:  {result['strategy']}")
        print(f"{'='*60}\n")
