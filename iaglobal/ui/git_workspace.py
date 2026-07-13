"""
iaglobal/ui/git_workspace.py
=============================
Workspace Git isolado por tarefa — manipulação de branches, commits e diretórios
de trabalho temporários para cada execução do agente.
"""

import os
import tempfile
from pathlib import Path
from typing import Optional

from iaglobal.utils.logger import logger

try:
    import git

    GITPYTHON_AVAILABLE = True
except ImportError:
    GITPYTHON_AVAILABLE = False
    logger.warning("[UI] GitPython não instalado — manipulação de Git via subprocess")


class GitWorkspaceError(Exception):
    """Erro na operação de workspace Git."""


class GitWorkspace:
    """Gerencia um workspace Git isolado para uma tarefa específica.

    Ciclo de vida:
        1. cria diretório temporário
        2. inicializa repo Git
        3. cria branch isolada
        4. executa tarefa no contexto do workspace
        5. commita resultados
        6. retorna caminho para inspeção/merge
    """

    def __init__(
        self, base_path: Optional[Path] = None, repo_url: Optional[str] = None
    ):
        from iaglobal._paths import PROJECT_ROOT

        self.base_path = base_path or PROJECT_ROOT
        self.repo_url = repo_url
        self._workspace_dir: Optional[Path] = None
        self._repo = None
        self._branch_name: Optional[str] = None

    def create(self, task_id: str) -> Path:
        """Cria workspace isolado para uma tarefa."""
        return self._create_sync(task_id)

    def _create_sync(self, task_id: str) -> Path:
        """Cria workspace de forma síncrona (executado em thread pool)."""
        # Sanitiza task_id para nome de branch válido
        safe_branch = (
            "iaglobal/task-"
            + "".join(c if c.isalnum() or c in "-_" else "_" for c in task_id)[:32]
        )
        self._branch_name = safe_branch

        # Cria diretório temporário
        temp_root = Path(tempfile.gettempdir()) / "iaglobal-workspaces"
        temp_root.mkdir(parents=True, exist_ok=True)

        workspace_name = f"ws-{task_id[:8]}-{os.getpid()}"
        self._workspace_dir = temp_root / workspace_name
        self._workspace_dir.mkdir(parents=True, exist_ok=True)

        try:
            if GITPYTHON_AVAILABLE:
                self._repo = git.Repo.init(self._workspace_dir)
                # Cria arquivo inicial para permitir commit
                readme = self._workspace_dir / "README.md"
                readme.write_text(
                    f"# IAGLOBAL Workspace\n\nTask: {task_id}\n\nBranch: {safe_branch}\n"
                )
                self._repo.index.add(["README.md"])
                self._repo.index.commit("chore: initial workspace commit [skip ci]")

                # Cria branch isolada
                self._repo.create_head(safe_branch)
                logger.info(
                    "[GIT] Workspace criado: %s (branch: %s)",
                    self._workspace_dir,
                    safe_branch,
                )
            else:
                # Fallback via subprocess
                self._init_git_sync(safe_branch)
                logger.info(
                    "[GIT] Workspace criado via subprocess: %s", self._workspace_dir
                )

        except Exception as e:
            logger.error("[GIT] Falha ao criar workspace: %s", e)
            raise GitWorkspaceError(f"Falha ao criar workspace Git: {e}")

        return self._workspace_dir

    def _init_git_sync(self, branch_name: str) -> None:
        """Fallback para inicialização Git via subprocess."""
        import subprocess

        cmds = [
            ["git", "init"],
            ["git", "config", "user.email", "iaglobal@localhost"],
            ["git", "config", "user.name", "IAGlobal Agent"],
            ["git", "checkout", "-b", branch_name],
        ]

        for cmd in cmds:
            subprocess.run(
                cmd, cwd=self._workspace_dir, check=True, capture_output=True
            )

        readme = self._workspace_dir / "README.md"
        readme.write_text(f"# IAGLOBAL Workspace\nBranch: {branch_name}\n")
        subprocess.run(
            ["git", "add", "README.md"],
            cwd=self._workspace_dir,
            check=True,
            capture_output=True,
        )
        subprocess.run(
            ["git", "commit", "-m", "chore: initial workspace commit [skip ci]"],
            cwd=self._workspace_dir,
            check=True,
            capture_output=True,
        )

    def commit_changes(self, message: str, files: Optional[list] = None) -> bool:
        """Commita alterações no workspace."""
        if not self._workspace_dir or not self._workspace_dir.exists():
            raise GitWorkspaceError("Workspace não inicializado")

        return self._commit_sync(message, files)

    def _commit_sync(self, message: str, files: Optional[list]) -> bool:
        """Commit síncrono (executado em thread pool)."""
        try:
            if GITPYTHON_AVAILABLE and self._repo:
                if files:
                    self._repo.index.add(files)
                else:
                    # Adiciona todos os arquivos modificados/novos
                    self._repo.git.add(A=True)
                self._repo.index.commit(message)
                logger.info("[GIT] Commit criado: %s", message[:60])
            else:
                self._commit_sync_fallback(message, files)
            return True
        except Exception as e:
            logger.error("[GIT] Falha no commit: %s", e)
            return False

    def _commit_sync_fallback(self, message: str, files: Optional[list]) -> None:
        """Fallback de commit via subprocess."""
        import subprocess

        if files:
            subprocess.run(
                ["git", "add"] + files,
                cwd=self._workspace_dir,
                check=True,
                capture_output=True,
            )
        else:
            subprocess.run(
                ["git", "add", "."],
                cwd=self._workspace_dir,
                check=True,
                capture_output=True,
            )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self._workspace_dir,
            check=True,
            capture_output=True,
        )

    def get_diff(self) -> str:
        """Retorna diff das alterações não commitadas."""
        if not self._workspace_dir or not self._workspace_dir.exists():
            return ""

        return self._get_diff_sync()

    def _get_diff_sync(self) -> str:
        """Diff síncrono."""
        try:
            if GITPYTHON_AVAILABLE and self._repo:
                # Captura tanto staged quanto untracked
                changed = []
                for item in self._repo.index.diff("HEAD"):
                    changed.append(
                        f"diff --git a/{item.a_path} b/{item.b_path}\n{item.diff}"
                    )
                for untracked in self._repo.untracked_files:
                    content = (self._workspace_dir / untracked).read_text(
                        errors="ignore"
                    )[:200]
                    changed.append(
                        f"new file mode 100644\nindex 0000000..0000000\n--- /dev/null\n+++ b/{untracked}\n@@ -0,0 +1 @@\n+{content}"
                    )
                return "\n".join(changed)
            else:
                import subprocess

                result = subprocess.run(
                    ["git", "diff", "--cached"],
                    cwd=self._workspace_dir,
                    capture_output=True,
                    text=True,
                )
                if result.stdout.strip():
                    return result.stdout
                result2 = subprocess.run(
                    ["git", "status", "--porcelain"],
                    cwd=self._workspace_dir,
                    capture_output=True,
                    text=True,
                )
                return result2.stdout
        except Exception:
            return ""

    def get_recent_commits(self, count: int = 5) -> list:
        """Retorna commits recentes."""
        if not self._workspace_dir or not self._workspace_dir.exists():
            return []

        return self._get_commits_sync(count)

    def _get_commits_sync(self, count: int) -> list:
        """Commits síncronos."""
        try:
            if GITPYTHON_AVAILABLE and self._repo:
                commits = []
                for c in list(self._repo.iter_commits("HEAD", max_count=count)):
                    commits.append(
                        {
                            "hash": c.hexsha[:8],
                            "message": c.message.strip(),
                            "author": str(c.author),
                            "date": c.committed_datetime.isoformat(),
                        }
                    )
                return commits
            else:
                import subprocess

                result = subprocess.run(
                    ["git", "log", f"-{count}", "--pretty=format:%h|%s|%an|%ai"],
                    cwd=self._workspace_dir,
                    capture_output=True,
                    text=True,
                )
                commits = []
                for line in result.stdout.strip().split("\n"):
                    if "|" in line:
                        parts = line.split("|", 3)
                        if len(parts) == 4:
                            commits.append(
                                {
                                    "hash": parts[0],
                                    "message": parts[1],
                                    "author": parts[2],
                                    "date": parts[3],
                                }
                            )
                return commits
        except Exception:
            return []

    def cleanup(self) -> None:
        """Remove workspace temporário."""
        if self._workspace_dir and self._workspace_dir.exists():
            try:
                import shutil

                shutil.rmtree(self._workspace_dir)
                logger.info("[GIT] Workspace removido: %s", self._workspace_dir)
            except Exception as e:
                logger.warning("[GIT] Falha ao remover workspace: %s", e)
            finally:
                self._workspace_dir = None
                self._repo = None
                self._branch_name = None

    @property
    def path(self) -> Optional[Path]:
        """Caminho absoluto do workspace."""
        return self._workspace_dir

    @property
    def branch(self) -> Optional[str]:
        """Nome da branch atual."""
        return self._branch_name
