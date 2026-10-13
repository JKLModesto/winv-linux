#!/usr/bin/env bash
# ==============================================================================
# Instalador universal do winv-linux
# Suporta: Linux Mint (Cinnamon/MATE/XFCE), Ubuntu, Zorin OS, Pop!_OS e
# demais distros baseadas em Debian/Ubuntu com GNOME, Cinnamon, MATE ou XFCE.
# ==============================================================================

set -e

GREEN='\033[0;32m'; BLUE='\033[0;34m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'

INSTALL_DIR="$HOME/.local/share/winv-linux"
BIN_DIR="$HOME/.local/bin"
SYSTEMD_USER_DIR="$HOME/.config/systemd/user"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CMD="$BIN_DIR/winv-linux --popup"
NAME="Histórico da Área de Transferência (Win+V)"

# ------------------------------------------------------------------------------
# Detecção do ambiente
# ------------------------------------------------------------------------------
DESKTOP_RAW="${XDG_CURRENT_DESKTOP:-${DESKTOP_SESSION:-unknown}}"
DESKTOP_LC="$(echo "$DESKTOP_RAW" | tr '[:upper:]' '[:lower:]')"
case "$DESKTOP_LC" in
    *cinnamon*)            DE="cinnamon" ;;
    *gnome*|*zorin*|*unity*|*ubuntu*|*pop*) DE="gnome" ;;
    *mate*)                DE="mate" ;;
    *xfce*)                DE="xfce" ;;
    *)                     DE="unknown" ;;
esac
SESSION="${XDG_SESSION_TYPE:-x11}"
DISTRO="$( (. /etc/os-release 2>/dev/null && echo "$PRETTY_NAME") || echo "Linux")"

# Helper Python para manipular listas GVariant ('as')
py_list() { # $1=lista atual  $2=add|remove  $3=item
    python3 - "$1" "$2" "$3" <<'EOF'
import sys, ast
raw, op, item = sys.argv[1].strip(), sys.argv[2], sys.argv[3]
try:
    lst = [] if raw.startswith('@as') else list(ast.literal_eval(raw))
except Exception:
    lst = []
lst = [x for x in lst if x != item]
if op == 'add':
    lst.append(item)
print(str(lst))
EOF
}

GNOME_MK="org.gnome.settings-daemon.plugins.media-keys"
GNOME_PATH="/org/gnome/settings-daemon/plugins/media-keys/custom-keybindings/winv/"
CIN_PATH="/org/cinnamon/desktop/keybindings/custom-keybindings/custom-winv/"

# ------------------------------------------------------------------------------
# Atalhos por ambiente
# ------------------------------------------------------------------------------
register_shortcut() {
    case "$DE" in
    cinnamon)
        local S="org.cinnamon.desktop.keybindings.custom-keybinding:$CIN_PATH"
        gsettings set "$S" name "$NAME"
        gsettings set "$S" command "$CMD"
        gsettings set "$S" binding "['<Super>v']"
        local CUR; CUR=$(gsettings get org.cinnamon.desktop.keybindings custom-list)
        gsettings set org.cinnamon.desktop.keybindings custom-list "$(py_list "$CUR" remove custom-winv)"
        sleep 0.2
        gsettings set org.cinnamon.desktop.keybindings custom-list "$(py_list "$CUR" add custom-winv)"
        ;;
    gnome)
        # O GNOME Shell (Ubuntu/Zorin) usa Super+V para abrir a bandeja de
        # notificações. Liberamos o atalho mantendo Super+M para essa função.
        if gsettings list-keys org.gnome.shell.keybindings 2>/dev/null | grep -q toggle-message-tray; then
            gsettings set org.gnome.shell.keybindings toggle-message-tray "['<Super>m']"
        fi
        local S="$GNOME_MK.custom-keybinding:$GNOME_PATH"
        gsettings set "$S" name "$NAME"
        gsettings set "$S" command "$CMD"
        gsettings set "$S" binding "<Super>v"
        local CUR; CUR=$(gsettings get "$GNOME_MK" custom-keybindings)
        gsettings set "$GNOME_MK" custom-keybindings "$(py_list "$CUR" add "$GNOME_PATH")"
        ;;
    mate)
        local P="/org/mate/desktop/keybindings/winv/"
        dconf write "${P}name" "'$NAME'"
        dconf write "${P}action" "'$CMD'"
        dconf write "${P}binding" "'<Mod4>v'"
        ;;
    xfce)
        xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/<Super>v" \
            -n -t string -s "$CMD" 2>/dev/null || \
        xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/<Super>v" -s "$CMD"
        ;;
    *)
        echo -e "${YELLOW}Ambiente '$DESKTOP_RAW' não reconhecido. Crie manualmente um atalho:${NC}"
        echo -e "  Tecla: Super+V   Comando: $CMD"
        return 1
        ;;
    esac
}

