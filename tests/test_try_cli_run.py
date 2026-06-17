import sys, os, asyncio
sys.path.insert(0, "/home/user/projeto-iaglobal")

try:
    from iaglobal.cli.main import run_cli
except Exception as e:
    print(f"Import error: {e}")
    sys.exit(1)

async def main():
    task = "crie uma calculadora em php com tema escuro"
    # Configurar sys.argv para parsing do argparse
    sys.argv = ["iaglobal", "run", task]
    try:
        await run_cli()
        print("✅ Pipeline executada até o fim")
    except KeyboardInterrupt:
        print("\n⏹️ Execução interrompida pelo usuário.")
    except Exception as e:
        print(f"\n❌ Erro na execução CLI: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
