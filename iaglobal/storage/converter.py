# storage/converter.py

import os
import cbor2
import json
import logging
import shutil
import hashlib
import tempfile
import copy

from pathlib import Path
from typing import Optional, Any, Dict, List
from datetime import datetime, timezone
from jsonschema import validate, ValidationError
from deepdiff import DeepDiff

from iaglobal._paths import DATA_ROOT

# Sincroniza o logger com o arquivo central utils/logger.py se ele já estiver carregado
logger = logging.getLogger("ia-global")

class DataBridge:
    META_KEY = "_meta"
    READ_ONLY_FIELDS = {"id", "uuid", "checksum"}

    @staticmethod
    def _get_hash(file_path: Path) -> str:
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha.update(chunk)
        return sha.hexdigest()

    @staticmethod
    def _create_backup(file_path: Path):
        counter = 1
        while True:
            backup = file_path.with_suffix(f"{file_path.suffix}.bak{counter}")
            if not backup.exists():
                shutil.copy2(file_path, backup)
                return backup
            counter += 1

    @staticmethod
    def _inject_metadata(data: Any, source: str) -> Any:
        if isinstance(data, dict):
            data = copy.deepcopy(data)
            data[DataBridge.META_KEY] = {
                "source": source,
                "timestamp": datetime.now(timezone.utc).replace(microsecond=0).isoformat() + "Z",
                "schema_version": "1.0",
                "editable": True
            }
        return data

    @staticmethod
    def _remove_metadata(data: Any) -> Any:
        if isinstance(data, dict):
            data = copy.deepcopy(data)
            data.pop(DataBridge.META_KEY, None)
        return data

    @staticmethod
    def cbor_to_json(cbor_path: str, json_path: Optional[str] = None) -> Optional[str]:
        try:
            cbor_file = Path(cbor_path)
            with open(cbor_file, "rb") as f:
                data = cbor2.load(f)
            data = DataBridge._inject_metadata(data, cbor_file.name)
            
            target = json_path or tempfile.NamedTemporaryFile(suffix=".json", delete=False).name
            with open(target, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4, ensure_ascii=False, default=str)
            return target
        except Exception:
            logger.exception("Falha na conversão CBOR->JSON")
            return None

    @staticmethod
    def validar_e_salvar(data: Any, target_path: Path, schema: Optional[Dict] = None):
        if not isinstance(data, (dict, list)):
            raise ValueError("Estrutura inválida.")

        if not DataBridge.validar_integridade_memoria(data if isinstance(data, list) else [data]):
            raise ValueError(f"Integridade de dados falhou para {target_path}. Serialização abortada.")
        
        if schema:
            validate(instance=data, schema=schema)

        sandbox = target_path.with_suffix(target_path.suffix + ".tmp")
        backup = None
        try:
            with open(sandbox, "wb") as f:
                cbor2.dump(data, f)
                f.flush()
                os.fsync(f.fileno())
            
            if target_path.exists():
                backup = DataBridge._create_backup(target_path)
            
            import time, gc
            gc.collect()
            time.sleep(0.05)
            
            sandbox.replace(target_path)
            logger.info(f"Commit atômico concluído: {target_path.name}")
        except Exception as e:
            if backup and backup.exists():
                shutil.copy2(backup, target_path)
            raise e
        finally:
            if sandbox.exists():
                sandbox.unlink(missing_ok=True)

    @staticmethod
    def gerar_schema(cbor_path: str) -> Dict:
        with open(cbor_path, "rb") as f:
            data = cbor2.load(f)
        def inferir(v):
            if isinstance(v, dict): return {"type": "object", "properties": {k: inferir(v) for k, v in v.items()}}
            if isinstance(v, list): return {"type": "array", "items": inferir(v[0]) if v else {}}
            if isinstance(v, bool): return {"type": "boolean"}
            if isinstance(v, int): return {"type": "integer"}
            if isinstance(v, float): return {"type": "number"}
            if v is None: return {"type": "null"}
            return {"type": "string"}
        return {"$schema": "http://json-schema.org/draft-07/schema#", **inferir(data)}

    @staticmethod
    def exportar_schema(cbor_path: str, output_path: str):
        """Exporta o schema inferido para um arquivo JSON na pasta de testes."""
        schema = DataBridge.gerar_schema(cbor_path)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(schema, f, indent=4)
        logger.info(f"Schema exportado para {output_path}")

    # =========================================================================
    # NOVA CAMADA: INGESTÃO E MAPEAMENTO DO EVENT LOOP DE SUGESTÕES
    # =========================================================================
    
    @staticmethod
    def validar_integridade_memoria(dados: Any) -> bool:
        for item in dados:
            if 'embedding' in item and isinstance(item['embedding'], bytes):
                if len(item['embedding']) == 0:
                    return False
        return True
    
    def processar_sugestao(self, json_path: str) -> Optional[Dict[str, Any]]:
        """
        Lê, valida a integridade e normaliza o payload vindo do Daemon Monitor.
        Garante que a chave 'task' exista antes de liberar para os agentes.
        """
        caminho = Path(json_path)
        if not caminho.exists():
            logger.error(f"Arquivo de sugestão sumiu antes do processamento: {json_path}")
            return None

        try:
            with open(caminho, "r", encoding="utf-8") as f:
                payload = json.load(f)

            # Schema validation para prevenir JSON injection
            schema = {
                "type": "object",
                "properties": {
                    "task": {"type": "string"},
                    "tarefa": {"type": "string"},
                    "prompt": {"type": "string"},
                    "input": {"type": "string"},
                    "checksum_origem": {"type": "string"},
                    "timestamp_ingestao": {"type": "string"}
                },
                "additionalProperties": False  # Bloqueia campos extras não definidos
            }
            
            from jsonschema import validate, ValidationError
            validate(instance=payload, schema=schema)

            # Validação defensiva do layout esperado
            if not isinstance(payload, dict):
                logger.warning(f"Formato inválido em {caminho.name}: Esperava um objeto JSON.")
                return None

            # Normalização de chaves flexíveis (aceita 'task', 'tarefa', 'prompt' ou 'input')
            task_text = None
            for key in ["task", "tarefa", "prompt", "input"]:
                if key in payload and str(payload[key]).strip():
                    task_text = str(payload[key]).strip()
                    break

            if not task_text:
                logger.warning(f"Ignorando arquivo {caminho.name}: Nenhuma string de tarefa/task foi localizada.")
                return None

            # Adiciona metadados de auditoria interna para rastreio
            dados_normalizados = {
                "task": task_text,
                "checksum_origem": self._get_hash(caminho),
                "timestamp_ingestao": datetime.now(timezone.utc).isoformat() + "Z"
            }
            
            logger.info(f"✔ Payload validado com sucesso pelo DataBridge. Checksum: {dados_normalizados['checksum_origem'][:8]}")
            return dados_normalizados

        except json.JSONDecodeError:
            logger.error(f"Erro crítico de sintaxe JSON ao ler o arquivo: {caminho.name}")
            return None
        except Exception as e:
            logger.error(f"Falha inesperada no pipeline de ingestão do DataBridge: {str(e)}")
            return None

    # =========================================================================
    # CONECTORES ADICIONAIS: PONTE ATÔMICA SQLITE <-> CBOR2 PARA O PIPELINE
    # =========================================================================
    
    @staticmethod
    def sincronizar_sqlite_para_cbor(db_name: str, table_name: str, cbor_filename: str) -> None:
        import sqlite3
        import re
        
        memory_dir = DATA_ROOT
        
        db_path = memory_dir / db_name
        target_cbor = memory_dir / cbor_filename

        try:
            conn = sqlite3.connect(db_path)
        except Exception as e:
            logger.error(f"Erro na sincronização de {table_name}: {e}")
            return

        try:
            with conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                # Usar parâmetro seguro para nome de tabela (whitelist validation)
                allowed_tables = ["cache", "sessions", "data"]  # ajustar conforme tabelas reais
                if table_name not in allowed_tables:
                    logger.error(f"Tabela {table_name} não permitida")
                    return
                # Sanitização rigorosa do nome da tabela (apenas alfanumérico e underscore)
                if not all(c.isalnum() or c == '_' for c in table_name):
                    logger.error(f"Nome de tabela inválido: {table_name}")
                    return
                cursor.execute(f"SELECT * FROM {table_name}")  # Nomes de tabela não podem usar parameter binding em SQLite
                rows = cursor.fetchall()
        except Exception as e:
            logger.error(f"Erro na sincronização de {table_name}: {e}")
            return
        finally:
            conn.close()

        dados_estruturados = []
        for row in rows:
            item_dict = dict(row)
            
            for chave, valor in item_dict.items():
                if isinstance(valor, str):
                    item_dict[chave] = re.sub(r"\s*\(score=\d+\.\d+\)", "", valor).strip()
                
                if isinstance(valor, bytes):
                    if len(valor) == 0:
                        logger.warning(f"BLOB vazio detectado em {chave} para id {item_dict.get('id')}")
            
            dados_estruturados.append(item_dict)
        
        DataBridge.validar_e_salvar(dados_estruturados, target_cbor)
            
    @staticmethod
    def ler_cbor_para_llm(cbor_filename: str) -> List[Dict[str, Any]]:
        """
        Processo Reverso: Abre o CBOR2 e deserializa com higienização de metadados.
        """
        cbor_path = DATA_ROOT / cbor_filename
        
        if not cbor_path.exists() or cbor_path.stat().st_size == 0:
            return []
            
        try:
            with open(cbor_path, "rb") as f:
                dados = cbor2.load(f)
            
            # Sanitização final antes de entregar para a IA
            if isinstance(dados, list):
                return [DataBridge._remove_metadata(item) for item in dados]
            return [DataBridge._remove_metadata(dados)]
        except Exception as e:
            logger.error(f"Erro ao converter CBOR2 para contexto legível: {e}")
            return []

