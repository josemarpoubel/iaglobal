# memory/backup_manager.py

import tarfile
import time
import datetime
import os

from typing import Optional

from pathlib import Path

from iaglobal._paths import DATA_ROOT, BACKUP_DIR

from iaglobal.utils.logger import logger

class MemoryManager:
    """
    Gerenciador de snapshots autônomo para a biblioteca de memória.
    Gerencia o ciclo de vida de backups de forma segura e atômica.
    """
    def __init__(self, data_path: str | None = None, backup_path: str | None = None):
        from iaglobal._paths import DATA_ROOT, BACKUP_DIR
        self.data_path = Path(data_path or DATA_ROOT)
        self.backup_path = Path(backup_path or BACKUP_DIR)
        
        # Garante que a estrutura necessária exista
        self.backup_path.mkdir(parents=True, exist_ok=True)
        
        self.min_backup_interval = 3600  # 1 hora padrão
        self.last_backup_time = 0

    def create_snapshot(self):
        """Método unificado para disparar o backup."""
        logger.info(f"💾 Iniciando snapshot de memória...")
        # Chame a lógica de backup que você já tem aqui dentro
        # Exemplo: self.run_backup() ou o código que você já usa para o .tar.gz
        try:
            # Sua lógica atual de backup aqui
            pass
        except Exception as e:
            logger.error(f"Erro ao criar snapshot: {e}")    
    
    def trigger_safe_snapshot(self, force: bool = False) -> None:
        """
        Executa snapshot da pasta de dados se o intervalo for respeitado.
        Pode ser forçado pelo orquestrador em eventos críticos (shutdown).
        """
        current_time = time.time()
        
        if not force and (current_time - self.last_backup_time < self.min_backup_interval):
            return

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        snapshot_file = self.backup_path / f"snap_{timestamp}.tar.gz"
        
        try:
            logger.info(f"Iniciando snapshot de memória em: {snapshot_file}")
            with tarfile.open(snapshot_file, "w:gz") as tar:
                # Adiciona todo o conteúdo da pasta data/
                # arcname garante que a estrutura interna do tar seja limpa
                tar.add(self.data_path, arcname=self.data_path.name)
            
            self.last_backup_time = current_time
            self._prune_old_backups(max_files=5)
            logger.info("Snapshot concluído com sucesso.")
            
        except Exception as e:
            logger.error(f"Falha crítica ao criar snapshot de memória: {e}")
            raise e

    def _prune_old_backups(self, max_files: int) -> None:
        """Remove snapshots antigos para evitar estouro de disco."""
        backups = sorted(
            self.backup_path.glob("*.tar.gz"), 
            key=lambda f: f.stat().st_mtime
        )
        
        while len(backups) > max_files:
            oldest = backups.pop(0)
            try:
                oldest.unlink()
                logger.debug(f"Snapshot antigo removido: {oldest.name}")
            except OSError as e:
                logger.warning(f"Erro ao remover snapshot antigo {oldest.name}: {e}")

    def force_emergency_backup(self) -> None:
        """Método de conveniência para Shutdown Hooks."""
        logger.warning("Executando backup de emergência antes de encerrar.")
        self.trigger_safe_snapshot(force=True)

    def realizar_backup():
        """Compacta a pasta de dados inteira com um timestamp."""
        
        # Define o nome do arquivo com data e hora
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = BACKUP_DIR / f"backup_memoria_{timestamp}.tar.gz"
        
        try:
            logger.info(f"📦 Iniciando backup de {DATA_ROOT} para {backup_filename}...")
            
            with tarfile.open(backup_filename, "w:gz") as tar:
                # Adiciona a pasta de dados, excluindo a própria pasta de backups 
                # para evitar recursão infinita
                tar.add(DATA_ROOT, arcname=os.path.basename(DATA_ROOT), 
                        filter=lambda x: None if "memory_backups" in x.name else x)
            
            logger.info(f"✅ Backup concluído com sucesso: {backup_filename}")
            return str(backup_filename)
            
        except Exception as e:
            logger.error(f"💥 Falha ao realizar backup: {e}")
            return None

    def limpar_backups_antigos(self, dias=30):
        """Remove backups com mais de X dias para liberar espaço."""
        limite = datetime.datetime.now() - datetime.timedelta(days=dias)
        
        for arquivo in BACKUP_DIR.glob("backup_memoria_*.tar.gz"):
            # Extrai o timestamp do nome do arquivo
            data_arquivo = datetime.datetime.strptime(arquivo.name.split('_')[2], "%Y%m%d")
            if data_arquivo < limite:
                os.remove(arquivo)
                logger.info(f"🗑️ Backup antigo removido: {arquivo.name}")

if __name__ == "__main__":
    realizar_backup()        
