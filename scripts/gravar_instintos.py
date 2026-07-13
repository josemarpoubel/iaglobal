#!/usr/bin/env python3
"""
Script para gravar os 12 Instintos Universais (Leis de Holliwell + Axiomas Biológicos)
no diretório 01_Instincts do Obsidian Vault.
"""

import asyncio
from pathlib import Path
from datetime import datetime, UTC

from iaglobal.obsidian.subconsciousapi import SubconsciousAPI
from iaglobal.obsidian.omnimind import LEIS_HOLLIWELL, AXIOMAS_BIOLOGICOS


async def gravar_instintos():
    """Grava todos os instintos no vault."""
    api = SubconsciousAPI()

    # Gravar as 11 Leis de Holliwell
    for i, lei in enumerate(LEIS_HOLLIWELL, 1):
        nome = f"Lei_{i:02d}_{lei.split(':')[0].replace('Lei do ', '').replace('Lei da ', '').replace('Lei ', '').replace(' ', '_')}"
        await api.escrever_instinto(
            nome=nome,
            conteudo=lei
        )
        print(f"✅ Instinto gravado: {nome}")

    # Gravar os 8 Axiomas Biológicos
    for i, axioma in enumerate(AXIOMAS_BIOLOGICOS, 1):
        nome = f"Axioma_{i:02d}_{axioma.split(':')[0].replace('Lei da ', '').replace('Axioma da ', '').replace('Axioma de ', '').replace(' ', '_')}"
        await api.escrever_instinto(
            nome=nome,
            conteudo=axioma
        )
        print(f"✅ Instinto gravado: {nome}")

    # Atualizar mapa sináptico
    await api.atualizar_mapa_conexoes()
    print("✅ Mapa sináptico atualizado")


def main():
    """Entry point para CLI."""
    asyncio.run(gravar_instintos())


if __name__ == "__main__":
    main()