class AIAssistantBridge:
    @staticmethod
    def prepare_file(file_path: str) -> str:
        converted = DataBridge.cbor_to_json(file_path)
        if not converted: raise RuntimeError(f"Falha ao preparar {file_path}")
        return converted

    @staticmethod
    def processar_edicao_ia(cbor_path: str, json_path: str, schema: Optional[Dict] = None):
        cbor_p, json_p = Path(cbor_path), Path(json_path)
        
        with open(cbor_p, "rb") as f: original = cbor2.load(f)
        with open(json_p, 'r', encoding='utf-8') as f: novo = json.load(f)
            
        # Auditoria sem poluição do _meta
        novo_limpo = DataBridge._remove_metadata(novo)
        diff = DeepDiff(original, novo_limpo, ignore_order=True, verbose_level=0)
        logger.info(f"{len(diff)} categorias modificadas pela IA.")
        
        # Policy Engine: Impedir alteração de campos protegidos
        if isinstance(original, dict):
            for field in DataBridge.READ_ONLY_FIELDS:
                if field in original and original[field] != novo_limpo.get(field):
                    raise PermissionError(f"Campo protegido alterado: {field}")
        
        DataBridge.validar_e_salvar(novo_limpo, cbor_p, schema)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Uso: python converter.py entrada.cbor saida.json e vice-versa")
        sys.exit(1)
    DataBridge.cbor_to_json(sys.argv[1], sys.argv[2])