unregister_shortcut() {
    # Remove de todos os ambientes, ignorando erros
    if gsettings list-schemas 2>/dev/null | grep -q '^org.cinnamon.desktop.keybindings$'; then
        local CUR; CUR=$(gsettings get org.cinnamon.desktop.keybindings custom-list)
        gsettings set org.cinnamon.desktop.keybindings custom-list "$(py_list "$CUR" remove custom-winv)" || true
        dconf reset -f "$CIN_PATH" 2>/dev/null || true
    fi
    if gsettings list-schemas 2>/dev/null | grep -q "^$GNOME_MK\$"; then
        local CUR; CUR=$(gsettings get "$GNOME_MK" custom-keybindings)
        gsettings set "$GNOME_MK" custom-keybindings "$(py_list "$CUR" remove "$GNOME_PATH")" || true
        dconf reset -f "$GNOME_PATH" 2>/dev/null || true
        gsettings reset org.gnome.shell.keybindings toggle-message-tray 2>/dev/null || true
    fi
    dconf reset -f /org/mate/desktop/keybindings/winv/ 2>/dev/null || true
    command -v xfconf-query >/dev/null && \
        xfconf-query -c xfce4-keyboard-shortcuts -p "/commands/custom/<Super>v" -r 2>/dev/null || true
}

# ------------------------------------------------------------------------------
# Migração da instalação antiga (winv-mint -> winv-linux)
# ------------------------------------------------------------------------------
migrate_legacy() {
    if [ -f "$SYSTEMD_USER_DIR/winv-mint.service" ] || [ -e "$HOME/.local/bin/winv-mint" ]; then
        echo -e "${YELLOW}Removendo instalação antiga (winv-mint)...${NC}"
        systemctl --user disable --now winv-mint.service 2>/dev/null || true
        rm -f "$SYSTEMD_USER_DIR/winv-mint.service" "$HOME/.local/bin/winv-mint"
        rm -rf "$HOME/.local/share/winv-mint"
        systemctl --user daemon-reload
    fi
}

echo -e "${BLUE}======================================================${NC}"
echo -e "${BLUE}           Instalador universal do winv-linux          ${NC}"
echo -e "${BLUE}======================================================${NC}"
echo -e "Sistema: ${YELLOW}$DISTRO${NC} | Desktop: ${YELLOW}$DESKTOP_RAW ($DE)${NC} | Sessão: ${YELLOW}$SESSION${NC}"

# ------------------------------------------------------------------------------
# Desinstalação
# ------------------------------------------------------------------------------
if [ "$1" == "--uninstall" ]; then
    migrate_legacy
    echo -e "${YELLOW}[1/3] Parando serviço...${NC}"
    systemctl --user disable --now winv-linux.service 2>/dev/null || true
    rm -f "$SYSTEMD_USER_DIR/winv-linux.service"
    systemctl --user daemon-reload
    echo -e "${YELLOW}[2/3] Removendo atalhos...${NC}"
    unregister_shortcut
    echo -e "${YELLOW}[3/3] Removendo arquivos...${NC}"
    rm -f "$BIN_DIR/winv-linux"; rm -rf "$INSTALL_DIR"
    echo -e "${GREEN}Desinstalação concluída!${NC}"
    exit 0
