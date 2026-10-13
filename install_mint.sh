#!/usr/bin/env bash
# ==============================================================================
# Script de Instalação e Configuração Automatizada do winv-mint
# Desenvolvido para Linux Mint (Cinnamon / X11)
# ==============================================================================

set -e

GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

INSTALL_DIR="$HOME/.local/share/winv-mint"
BIN_DIR="$HOME/.local/bin"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}       Instalador do winv-mint para Linux Mint       ${NC}"
echo -e "${BLUE}  Experiência Nativa do Win+V com Engenharia Reversa  ${NC}"
echo -e "${BLUE}======================================================${NC}"

# Tratamento do modo de desinstalação
if [ "$1" == "--uninstall" ]; then
    echo -e "${YELLOW}[1/4] Parando e desativando serviço systemd...${NC}"
    systemctl --user stop winv-mint.service 2>/dev/null || true
    systemctl --user disable winv-mint.service 2>/dev/null || true
    rm -f "$SYSTEMD_USER_DIR/winv-mint.service"
    systemctl --user daemon-reload

    echo -e "${YELLOW}[2/4] Removendo atalho de teclado no Cinnamon...${NC}"
    CURRENT_LIST=$(gsettings get org.cinnamon.desktop.keybindings custom-list)
    UPDATED_LIST=$(python3 -c "
import ast
lst = ast.literal_eval('$CURRENT_LIST')
if 'custom-winv' in lst:
    lst.remove('custom-winv')
print(str(lst))
")
    gsettings set org.cinnamon.desktop.keybindings custom-list "$UPDATED_LIST"
    dconf reset -f /org/cinnamon/desktop/keybindings/custom-keybindings/custom-winv/ 2>/dev/null || true

    echo -e "${YELLOW}[3/4] Removendo binários e arquivos...${NC}"
    rm -f "$BIN_DIR/winv-mint"
    rm -rf "$INSTALL_DIR"

    echo -e "${GREEN}Desinstalação concluída com sucesso!${NC}"
    exit 0
fi

# 1. Verificação e Instalação de Dependências do Sistema
echo -e "\n${BLUE}[1/5] Verificando dependências do sistema via APT...${NC}"
REQUIRED_PKGS=(
    python3
    python3-gi
    gir1.2-gtk-3.0
    gir1.2-wnck-3.0
    xdotool
    x11-utils
    python3-xlib
)

MISSING_PKGS=()
for pkg in "${REQUIRED_PKGS[@]}"; do
    if ! dpkg -s "$pkg" >/dev/null 2>&1; then
        MISSING_PKGS+=("$pkg")
    fi
done

if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo -e "${YELLOW}Instalando pacotes necessários: ${MISSING_PKGS[*]}${NC}"
    sudo apt-get update -qq
    sudo apt-get install -y "${MISSING_PKGS[@]}"
else
    echo -e "${GREEN}Todas as dependências já estão instaladas.${NC}"
fi

# 2. Instalação dos Arquivos no Diretório do Usuário
echo -e "\n${BLUE}[2/5] Copiando arquivos do winv-mint...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"

cp -r "$SCRIPT_DIR/winv" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/bin/winv-mint" "$BIN_DIR/winv-mint"
chmod +x "$BIN_DIR/winv-mint"

# Garante que ~/.local/bin esteja presente no ~/.bashrc
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]]; then
    if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.bashrc"; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    fi
fi

# 3. Configuração do Serviço systemd (User Session)
echo -e "\n${BLUE}[3/5] Configurando serviço systemd do usuário...${NC}"
mkdir -p "$SYSTEMD_USER_DIR"
cp "$SCRIPT_DIR/systemd/winv-mint.service" "$SYSTEMD_USER_DIR/winv-mint.service"

systemctl --user daemon-reload
systemctl --user enable winv-mint.service
systemctl --user restart winv-mint.service

echo -e "${GREEN}Serviço winv-mint iniciado com sucesso!${NC}"

# 4. Registro Automático do Atalho Global Super+V no Cinnamon
echo -e "\n${BLUE}[4/5] Registrando atalho global Super+V no Cinnamon...${NC}"
CURRENT_LIST=$(gsettings get org.cinnamon.desktop.keybindings custom-list)

NEW_LIST=$(python3 -c "
import ast
try:
    lst = ast.literal_eval('$CURRENT_LIST')
except Exception:
    lst = []
if 'custom-winv' not in lst:
    lst.append('custom-winv')
print(str(lst))
")

gsettings set org.cinnamon.desktop.keybindings custom-list "$NEW_LIST"

KEY_SCHEMA="org.cinnamon.desktop.keybindings.custom-keybinding:/org/cinnamon/desktop/keybindings/custom-keybindings/custom-winv/"
gsettings set "$KEY_SCHEMA" name "Histórico da Área de Transferência (Win+V)"
gsettings set "$KEY_SCHEMA" command "$BIN_DIR/winv-mint --popup"
gsettings set "$KEY_SCHEMA" binding "['<Super>v']"

echo -e "${GREEN}Atalho Super+V registrado no Cinnamon com sucesso!${NC}"

# 5. Validação Final
echo -e "\n${BLUE}[5/5] Validando status do daemon...${NC}"
sleep 1
if "$BIN_DIR/winv-mint" --status >/dev/null 2>&1; then
    echo -e "${GREEN}>>> Instalação finalizada com 100% de sucesso! <<<${NC}"
    echo -e "Agora você já pode pressionar ${YELLOW}Super + V${NC} no Linux Mint!"
else
    echo -e "${YELLOW}Aviso: Daemon em inicialização. Teste com o comando 'winv-mint --status'.${NC}"
fi
