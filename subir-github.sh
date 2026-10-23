#!/usr/bin/env bash
# Sobe este projeto para um repositorio GitHub que VOCE ja criou (vazio).
# Rode DENTRO da pasta gophish-platform.
#
# Uso:
#   bash subir-github.sh git@github.com:SEU_USUARIO/SEU_REPO.git
# ou (https):
#   bash subir-github.sh https://github.com/SEU_USUARIO/SEU_REPO.git
set -e

REPO_URL="$1"
if [ -z "$REPO_URL" ]; then
  echo "Uso: bash subir-github.sh <URL-do-repo-git>"
  exit 1
fi

git init
git add .
git -c user.name="$(git config user.name || echo awareness)" \
    -c user.email="$(git config user.email || echo awareness@local)" \
    commit -m "Plataforma de Awareness (camada sobre o GoPhish)"
git branch -M main
git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"
git push -u origin main
echo "Pronto. Repo atualizado: $REPO_URL"
