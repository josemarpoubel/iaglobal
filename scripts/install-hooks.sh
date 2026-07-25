#!/usr/bin/env bash
# Instala os git hooks versionados em scripts/git-hooks/ em .git/hooks/.
# Deve ser rodado uma vez por clone ou após reset.

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_SRC="$REPO_ROOT/scripts/git-hooks"
HOOKS_DST="$REPO_ROOT/.git/hooks"

if [ ! -d "$HOOKS_SRC" ]; then
    echo "ERRO: $HOOKS_SRC não encontrado." >&2
    exit 1
fi

echo "Instalando hooks em $HOOKS_DST ..."

for hook_file in "$HOOKS_SRC"/*; do
    [ -f "$hook_file" ] || continue
    name="$(basename "$hook_file")"
    dst="$HOOKS_DST/$name"

    rm -f "$dst"
    cp "$hook_file" "$dst"
    chmod +x "$dst"
    echo "  installed: $name"
done

git config core.hooksPath scripts/git-hooks >/dev/null 2>&1 || true

echo ""
echo "Pronto. Proximo git commit em arquivos sensiveis dispara:"
echo "  pre-commit -> scripts/git-hooks/pre-commit (smoke MCP)"
echo ""
echo "Desinstalar: rm /home/kitohamachi/iaglobal-main/.git/hooks/pre-commit"
