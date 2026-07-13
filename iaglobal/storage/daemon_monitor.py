# daemon_monitor.py

# daemon_monitor.py

import time
import os

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from iaglobal.storage.converter import DataBridge
from iaglobal.agents.multi_agent import resolver
from iaglobal.utils.logger import logger

from iaglobal._paths import MONITORED_DIR

PASTA_MONITORADA = MONITORED_DIR


def aguardar_arquivo_estavel(path, tentativas=10, intervalo=0.5):
    """
    Aguarda até que o tamanho do arquivo pare de mudar,
    indicando que a escrita terminou.
    """

    tamanho_anterior = -1

    for tentativa in range(tentativas):
        try:
            tamanho_atual = os.path.getsize(path)

            logger.debug(
                f"📦 Verificando estabilidade do arquivo "
                f"({tentativa + 1}/{tentativas}) -> "
                f"{tamanho_atual} bytes"
            )

            if tamanho_atual == tamanho_anterior:
                logger.info(f"✅ Arquivo estabilizado: {path}")
                return True

            tamanho_anterior = tamanho_atual
            time.sleep(intervalo)

        except FileNotFoundError:
            logger.warning(f"⚠️ Arquivo não encontrado durante monitoramento: {path}")
            return False

        except Exception as e:
            logger.error(
                f"❌ Erro ao verificar estabilidade do arquivo {path}: {str(e)}",
                exc_info=True,
            )
            return False

    logger.warning(f"⚠️ Arquivo ainda em escrita após espera: {path}")
    return False


class MonitorHandler(FileSystemEventHandler):
    def on_modified(self, event):

        # Ignora diretórios
        if event.is_directory:
            return

        nome_arquivo = os.path.basename(event.src_path)

        # Processa apenas JSONs de sugestão
        if not nome_arquivo.endswith(".json"):
            return

        if "sugestao" not in nome_arquivo.lower():
            return

        logger.info(f"📁 Alteração detectada: {nome_arquivo}")

        # Aguarda estabilização real do arquivo
        if not aguardar_arquivo_estavel(event.src_path):
            logger.warning(
                f"⏳ Ignorando processamento pois o arquivo ainda está sendo escrito: "
                f"{nome_arquivo}"
            )
            return

        try:
            # -------------------------------------------------
            # 1. Normalização do JSON
            # -------------------------------------------------
            bridge = DataBridge()

            dados_normalizados = bridge.processar_sugestao(event.src_path)

            if not dados_normalizados:
                logger.warning(
                    f"⚠️ Nenhum dado válido retornado pelo DataBridge "
                    f"para {nome_arquivo}"
                )
                return

            if "task" not in dados_normalizados:
                logger.warning(f"⚠️ Nenhuma task encontrada em {nome_arquivo}")
                return

            task_text = dados_normalizados["task"]

            logger.info(
                f"🚀 Invocando Multi-Agent Resolver para task: '{task_text[:60]}...'"
            )

            # -------------------------------------------------
            # 2. Execução multi-agente
            # -------------------------------------------------
            codigo_final = resolver(task_text, max_iters=3)

            logger.info(f"✨ Processamento concluído com sucesso para {nome_arquivo}")

        except Exception as e:
            logger.error(
                f"❌ Erro crítico ao processar {nome_arquivo}: {str(e)}", exc_info=True
            )


if __name__ == "__main__":
    # Garante existência da pasta
    os.makedirs(PASTA_MONITORADA, exist_ok=True)

    logger.info(f"👁️ Monitorando diretório: {PASTA_MONITORADA}")

    event_handler = MonitorHandler()

    observer = Observer()

    observer.schedule(event_handler, PASTA_MONITORADA, recursive=False)

    observer.start()

    try:
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("🛑 Encerrando daemon monitor...")
        observer.stop()

    observer.join()
