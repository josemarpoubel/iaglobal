import asyncio


from iaglobal.cli.main import run_cli

from iaglobal.core.env_loader import load_env

load_env()

if __name__ == "__main__":
    asyncio.run(run_cli())
