#!/bin/bash
# ==============================================================================
# build_deb.sh - Construtor de Pacote Debian/Ubuntu (.deb) para o winv-linux
# ==============================================================================
set -e

# Lê dinamicamente a versão configurada no código
VERSION=$(python3 -c "from winv.config import VERSION; print(VERSION)" 2>/dev/null || echo "1.0.0")
PKG_NAME="winv-linux"
ARCH="all"
DIST_DIR="dist"
BUILD_DIR="${DIST_DIR}/${PKG_NAME}_${VERSION}_${ARCH}"
DEB_FILE="${DIST_DIR}/${PKG_NAME}_${VERSION}_${ARCH}.deb"

echo "======================================================"
echo "   Construindo pacote .deb oficial: ${PKG_NAME} v${VERSION}   "
echo "======================================================"

echo "[1/6] Limpando ambiente de build anterior..."
rm -rf "${DIST_DIR}"
mkdir -p "${DIST_DIR}"

echo "[2/6] Criando a estrutura de diretórios do sistema..."
mkdir -p "${BUILD_DIR}/usr/bin"
mkdir -p "${BUILD_DIR}/usr/share/${PKG_NAME}"
mkdir -p "${BUILD_DIR}/usr/lib/systemd/user"
mkdir -p "${BUILD_DIR}/usr/share/applications"
mkdir -p "${BUILD_DIR}/etc/xdg/autostart"
mkdir -p "${BUILD_DIR}/DEBIAN"

echo "[3/6] Copiando arquivos do projeto..."
# Código Python em /usr/share/winv-linux/winv
cp -r winv/ "${BUILD_DIR}/usr/share/${PKG_NAME}/"
find "${BUILD_DIR}/usr/share/${PKG_NAME}" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

# Executável CLI em /usr/bin/winv-linux
cp bin/winv-linux "${BUILD_DIR}/usr/bin/winv-linux"
chmod 755 "${BUILD_DIR}/usr/bin/winv-linux"

# Serviço systemd de usuário global (/usr/lib/systemd/user/winv-linux.service)
cat <<'EOF' > "${BUILD_DIR}/usr/lib/systemd/user/winv-linux.service"
[Unit]
Description=winv-linux - Windows Win+V Clipboard History Daemon for Linux
Documentation=https://github.com/JKLModesto/winv-linux

[Service]
Type=simple
ExecStart=/usr/bin/winv-linux --daemon
Restart=on-failure
RestartSec=2s
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
EOF
chmod 644 "${BUILD_DIR}/usr/lib/systemd/user/winv-linux.service"

# Ícone oficial nos formatos freedesktop (hicolor e pixmaps)
mkdir -p "${BUILD_DIR}/usr/share/pixmaps"
cp winv-linux.png "${BUILD_DIR}/usr/share/pixmaps/winv-linux.png"
chmod 644 "${BUILD_DIR}/usr/share/pixmaps/winv-linux.png"

# Gera as variantes hicolor para excelente nitidez em todas as resoluções
python3 -c "
import gi
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf
import os

src = 'winv-linux.png'
pix = GdkPixbuf.Pixbuf.new_from_file(src)
sizes = [16, 24, 32, 48, 64, 128, 256, 512]
base_dir = '${BUILD_DIR}/usr/share/icons/hicolor'

for s in sizes:
    dest_dir = f'{base_dir}/{s}x{s}/apps'
    os.makedirs(dest_dir, exist_ok=True)
    scaled = pix.scale_simple(s, s, GdkPixbuf.InterpType.BILINEAR)
    scaled.savev(f'{dest_dir}/winv-linux.png', 'png', [], [])
"

# Atalho no menu do sistema (.desktop)
cat <<EOF > "${BUILD_DIR}/usr/share/applications/winv-linux.desktop"
[Desktop Entry]
Name=Área de Transferência (Win+V)
Comment=Histórico de Área de Transferência nativo do Windows para Linux
Exec=/usr/bin/winv-linux
Icon=winv-linux
Terminal=false
Type=Application
Categories=Utility;System;
StartupNotify=false
EOF
chmod 644 "${BUILD_DIR}/usr/share/applications/winv-linux.desktop"

# Configuração automática do atalho Super+V no autostart do usuário (/etc/xdg/autostart/)
# Garante que qualquer novo login registre o atalho automaticamente
cat <<'EOF' > "${BUILD_DIR}/etc/xdg/autostart/winv-linux-shortcut.desktop"
[Desktop Entry]
Type=Application
Name=winv-linux Shortcut Auto-Config
Comment=Garante a configuração automática do atalho Super+V no desktop do usuário
Exec=/usr/bin/winv-linux --setup-shortcut
Terminal=false
NoDisplay=true
X-GNOME-Autostart-enabled=true
EOF
chmod 644 "${BUILD_DIR}/etc/xdg/autostart/winv-linux-shortcut.desktop"

echo "[4/6] Gerando arquivo de controle e metadados (DEBIAN/control)..."
cat <<EOF > "${BUILD_DIR}/DEBIAN/control"
Package: ${PKG_NAME}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: python3, python3-gi, gir1.2-gtk-3.0, gir1.2-wnck-3.0, xdotool, python3-xlib, python3-cryptography
Maintainer: Pedro Modesto <pedrogabrielmodesto@gmail.com>
Homepage: https://github.com/JKLModesto/winv-linux
Description: Experiencia nativa do Win+V com Engenharia Reversa.
 Gerenciador de area de transferencia ultra-rapido (<10ms) para Linux X11,
 com abas persistentes, cofre criptografado (AES-256-GCM + Scrypt),
 configuracao automatica de atalhos e verificador de atualizacoes GitHub.