fi

if ! command -v apt-get >/dev/null; then
    echo -e "${RED}Este instalador requer uma distro baseada em Debian/Ubuntu (apt).${NC}"
    exit 1
fi

migrate_legacy

# 1. Dependências
echo -e "\n${BLUE}[1/5] Verificando dependências (APT)...${NC}"
REQUIRED_PKGS=(python3 python3-gi gir1.2-gtk-3.0 gir1.2-wnck-3.0 xdotool x11-utils python3-xlib dconf-cli)
MISSING_PKGS=()
for pkg in "${REQUIRED_PKGS[@]}"; do
    dpkg -s "$pkg" >/dev/null 2>&1 || MISSING_PKGS+=("$pkg")
done
if [ ${#MISSING_PKGS[@]} -gt 0 ]; then
    echo -e "${YELLOW}Instalando: ${MISSING_PKGS[*]}${NC}"
    sudo apt-get update -qq
    sudo apt-get install -y "${MISSING_PKGS[@]}"
else
    echo -e "${GREEN}Todas as dependências já estão instaladas.${NC}"
fi

# 2. Arquivos
echo -e "\n${BLUE}[2/5] Copiando arquivos...${NC}"
mkdir -p "$INSTALL_DIR" "$BIN_DIR"
rm -rf "$INSTALL_DIR/winv"
cp -r "$SCRIPT_DIR/winv" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/bin/winv-linux" "$BIN_DIR/winv-linux"
chmod +x "$BIN_DIR/winv-linux"
if [[ ":$PATH:" != *":$HOME/.local/bin:"* ]] && ! grep -q '.local/bin' "$HOME/.bashrc"; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
fi

# 3. Serviço systemd
echo -e "\n${BLUE}[3/5] Configurando serviço systemd do usuário...${NC}"
mkdir -p "$SYSTEMD_USER_DIR"
cp "$SCRIPT_DIR/systemd/winv-linux.service" "$SYSTEMD_USER_DIR/winv-linux.service"
# Garante que o systemd do usuário conheça a sessão gráfica atual
systemctl --user import-environment DISPLAY XAUTHORITY WAYLAND_DISPLAY XDG_SESSION_TYPE XDG_CURRENT_DESKTOP 2>/dev/null || true
systemctl --user daemon-reload
systemctl --user enable winv-linux.service
systemctl --user restart winv-linux.service
echo -e "${GREEN}Serviço iniciado!${NC}"

# 4. Atalho
echo -e "\n${BLUE}[4/5] Registrando atalho Super+V ($DE)...${NC}"
if register_shortcut; then
    echo -e "${GREEN}Atalho Super+V registrado!${NC}"
fi

# 5. Validação
echo -e "\n${BLUE}[5/5] Validando daemon...${NC}"
sleep 1
if "$BIN_DIR/winv-linux" --status | grep -q ATIVO; then
    echo -e "${GREEN}>>> Instalação concluída com sucesso! Pressione Super + V. <<<${NC}"
else
    echo -e "${YELLOW}Daemon inicializando. Verifique com: winv-linux --status${NC}"
fi

if [ "$SESSION" = "wayland" ]; then
    echo -e "\n${YELLOW}AVISO: sessão Wayland detectada.${NC}"
    echo -e "O popup e o histórico funcionam via XWayland, mas a colagem automática"
    echo -e "pode não funcionar em apps nativos Wayland (o item é copiado; use Ctrl+V)."
    echo -e "Para experiência completa, na tela de login clique na engrenagem e"
    echo -e "escolha a sessão ${YELLOW}\"Zorin Desktop on Xorg\"${NC} / ${YELLOW}\"Ubuntu on Xorg\"${NC}."
fi
