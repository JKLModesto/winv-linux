<div align="center">

<img src="winv-linux.png" alt="winv-linux logo" width="160" />

# winv-linux
### Experiência Nativa do Windows `Win + V` para Linux

[![Versão](https://img.shields.io/badge/vers%C3%A3o-1.0.0-blue.svg?style=flat-square)](https://github.com/JKLModesto/winv-linux/releases)
[![Licença: MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-green.svg?style=flat-square)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8%2B-yellow.svg?style=flat-square)](https://www.python.org/)
[![Status dos Testes](https://img.shields.io/badge/testes-31%20passando-brightgreen.svg?style=flat-square)]()
[![Desenvolvedor](https://img.shields.io/badge/desenvolvido%20por-Pedro%20Modesto-orange.svg?style=flat-square)](https://github.com/JKLModesto)

</div>

> **Português:** Implementação nativa, de altíssima performance (<10ms) e sem concessões da experiência completa do **Histórico da Área de Transferência do Windows (`Win + V`)** para sistemas Linux X11, construída a partir de engenharia reversa detalhada dos binários oficiais do Windows (`cbdhsvc.dll` e `SuggestionUIUndocked.dll`).
>
> **English:** A native, ultra-low-latency (<10ms), zero-compromise implementation of the **Windows Clipboard History (`Win + V`)** experience for Linux X11 environments, engineered directly from reverse-engineered Windows internals (`cbdhsvc.dll` and `SuggestionUIUndocked.dll`).

---

## 👨‍💻 Desenvolvedor & Autor

* **Autor:** **Pedro Modesto**
* **GitHub:** [@JKLModesto](https://github.com/JKLModesto)
* **Repositório Oficial:** [JKLModesto/winv-linux](https://github.com/JKLModesto/winv-linux)

---

## 🖥️ Sistemas Operacionais e Ambientes Compatíveis

O `winv-linux` foi desenvolvido e homologado para as principais distribuições Linux em sessões **X11**, com suporte a registro automático do atalho global **<kbd>Super</kbd> + <kbd>V</kbd>** (ou Tecla Windows + V):

### Distribuições Suportadas
| Distribuição | Versões Testadas | Método de Instalação Recomendado |
| :--- | :--- | :--- |
| **Linux Mint** | 20.x, 21.x, **22.x** (Wilma / Xia) | Pacote `.deb` ou `install.sh` |
| **Ubuntu** | 20.04 LTS, 22.04 LTS, **24.04 LTS** | Pacote `.deb` ou `install.sh` |
| **Debian** | 11 (Bullseye), **12 (Bookworm)**, Sid | Pacote `.deb` ou `install.sh` |
| **Zorin OS** | 16.x, **17.x** | Pacote `.deb` ou `install.sh` |
| **Pop!_OS** | 20.04 LTS, 22.04 LTS | Pacote `.deb` ou `install.sh` |
| **Outras distros baseadas em Debian** | Qualquer kernel moderno com suporte a GTK3/X11 | Pacote `.deb` ou `install.sh` |
| **Arch Linux / Fedora / openSUSE** | Versões atuais (sessão X11) | Script `install.sh` |

### Ambientes de Desktop (DEs) com Atalho Automático
* **Cinnamon (Linux Mint):** Configuração nativa no schema `org.cinnamon.desktop.keybindings` com hot-reload dinâmico.
* **GNOME Shell (Ubuntu, Zorin, Pop!_OS):** Configuração em `org.gnome.settings-daemon.plugins.media-keys` com liberação automática de conflitos na bandeja de notificações.
* **MATE Desktop:** Registro automático via `dconf` em `/org/mate/desktop/keybindings/`.
* **XFCE4:** Configuração direta no canal `xfce4-keyboard-shortcuts` via `xfconf-query`.

---

## ⚡ Instalação

Você pode instalar o `winv-linux` facilmente pelo **pacote oficial `.deb`** ou pelo instalador universal via script:

### Opção 1: Instalador Oficial `.deb` (Recomendado para Mint, Ubuntu e Debian)

Baixe a versão mais recente em [Releases](https://github.com/JKLModesto/winv-linux/releases) ou compile localmente:

```bash
# Compilação do pacote deb (opcional, caso esteja no código-fonte):
./build_deb.sh

# Instalação com resolução automática de dependências:
sudo dpkg -i dist/winv-linux_1.0.0_all.deb
sudo apt-get install -f   # Garante qualquer dependência pendente
```

> 💡 **Vantagens do pacote `.deb`:**
> * Instalação no padrão FHS do sistema (`/usr/bin/winv-linux`, `/usr/share/winv-linux/`).
> * Registra e ativa o serviço global do systemd para todos os usuários.
> * Vincula o atalho <kbd>Super</kbd> + <kbd>V</kbd> imediatamente no desktop ativo.
> * Adiciona inicialização automática transparente em `/etc/xdg/autostart/`.

### Opção 2: Instalador Universal (`install.sh`)

Para instalação local sem empacotamento:

```bash
git clone https://github.com/JKLModesto/winv-linux.git
cd winv-linux
chmod +x install.sh
./install.sh
```

---

## 🔬 Engenharia Reversa do Windows (`cbdhsvc.dll` & `SuggestionUIUndocked.dll`)

Este projeto não é um simples utilitário de colagem; ele reproduz fielmente as especificações internas do Windows 10/11:

| Mecanismo do Windows | Implementação no `winv-linux` |
| :--- | :--- |
| **Limite Circular:** Buffer em RAM com no máximo 25 itens (`maxBufferItemsCount`). | Buffer FIFO estrito de 25 itens voláteis na memória RAM. |
| **Limite de Tamanho:** Rejeita payloads acima de 4 MB (`maxHistoryItemSizeInBytes`). | Verificação de integridade limitando cada item copiado a 4 MB. |
| **Ciclo de Vida Híbrido:** Itens normais vivem na RAM; Itens Fixados persistem em disco com `metadata.json`. | Estrutura híbrida com `metadata.json` + payloads em `~/.local/share/winv-clipboard/Pinned/`. |
| **Filtro Anti-Loop (`ExcludeClipboardContent`):** O monitor ignora colagens geradas pelo próprio app. | Rastreamento criptográfico (SHA-256) das colagens injetadas pela UI. |
| **Posicionamento Multi-Monitor:** O flyout calcula o cursor e inverte (Top/Bottom) conforme as bordas do monitor. | Detecção precisa de múltiplos monitores via GDK, respeitando painéis de tarefas e margens. |
| **Auto-Paste Contextual:** Restaura a janela ativa anterior e aguarda 25ms antes de enviar o paste. | Restauração de `XID` com delay de 25ms, enviando `Ctrl+Shift+V` para terminais e `Ctrl+V` para apps comuns. |
| **Latência Instantânea (< 10ms):** UI pré-carregada na inicialização do sistema. | Daemon em processo único com janela GTK3 pré-renderizada e oculta via `hide()`, abrindo em menos de 10ms via Unix Socket. |

Consulte o documento técnico completo com diagramas: 👉 **[DOCS/WINDOWS_CLIPBOARD_RE.md](DOCS/WINDOWS_CLIPBOARD_RE.md)**.

---

## ✨ Funcionalidades em Destaque (v1.0.0)

### 🎨 Design Minimalista e Moderno
* **Abas Sem Contornos Pesados:** Estilo limpo e minimalista, sem fundos retangulares cinzas, mantendo apenas um traço elegante sublinhado sob a aba ativa.
* **Organização Fluida de Abas:** Rolagem horizontal suave com a roda do mouse (sem necessidade de pressionar Shift) e botões contextuais de mover para esquerda/direita.

### 🔒 Abas Cofre (Criptografia AES-256-GCM + Scrypt)
* **Criptografia Forte:** Abas protegidas por senha com derivação de chave em **Scrypt** (`memory-hard`) e cifra autenticada **AES-256-GCM**.
* **Zero Plaintext:** Textos, previews e imagens de cofres são salvos em um único payload cifrado (`vault.enc`).
* **Auto-Lock por Inatividade:** Trancamento automático na RAM após 5 minutos sem uso.
* **Auto-Restore Anti-Leak (1.5s):** Ao colar credenciais ou tokens de uma aba cofre, o `winv-linux` injeta a colagem no app de destino e, **1.5s depois, restaura o clipboard com o conteúdo público anterior** (ou limpa a área de transferência), impedindo que a senha permaneça exposta ao `Ctrl+V` acidental ou a leituras externas.

### 🔄 Verificador de Atualizações Assíncrono
* Consulta silenciosa da API do GitHub Releases 15 segundos após a inicialização (e periodicamente a cada 24 horas).
* **Zero impacto na velocidade:** A checagem roda em thread secundária isolada e nunca atrasa a abertura do flyout.
* Notificação não-intrusiva com link direto para download do `.deb` mais novo quando disponível.

---

## ⌨️ Atalhos de Teclado

* **<kbd>Super</kbd> + <kbd>V</kbd>** (ou Tecla Windows + V): Abre ou oculta o flyout instantaneamente.
* **<kbd>Alt</kbd> + <kbd>1</kbd>, <kbd>2</kbd>, ... <kbd>9</kbd>**: Alterna rapidamente entre as abas (1 = Histórico, 2..9 = Abas personalizadas).
* **<kbd>Ctrl</kbd> + <kbd>PageUp</kbd> / <kbd>PageDown</kbd>**: Navega sequencialmente entre as abas.
* **<kbd>Ctrl</kbd> + <kbd>L</kbd>**: Tranca a aba cofre atual imediatamente.
* **<kbd>Enter</kbd> ou Clique**: Cola o item selecionado na janela anterior.
* **<kbd>Esc</kbd>**: Fecha popovers ou oculta o histórico.
* **`◇ / ◆` (Fixar / Desafixar)**: Torna o item permanente no Histórico.
* **`→` (Enviar para aba)**: Envia uma cópia do item para uma aba temática ou cofre.

---

## 🛠️ Interface de Linha de Comando (CLI)

O executável `winv-linux` pode ser usado diretamente no terminal ou em scripts:

```bash
# Alterna a visibilidade do popup (mesma ação do Super+V)
winv-linux --toggle

# Força abertura ou ocultação
winv-linux --show
winv-linux --hide

# Limpa itens não-fixados do histórico em memória
winv-linux --clear

# Verifica o status de resposta do daemon
winv-linux --status

# Registra/repara o atalho global Super+V no ambiente gráfico atual
winv-linux --setup-shortcut

# Exibe a ajuda
winv-linux --help
```

---

## 📁 Arquitetura do Projeto

O código do `winv-linux` é modularizado e organizado segundo princípios de responsabilidade única:

```text
winv-linux/
├── DOCS/
│   └── WINDOWS_CLIPBOARD_RE.md   # Engenharia reversa formal das DLLs do Windows
├── bin/
│   └── winv-linux                # Entry point executável CLI e disparador IPC
├── winv/
│   ├── config.py                 # Constantes e limites espelhados do Windows
│   ├── crypto.py                 # Criptografia Scrypt + AES-256-GCM para cofres
│   ├── tabs.py                   # Gerenciamento de abas persistentes e cofres
│   ├── models.py                 # Modelos de dados de histórico e serialização
│   ├── storage.py                # Armazenamento híbrido (RAM FIFO + Disco Pinned)
│   ├── monitor.py                # Monitor de clipboard X11 com filtro anti-loop
│   ├── updater.py                # Verificador assíncrono de updates no GitHub
│   ├── x11_helper.py             # Posicionamento multi-monitor e foco X11
│   ├── ipc.py                    # Servidor e cliente Unix Socket (<10ms)
│   ├── daemon.py                 # Daemon central em background
│   └── ui/                       # Interface gráfica GTK3 modular
│       ├── window.py             # Janela Flyout principal
│       ├── tabs_bar.py           # Barra de abas com scroll e reordenação
│       ├── cards.py              # Renderização dos cards de conteúdo e colagem
│       ├── popovers.py           # Menus de contexto, nova aba e desbloqueio
│       ├── styles.py             # Estilos CSS dark mode minimalista
│       └── constants.py          # Constantes visuais
├── tests/                        # Suíte de 31 testes unitários automatizados
├── systemd/
│   └── winv-linux.service        # Unidade systemd para gerenciamento do serviço
├── build_deb.sh                  # Script oficial de geração do instalador .deb
├── install.sh                    # Instalador universal via shell script
└── README.md                     # Documentação oficial do projeto
```

---

## 🧪 Testes Automatizados

Para rodar a suíte de testes unitários:

```bash
python3 -m unittest discover -s tests
```

---

## 🗑️ Desinstalação

Caso deseje desinstalar completamente o pacote:

* **Se instalado via `.deb`:**
  ```bash
  sudo apt-get remove winv-linux
  # ou
  sudo dpkg -r winv-linux
  ```

* **Se instalado via `install.sh`:**
  ```bash
  ./install.sh --uninstall
  ```

---

## 📄 Licença

Distribuído sob a licença **MIT**. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.

Desenvolvido com dedicação por **Pedro Modesto** para a comunidade Linux. 🐧