EOF

echo "[5/6] Gerando scripts de pós-instalação e pré-remoção..."
cat <<'EOF' > "${BUILD_DIR}/DEBIAN/postinst"
#!/bin/bash
set -e

# 1. Habilita o serviço de usuário globalmente
systemctl --global enable winv-linux.service 2>/dev/null || true

# 2. Função auxiliar para configurar o atalho Super+V na sessão gráfica ativa do usuário
setup_user_shortcut_now() {
    local u_name="$1"
    local u_uid="$2"
    local u_bus="/run/user/${u_uid}/bus"
    local u_runtime="/run/user/${u_uid}"
    local u_home
    u_home=$(getent passwd "$u_name" | cut -d: -f6)

    if [ -S "$u_bus" ] && [ -d "$u_runtime" ]; then
        local u_env
        u_env=$(systemctl --user -M "${u_uid}@" show-environment 2>/dev/null || true)
        local u_desktop
        u_desktop=$(echo "$u_env" | grep -E '^XDG_CURRENT_DESKTOP=' | cut -d= -f2-)
        local u_display
        u_display=$(echo "$u_env" | grep -E '^DISPLAY=' | cut -d= -f2-)
        local u_xauth
        u_xauth=$(echo "$u_env" | grep -E '^XAUTHORITY=' | cut -d= -f2-)

        if [ -z "$u_xauth" ] && [ -f "$u_home/.Xauthority" ]; then
            u_xauth="$u_home/.Xauthority"
        fi

        runuser -u "$u_name" -- env \
            HOME="$u_home" \
            USER="$u_name" \
            DBUS_SESSION_BUS_ADDRESS="unix:path=$u_bus" \
            XDG_RUNTIME_DIR="$u_runtime" \
            XDG_CURRENT_DESKTOP="${u_desktop:-X-Cinnamon}" \
            DISPLAY="${u_display:-:0}" \
            XAUTHORITY="$u_xauth" \
            /usr/bin/winv-linux --setup-shortcut 2>&1 || true
    fi
}

# 3. Notifica e reinicia o serviço + aplica atalho para sessões ativas
if [ -n "$SUDO_USER" ] && [ "$SUDO_USER" != "root" ]; then
    s_uid=$(id -u "$SUDO_USER" 2>/dev/null || true)
    if [ -n "$s_uid" ]; then
        systemctl --user -M "$s_uid@" daemon-reload 2>/dev/null || true
        systemctl --user -M "$s_uid@" restart winv-linux.service 2>/dev/null || true
        setup_user_shortcut_now "$SUDO_USER" "$s_uid"
    fi
fi

if command -v loginctl >/dev/null 2>&1; then
    for uid in $(loginctl list-users --no-legend 2>/dev/null | awk '{print $1}'); do
        if [ "$uid" -ge 1000 ] 2>/dev/null; then
            u_name=$(id -nu "$uid" 2>/dev/null || true)
            systemctl --user -M "$uid@" daemon-reload 2>/dev/null || true
            systemctl --user -M "$uid@" restart winv-linux.service 2>/dev/null || true
            if [ -n "$u_name" ] && [ "$u_name" != "$SUDO_USER" ]; then
                setup_user_shortcut_now "$u_name" "$uid"
            fi
        fi
    done
# 4. Atualiza cache de ícones e base de dados desktop
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true
fi
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications 2>/dev/null || true
fi

echo ""
echo "================================================================"
echo " ✅ winv-linux instalado com sucesso!"
echo " ⌨️  Atalho Super+V registrado e serviço systemd iniciado."
echo "================================================================"
echo ""
exit 0
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/postinst"

cat <<'EOF' > "${BUILD_DIR}/DEBIAN/prerm"
#!/bin/bash
set -e

# Para o serviço em sessões ativas
if command -v loginctl >/dev/null 2>&1; then
    for uid in $(loginctl list-users --no-legend 2>/dev/null | awk '{print $1}'); do
        if [ "$uid" -ge 1000 ] 2>/dev/null; then
            systemctl --user -M "$uid@" stop winv-linux.service 2>/dev/null || true
        fi
    done
fi

systemctl --global disable winv-linux.service 2>/dev/null || true
exit 0
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/prerm"

cat <<'EOF' > "${BUILD_DIR}/DEBIAN/postrm"
#!/bin/bash
set -e

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    if command -v gtk-update-icon-cache >/dev/null 2>&1; then
        gtk-update-icon-cache -q -t -f /usr/share/icons/hicolor 2>/dev/null || true
    fi
    if command -v update-desktop-database >/dev/null 2>&1; then
        update-desktop-database -q /usr/share/applications 2>/dev/null || true
    fi
fi
exit 0
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/postrm"

# Ajusta permissões gerais de arquivos e pastas
find "${BUILD_DIR}/usr" -type d -exec chmod 755 {} +
find "${BUILD_DIR}/usr/share" -type f -exec chmod 644 {} +
find "${BUILD_DIR}/etc" -type d -exec chmod 755 {} +
find "${BUILD_DIR}/etc" -type f -exec chmod 644 {} +
chmod 755 "${BUILD_DIR}/usr/bin/winv-linux"

echo "[6/6] Empacotando com dpkg-deb..."
dpkg-deb --build --root-owner-group "${BUILD_DIR}"

echo ""
echo "======================================================"
echo "🎉 Sucesso! Pacote .deb gerado com sucesso:"
echo "   -> ${DEB_FILE}"
echo ""
echo "Para instalar:"
echo "   sudo dpkg -i ${DEB_FILE}"
echo "   sudo apt-get install -f   # (se faltar dependências)"
echo "======================================================"
