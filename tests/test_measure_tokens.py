#!/usr/bin/env python3
"""Mede uso de tokens diretamente do banco SQLite (core.db).

Uso:
    python test_measure_tokens.py              # relatório completo
    python test_measure_tokens.py --last 5     # últimos N registros
    python test_measure_tokens.py --model foo  # filtrar por modelo
    python test_measure_tokens.py --watch      # modo contínuo (polling a cada 5s)
"""
import argparse
import sqlite3
import time
from pathlib import Path
from typing import Optional


CORE_DB = Path(__file__).parent / "iaglobal" / "memory" / "data" / "db" / "core.db"


def connect():
    if not CORE_DB.exists():
        print(f"[ERRO] Banco não encontrado: {CORE_DB}")
        return None
    return sqlite3.connect(str(CORE_DB), timeout=5)


def query_events(conn, model: Optional[str] = None, limit: Optional[int] = None):
    where, params = "", []
    if model:
        where, params = "WHERE model = ?", [model]
    lim = f"LIMIT {limit}" if limit else ""
    return conn.execute(
        f"SELECT id, timestamp, task_fingerprint, event_type, "
        f"model, latency_ms, tokens_in, tokens_out "
        f"FROM events {where} ORDER BY id DESC {lim}",
        params,
    ).fetchall()


def query_outcomes(conn, model: Optional[str] = None, limit: Optional[int] = None):
    where, params = "", []
    if model:
        where, params = "WHERE model = ?", [model]
    lim = f"LIMIT {limit}" if limit else ""
    return conn.execute(
        f"SELECT id, provider, model, fingerprint, latency_ms, "
        f"token_cost, success_score, retries, timestamp, tokens_in, tokens_out "
        f"FROM execution_outcomes {where} ORDER BY id DESC {lim}",
        params,
    ).fetchall()


def print_summary(conn):
    print("=" * 64)
    print("  TELEMETRIA — Eventos")
    print("=" * 64)
    row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
    total_events = row[0] if row else 0
    print(f"  Total de eventos:          {total_events}")

    if total_events:
        row = conn.execute("SELECT COALESCE(SUM(tokens_in), 0), COALESCE(SUM(tokens_out), 0) FROM events").fetchone()
        print(f"  Tokens in (total):         {row[0]:>8}")
        print(f"  Tokens out (total):        {row[1]:>8}")
        print(f"  Tokens total:              {row[0] + row[1]:>8}")

        row = conn.execute("SELECT COUNT(DISTINCT event_type) FROM events").fetchone()
        print(f"  Tipos de evento:           {row[0] if row else 0}")

        print()
        print("  -- Por tipo de evento --")
        for r in conn.execute(
            "SELECT event_type, COUNT(*), COALESCE(SUM(tokens_in),0), COALESCE(SUM(tokens_out),0), "
            "ROUND(AVG(latency_ms), 1) FROM events GROUP BY event_type ORDER BY COUNT(*) DESC"
        ).fetchall():
            print(f"  {r[0]:<30s}  {r[1]:>4} eventos  "
                  f"tok_in={r[2]:>6}  tok_out={r[3]:>6}  lat_avg={r[4]:>8}ms")

        print()
        print("  -- Por modelo --")
        for r in conn.execute(
            "SELECT model, COUNT(*), COALESCE(SUM(tokens_in),0), COALESCE(SUM(tokens_out),0), "
            "ROUND(AVG(latency_ms), 1) FROM events WHERE model != '' GROUP BY model ORDER BY COUNT(*) DESC"
        ).fetchall():
            print(f"  {r[0]:<30s}  {r[1]:>4} eventos  "
                  f"tok_in={r[2]:>6}  tok_out={r[3]:>6}  lat_avg={r[4]:>8}ms")

    print()
    print("=" * 64)
    print("  TELEMETRIA — Execution Outcomes")
    print("=" * 64)
    row = conn.execute("SELECT COUNT(*) FROM execution_outcomes").fetchone()
    total_outcomes = row[0] if row else 0
    print(f"  Total de outcomes:         {total_outcomes}")

    if total_outcomes:
        row = conn.execute(
            "SELECT COALESCE(SUM(tokens_in),0), COALESCE(SUM(tokens_out),0), "
            "COALESCE(SUM(token_cost),0.0), ROUND(AVG(success_score), 3), "
            "ROUND(AVG(latency_ms), 1), COALESCE(SUM(retries),0) "
            "FROM execution_outcomes"
        ).fetchone()
        print(f"  Tokens in (total):         {row[0]:>8}")
        print(f"  Tokens out (total):        {row[1]:>8}")
        print(f"  Tokens total:              {row[0] + row[1]:>8}")
        print(f"  Custo total (USD):         {row[2]:>8.6f}")
        print(f"  Success rate (média):      {row[3]:>8.3f}")
        print(f"  Latência média (ms):       {row[4]:>8.1f}")
        print(f"  Total de retries:          {row[5]:>8}")

        print()
        print("  -- Por modelo --")
        for r in conn.execute(
            "SELECT model, COUNT(*), COALESCE(SUM(tokens_in),0), COALESCE(SUM(tokens_out),0), "
            "ROUND(AVG(success_score), 3), ROUND(AVG(latency_ms), 1), "
            "ROUND(COALESCE(SUM(token_cost),0.0), 6) "
            "FROM execution_outcomes GROUP BY model ORDER BY COUNT(*) DESC"
        ).fetchall():
            print(f"  {r[0]:<30s}  {r[1]:>4} ocorrências  "
                  f"tok_in={r[2]:>6}  tok_out={r[3]:>6}  "
                  f"success={r[4]:.2f}  lat={r[5]:>8.1f}ms  cost={r[6]:.6f}")

        print()
        print("  -- Por provedor --")
        for r in conn.execute(
            "SELECT provider, COUNT(*), COALESCE(SUM(tokens_in),0), COALESCE(SUM(tokens_out),0), "
            "ROUND(AVG(success_score), 3), ROUND(AVG(latency_ms), 1) "
            "FROM execution_outcomes GROUP BY provider ORDER BY COUNT(*) DESC"
        ).fetchall():
            print(f"  {r[0]:<30s}  {r[1]:>4} ocorrências  "
                  f"tok_in={r[2]:>6}  tok_out={r[3]:>6}  "
                  f"success={r[4]:.2f}  lat={r[5]:>8.1f}ms")

    print()
    print("=" * 64)
    print("  DECISION EVENTS (últimos 10)")
    print("=" * 64)
    rows = conn.execute(
        "SELECT id, execution_id, step, timestamp, event_data "
        "FROM decision_events ORDER BY id DESC LIMIT 10"
    ).fetchall()
    if rows:
        for r in rows:
            print(f"  #{r[0]}  exec={r[1]:<20s}  step={r[2]:<20s}  ts={r[3]}")
    else:
        print("  (vazio)")
    print()


