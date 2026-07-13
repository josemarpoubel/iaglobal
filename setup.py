import sys
from setuptools import setup
from setuptools.command.develop import develop
from setuptools.command.install import install

def run_automated_tests():
    print("\n" + "="*60)
    print("🚀 INSTALAÇÃO CONCLUÍDA! DISPARANDO PYTEST AUTOMATICAMENTE...")
    print("="*60 + "\n")
    import pytest
    # Executa o pytest na raiz e retorna o código de status
    exit_code = pytest.main(["."])
    if exit_code != 0:
        print("\n❌ Atenção: Alguns testes falharam após a instalação.")
    else:
        print("\n✅ Todos os testes passaram com sucesso pós-instalação!")

class PostDevelopCommand(develop):
    """Gatilho acionado especificamente por: pip install -e ."""
    def run(self):
        develop.run(self)
        run_automated_tests()

class PostInstallCommand(install):
    """Gatilho acionado por instalações normais: pip install ."""
    def run(self):
        install.run(self)
        run_automated_tests()

# O setuptools vai herdar as dependências do seu pyproject.toml automaticamente
setup(
    cmdclass={
        'develop': PostDevelopCommand,
        'install': PostInstallCommand,
    }
)
