"""
Conversor de dados CBOR/DB para JSON
Permite que o servidor UI leia os dados reais do sistema iaglobal
"""

import json
import cbor2
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

# Caminhos base
MEMORY_DIR = Path(__file__).parent.parent / "memory" / "data"
JSON_DIR = MEMORY_DIR / "json"
CBOR_DIR = MEMORY_DIR / "cbor"
DB_DIR = MEMORY_DIR / "db"


def read_cbor_file(file_path: Path) -> Any:
    """Lê um arquivo CBOR e retorna o objeto Python"""
    if not file_path.exists():
        return None

    try:
        with open(file_path, "rb") as f:
            data = cbor2.load(f)
        return data
    except Exception as e:
        print(f"Erro ao ler CBOR {file_path}: {e}")
        return None


def convert_cbor_to_json(cbor_data: Any) -> Any:
    """Converte dados CBOR (Python objects) para estrutura JSON-safe"""
    if isinstance(cbor_data, bytes):
        # Bytes podem ser hash ou dados binários
        try:
            return cbor_data.hex()
        except:
            return str(cbor_data)
    elif isinstance(cbor_data, datetime):
        return cbor_data.isoformat()
    elif isinstance(cbor_data, dict):
        return {str(k): convert_cbor_to_json(v) for k, v in cbor_data.items()}
    elif isinstance(cbor_data, (list, tuple)):
        return [convert_cbor_to_json(item) for item in cbor_data]
    elif isinstance(cbor_data, set):
        return list(cbor_data)
    else:
        return cbor_data


def get_execution_history(limit: int = 50) -> List[Dict]:
    """
    Obtém histórico de execuções dos arquivos CBOR de tasks/results
    """
    executions = []

    # Procurar em múltiplas localizações possíveis
    search_dirs = [
        JSON_DIR,
        CBOR_DIR,
        MEMORY_DIR / "tasks",
        MEMORY_DIR / "results",
        MEMORY_DIR,
    ]

    all_files = []
    for search_dir in search_dirs:
        if search_dir.exists():
            # Arquivos CBOR
            all_files.extend(search_dir.glob("*.cbor"))
            # Arquivos JSON
            all_files.extend(search_dir.glob("*.json"))

    # Ordenar por data de modificação (mais recente primeiro)
    all_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)

    for file_path in all_files[:limit]:
        try:
            if file_path.suffix == ".cbor":
                data = read_cbor_file(file_path)
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

            if data:
                # Converter para JSON-safe
                json_data = convert_cbor_to_json(data)

                # Extrair metadados
                execution = {
                    "file": file_path.name,
                    "path": str(file_path.relative_to(MEMORY_DIR.parent)),
                    "timestamp": file_path.stat().st_mtime,
                    "datetime": datetime.fromtimestamp(
                        file_path.stat().st_mtime
                    ).isoformat(),
                    "data": json_data,
                    "type": "cbor" if file_path.suffix == ".cbor" else "json",
                }

                # Tentar extrair informações relevantes
                if isinstance(json_data, dict):
                    if "task_id" in json_data:
                        execution["task_id"] = json_data["task_id"]
                    if "status" in json_data:
                        execution["status"] = json_data["status"]
                    if "result" in json_data:
                        execution["result"] = json_data["result"]
                    if "agent_id" in json_data:
                        execution["agent_id"] = json_data["agent_id"]

                # Normalizar campos esperados pelo frontend
                execution.setdefault("id", execution.get("task_id") or file_path.stem)
                execution.setdefault("task", execution.get("file") or file_path.stem)
                execution.setdefault("status", execution.get("status") or "unknown")

                executions.append(execution)

        except Exception as e:
            # Ignorar arquivos corrompidos
            print(f"Erro ao processar {file_path}: {e}")
            continue

    return executions


