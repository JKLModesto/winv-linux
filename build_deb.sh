#!/bin/bash
# ==============================================================================
# build_deb.sh - Construtor de Pacote Debian/Ubuntu (.deb) para o winv-linux
# ==============================================================================
set -e

VERSION="1.0.0"
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
mkdir -p "${BUILD_DIR}/DEBIAN"

echo "[3/6] Copiando arquivos do projeto..."
# Código Python em /usr/share/winv-linux/winv
cp -r winv/ "${BUILD_DIR}/usr/share/${PKG_NAME}/"
# Remove possíveis caches de bytecode
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

# Atalho no menu do sistema (.desktop)
cat <<EOF > "${BUILD_DIR}/usr/share/applications/winv-linux.desktop"
[Desktop Entry]
Name=Área de Transferência (Win+V)
Comment=Histórico de Área de Transferência nativo do Windows para Linux
Exec=/usr/bin/winv-linux
Icon=edit-paste
Terminal=false
Type=Application
Categories=Utility;System;
StartupNotify=false
EOF
chmod 644 "${BUILD_DIR}/usr/share/applications/winv-linux.desktop"

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
 com abas persistentes, cofre criptografado (AES-256-GCM + Scrypt)
 e verificador de atualizacoes automatico integrado ao GitHub Releases.
EOF

echo "[5/6] Gerando scripts de pós-instalação e pré-remoção..."
cat <<'EOF' > "${BUILD_DIR}/DEBIAN/postinst"
#!/bin/bash
set -e

# Habilita o serviço de usuário globalmente
systemctl --global enable winv-linux.service 2>/dev/null || true

# Notifica e reinicia o serviço para sessões ativas com UID >= 1000
if command -v loginctl >/dev/null 2>&1; then
    for uid in $(loginctl list-users --no-legend 2>/dev/null | awk '{print $1}'); do
        if [ "$uid" -ge 1000 ] 2>/dev/null; then
            systemctl --user -M "$uid@" daemon-reload 2>/dev/null || true
            systemctl --user -M "$uid@" restart winv-linux.service 2>/dev/null || true
        fi
    done
fi

echo ""
echo "================================================================"
echo " ✅ winv-linux v1.0.0 instalado com sucesso!"
echo " Para registrar o atalho global Super+V no seu usuário, execute:"
echo "    winv-linux --setup-shortcut"
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

# Ajusta permissões gerais de arquivos e pastas
find "${BUILD_DIR}/usr" -type d -exec chmod 755 {} +
find "${BUILD_DIR}/usr/share" -type f -exec chmod 644 {} +
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