def print_last_entries(conn, model: Optional[str] = None, n: int = 10):
    print("--- ÚLTIMOS EVENTOS ---")
    rows = query_events(conn, model=model, limit=n)
    if rows:
        for r in rows:
            eid, ts, fp, etype, mdl, lat, tin, tout = r
            print(f"  #{eid}  [{etype:<20s}]  model={mdl:<20s}  "
                  f"tokens=({tin},{tout})  lat={lat:.0f}ms  fp={fp}")
    else:
        print("  (vazio)")

    print()
    print("--- ÚLTIMOS OUTCOMES ---")
    rows = query_outcomes(conn, model=model, limit=n)
    if rows:
        for r in rows:
            eid, prov, mdl, fp, lat, cost, success, retries, ts, tin, tout = r
            print(f"  #{eid}  [{prov:<15s}]  model={mdl:<20s}  "
                  f"tokens=({tin},{tout})  success={success:.2f}  "
                  f"lat={lat:.0f}ms  cost={cost:.6f}")
    else:
        print("  (vazio)")
    print()


def main():
    parser = argparse.ArgumentParser(description="Mede uso de tokens do banco core.db")
    parser.add_argument("--last", type=int, default=0, help="Mostrar últimos N registros")
    parser.add_argument("--model", type=str, default=None, help="Filtrar por modelo")
    parser.add_argument("--watch", action="store_true", help="Modo contínuo (polling a cada 5s)")
    args = parser.parse_args()

    conn = connect()
    if conn is None:
        return 1

    try:
        if args.watch:
            prev_events = 0
            prev_outcomes = 0
            try:
                while True:
                    total_events = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
                    total_outcomes = conn.execute("SELECT COUNT(*) FROM execution_outcomes").fetchone()[0]

                    new_events = total_events - prev_events
                    new_outcomes = total_outcomes - prev_outcomes

                    if new_events > 0 or new_outcomes > 0:
                        print(f"[{time.strftime('%H:%M:%S')}] "
                              f"+{new_events} eventos  +{new_outcomes} outcomes  "
                              f"(total: {total_events}ev / {total_outcomes}oc)")
                        prev_events = total_events
                        prev_outcomes = total_outcomes

                    time.sleep(5)
            except KeyboardInterrupt:
                print("\n[watch interrompido]")
        elif args.last:
            print_last_entries(conn, model=args.model, n=args.last)
        else:
            print_summary(conn)
    finally:
        conn.close()

    return 0


if __name__ == "__main__":
    exit(main())
