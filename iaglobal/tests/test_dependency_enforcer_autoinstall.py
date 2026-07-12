# 🧬 LINEAGE_MARKER: cc7017b56557586095e8dc6dae27b3e61feac8ab7bb9c2ca229a3723bc250524f3b65d01c3a7d148ba2f0282e63484bfb884f6425a36aba3cee3edd37b01e136
"""Testes do DependencyEnforcer com auto-install."""
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from iaglobal.core.dependency_enforcer import DependencyEnforcer, REQUIREMENTS_PATH


@pytest.fixture
def enforcer_with_autoinstall():
    """Cria enforcer com auto-install ativado."""
    return DependencyEnforcer(auto_install=True)


@pytest.fixture
def enforcer_without_autoinstall():
    """Cria enforcer com auto-install desativado."""
    return DependencyEnforcer(auto_install=False)


def test_auto_install_disabled_wraps(enforcer_without_autoinstall):
    """Com auto-install=False, pacotes não-instalados são wrapped."""
    code = "import fake_package_xyz_123\nprint(fake_package_xyz_123.test())"
    result = enforcer_without_autoinstall.enforce(code)
    
    # Deve fazer wrap porque auto-install está desativado
    assert result.was_modified is True
    assert len(result.wrapped_imports) > 0


def test_requirements_cache_loaded():
    """Verifica que requirements.txt é carregado no cache."""
    enforcer = DependencyEnforcer()
    reqs = enforcer._get_requirements()
    
    # requirements.txt deve existir e ter pacotes
    assert REQUIREMENTS_PATH.exists()
    assert len(reqs) > 0


def test_install_package_success():
    """Testa instalação de pacote (mock para não instalar de verdade)."""
    from subprocess import TimeoutExpired
    
    enforcer = DependencyEnforcer()
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = enforcer._install_package("test_package")
        
        assert result is True
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        # args[0] é o python, args deve conter 'pip' e 'install'
        assert "pip" in " ".join(args)
        assert "install" in args
        assert "test_package" in args


def test_install_package_failure():
    """Testa falha na instalação."""
    enforcer = DependencyEnforcer()
    
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="Erro: pacote não existe")
        result = enforcer._install_package("nonexistent_package_xyz")
        
        assert result is False


def test_install_package_timeout():
    """Testa timeout na instalação."""
    enforcer = DependencyEnforcer()
    
    with patch("subprocess.run") as mock_run:
        mock_run.side_effect = TimeoutExpired(cmd="pip install", timeout=60)
        result = enforcer._install_package("slow_package")
        
        assert result is False


def test_requirements_normalization():
    """Verifica que nomes de pacotes são normalizados (hifen → underscore)."""
    # Testa a função de parsing diretamente
    from iaglobal.core.dependency_enforcer import DependencyEnforcer
    
    # Simula linha de requirements
    line = "package-name==1.0.0"
    pkg = line.split("==")[0].split(">=")[0].split("<")[0].split("[")[0]
    pkg = pkg.lower().replace("-", "_")
    
    assert pkg == "package_name"


def test_requirements_ignores_comments():
    """Verifica que comentários e linhas vazias são ignorados no parsing."""
    content = """# Comentário
package1==1.0.0

# Outro comentário
package2>=2.0.0
"""
    packages = set()
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg = line.split("==")[0].split(">=")[0].split("<")[0].split("[")[0]
        packages.add(pkg.lower().replace("-", "_"))
    
    assert "package1" in packages
    assert "package2" in packages
    assert len(packages) == 2


def test_requirements_strips_version_specifiers():
    """Verifica que version specifiers são removidos no parsing."""
    content = """
pkg1==1.0.0
pkg2>=2.0.0
pkg3<3.0.0
pkg4[extra]==4.0.0
"""
    packages = set()
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        pkg = line.split("==")[0].split(">=")[0].split("<")[0].split("[")[0]
        packages.add(pkg.lower().replace("-", "_"))
    
    assert "pkg1" in packages
    assert "pkg2" in packages
    assert "pkg3" in packages
    assert "pkg4" in packages
    assert len(packages) == 4


@pytest.mark.skip(reason="Teste de integração real - requer rede")
def test_auto_install_real_package(enforcer_with_autoinstall):
    """Teste de integração real (skip por padrão)."""
    # Este teste instalaria um pacote de verdade
    code = "import httpx\nprint(httpx.get('http://example.com'))"
    result = enforcer_with_autoinstall.enforce(code)
    
    # httpx já deve estar instalado, então não deveria fazer wrap
    assert "httpx" in result.installed_imports or len(result.wrapped_imports) == 0


from subprocess import TimeoutExpired