def get_agent_status() -> Dict:
    """
    Obtém status dos agentes de arquivos CBOR/JSON
    """
    agents = {}

    # Procurar arquivos de agentes
    agent_files = []
    for pattern in ["**/agents/*.cbor", "**/agents/*.json", "**/*agent*.cbor"]:
        agent_files.extend(MEMORY_DIR.glob(pattern))

    for file_path in agent_files:
        try:
            if file_path.suffix == ".cbor":
                data = read_cbor_file(file_path)
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

            if data and isinstance(data, dict):
                agent_id = data.get("agent_id", file_path.stem)
                agents[agent_id] = {
                    "agent_id": agent_id,
                    "file": file_path.name,
                    "status": data.get("status", "unknown"),
                    "last_update": datetime.fromtimestamp(
                        file_path.stat().st_mtime
                    ).isoformat(),
                    "data": convert_cbor_to_json(data),
                }
        except Exception as e:
            continue

    return {
        "total_agents": len(agents),
        "agents": list(agents.values()),
        "timestamp": datetime.now().isoformat(),
    }


def get_metabolic_state() -> Dict:
    """
    Obtém estado metabólico (pools, energia, etc.)
    """
    metabolic_data = {
        "pools": {},
        "energy": {},
        "timestamp": datetime.now().isoformat(),
    }

    # Procurar arquivos de pools
    pool_files = list(MEMORY_DIR.glob("**/*pool*.cbor")) + list(
        MEMORY_DIR.glob("**/*pool*.json")
    )

    for file_path in pool_files:
        try:
            if file_path.suffix == ".cbor":
                data = read_cbor_file(file_path)
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

            if data:
                pool_name = file_path.stem
                metabolic_data["pools"][pool_name] = {
                    "file": file_path.name,
                    "data": convert_cbor_to_json(data),
                    "last_update": datetime.fromtimestamp(
                        file_path.stat().st_mtime
                    ).isoformat(),
                }
        except Exception as e:
            continue

    # Procurar arquivos de energia/ATP
    energy_files = (
        list(MEMORY_DIR.glob("**/*atp*.cbor"))
        + list(MEMORY_DIR.glob("**/*energy*.cbor"))
        + list(MEMORY_DIR.glob("**/*energia*.cbor"))
    )

    for file_path in energy_files:
        try:
            if file_path.suffix == ".cbor":
                data = read_cbor_file(file_path)
            else:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

            if data:
                energy_name = file_path.stem
                metabolic_data["energy"][energy_name] = {
                    "file": file_path.name,
                    "data": convert_cbor_to_json(data),
                    "last_update": datetime.fromtimestamp(
                        file_path.stat().st_mtime
                    ).isoformat(),
                }
        except Exception as e:
            continue

    return metabolic_data


def get_epigenetic_markers(agent_id: Optional[str] = None) -> Dict:
    """
    Obtém marcadores epigenéticos
    """
    markers = []

    # Procurar arquivos epigenéticos
    epi_files = (
        list(MEMORY_DIR.glob("**/epigenetic/**/*.cbor"))
        + list(MEMORY_DIR.glob("**/*epigenetic*.cbor"))
        + list(MEMORY_DIR.glob("**/*marker*.cbor"))
    )

    for file_path in epi_files:
        try:
            data = read_cbor_file(file_path)
            if data:
                marker_data = convert_cbor_to_json(data)

                # Filtrar por agent_id se especificado
                if agent_id and isinstance(marker_data, dict):
                    if marker_data.get("agent_id") != agent_id:
                        continue

                markers.append(
                    {
                        "file": file_path.name,
                        "timestamp": datetime.fromtimestamp(
                            file_path.stat().st_mtime
                        ).isoformat(),
                        "data": marker_data,
                    }
                )
        except Exception as e:
            continue

    return {
        "total_markers": len(markers),
        "markers": markers,
        "timestamp": datetime.now().isoformat(),
    }


if __name__ == "__main__":
    # Teste rápido
    print("=== Teste do Conversor ===")

    print("\n1. Execuções:")
    execs = get_execution_history(5)
    print(f"   Encontradas {len(execs)} execuções")
    if execs:
        print(f"   Mais recente: {execs[0].get('datetime', 'N/A')}")

    print("\n2. Agentes:")
    agents = get_agent_status()
    print(f"   Total: {agents['total_agents']} agentes")

    print("\n3. Estado Metabólico:")
    metabolic = get_metabolic_state()
    print(f"   Pools: {len(metabolic['pools'])}")
    print(f"   Energia: {len(metabolic['energy'])}")

    print("\n4. Marcadores Epigenéticos:")
    epi = get_epigenetic_markers()
    print(f"   Total: {epi['total_markers']} marcadores")

    print("\n=== Conversor OK ===")
