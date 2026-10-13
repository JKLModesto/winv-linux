# 📋 winv-linux: Windows `Win + V` Clipboard Experience for Linux

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux%20Mint%20%28Cinnamon%20%2F%20X11%29-green.svg)]()
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-yellow.svg)]()

> **Português:** Implementação nativa, de altíssima performance e sem concessões da experiência completa do **Histórico da Área de Transferência do Windows (`Win + V`)** para o **Linux Mint (Cinnamon / X11)**, construída a partir de engenharia reversa detalhada dos binários do Windows (`cbdhsvc.dll` e `SuggestionUIUndocked.dll`).
>
> **English:** A native, ultra-low-latency, zero-compromise implementation of the **Windows Clipboard History (`Win + V`)** experience for **Linux Mint (Cinnamon / X11)**, engineered directly from reverse-engineered Windows internals (`cbdhsvc.dll` and `SuggestionUIUndocked.dll`).

---

## 🔬 Engenharia Reversa do Windows (Reverse Engineering Highlights)

Este projeto não é apenas "mais um gerenciador de clipboard". Ele replica a arquitetura interna e as regras de negócio exatas que a Microsoft emprega no subsistema do `Win + V`:

| Comportamento do Windows (`cbdhsvc.dll` / `SuggestionUIUndocked.dll`) | Implementação no `winv-linux` |
| :--- | :--- |
| **Limite Circular:** Buffer em RAM com no máximo 25 itens (`maxBufferItemsCount`). | Buffer FIFO estrito de 25 itens não-fixados em memória RAM. |
| **Limite de Tamanho:** Rejeita payloads acima de 4 MB (`maxHistoryItemSizeInBytes`). | Verificação de integridade limitando cada item a 4 MB. |
| **Ciclo de Vida Híbrido:** Itens não fixados vivem na RAM e são limpos no logoff; Itens Fixados são salvos em disco com `metadata.json`. | Estrutura híbrida com `metadata.json` + payloads gravados em `~/.local/share/winv-clipboard/Pinned/`. |
| **Filtro Anti-Loop (`ExcludeClipboardContent`):** O monitor ignora colagens geradas pela própria UI para evitar duplicações. | Rastreamento criptográfico (SHA-256) das colagens injetadas pela UI. |
| **Multi-Monitor Bounding Box:** O flyout calcula a posição do cursor e inverte (Top/Bottom) conforme a área útil do monitor. | Detecção precisa de múltiplos monitores via GDK, respeitando painéis e margens de tela. |
| **Auto-Paste Contextual:** Restaura a janela anterior e aguarda 25ms de estabilização antes de enviar `Ctrl+V`. | Restauração de `XID` com delay de 25ms, enviando `Ctrl+Shift+V` para terminais e `Ctrl+V` para apps comuns. |
| **Latência Instantânea (< 10ms):** `TextInputHost.exe` mantém a UI pré-carregada na inicialização do sistema. | Daemon com processo único e janela GTK3 pré-renderizada e oculta via `hide()`, abrindo em menos de 10ms. |

Para detalhes aprofundados com diagramas Mermaid e tabelas de símbolos, consulte o documento técnico:  
👉 **[DOCS/WINDOWS_CLIPBOARD_RE.md](DOCS/WINDOWS_CLIPBOARD_RE.md)**.

---

## 🚀 Instalação Rápida (Mint, Ubuntu, Zorin) (Quick Start)

Clone o repositório e execute o script de instalação automatizada:

```bash
git clone https://github.com/pedro/winv-linux.git
cd winv-linux
chmod +x install.sh
./install.sh
```

### O que o instalador faz automaticamente:
1. Instala as dependências nativas via `apt` (`python3-gi`, `gir1.2-gtk-3.0`, `gir1.2-wnck-3.0`, `xdotool`, `x11-utils`, `python3-xlib`).
2. Copia os binários para `~/.local/bin/winv-linux` e bibliotecas para `~/.local/share/winv-linux/`.
3. Cria, ativa e inicia o serviço de usuário no systemd (`systemctl --user enable --now winv-linux.service`).
4. **Registra automaticamente o atalho global `Super + V`** no seu ambiente (Cinnamon, GNOME/Zorin/Ubuntu, MATE ou XFCE).

Agora basta pressionar **`Super + V`** (a tecla Windows + V) em qualquer lugar do seu Linux! 🎉

---

## 🗂️ Abas Persistentes e Abas Cofre (Criptografia AES-256-GCM + Scrypt)

Além do histórico padrão de 25 itens em RAM, o `winv-linux` permite criar **Abas Personalizadas**:

* **Abas Normais:** Ideais para comandos CLI frequentes, respostas prontas ou anotações de trabalho. Todos os itens adicionados são persistidos em disco (`~/.local/share/winv-clipboard/Tabs/`) e sobrevivem a reinicializações.
* **Abas Cofre (🔒 Protegidas por Senha):**
  * **Criptografia Forte em Disco:** Protegidas com derivação de chave via **Scrypt** (`memory-hard`, defensivo contra GPUs) e cifra autenticada **AES-256-GCM** com AAD vinculado ao ID da aba.
  * **Zero Plaintext:** Textos, previews e imagens são gravados em um único arquivo cifrado (`vault.enc`).
  * **Zero Memory Leak:** A chave fica em memória mutável e é zerada com `zero-fill` ao trancar.
  * **Auto-Lock por Inatividade:** Após 5 minutos sem uso, o cofre é trancado automaticamente na RAM.
  * **Auto-Restore Anti-Leak (1.5s):** Ao colar credenciais ou tokens de uma aba cofre, o `winv-linux` injeta a colagem no app de destino e, **1.5s depois, restaura o clipboard com o conteúdo público anterior** (ou limpa a área de transferência), impedindo que a senha permaneça exposta ao `Ctrl+V` acidental ou a leituras externas.

---

## ⌨️ Atalhos e Interação

* **`Super + V`**: Abre ou fecha o histórico na posição exata do cursor.
* **`Alt + 1, 2, ... 9`**: Alterna instantaneamente entre as abas (1 = Histórico, 2..9 = Abas customizadas).
* **`Ctrl + PageUp / PageDown`**: Navega ciclicamente entre as abas.
* **`Ctrl + L`**: Tranca a aba cofre atual imediatamente.
* **Clique ou `Enter`**: Cola o item selecionado diretamente na janela em que você estava trabalhando.
* **`Esc`**: Fecha o popover aberto ou o flyout.
* **`→` (Enviar para aba)**: No Histórico, copia um item diretamente para qualquer aba criada.
* **`+ Novo item`**: Permite adicionar um snippet ou texto livre (ou colar o clipboard atual) direto na aba ativa.
* **Clique direito na aba**: Permite renomear, trancar ou excluir a aba.
* **`◇ / ◆` (Fixar / Desafixar)**: Torna o item permanente no Histórico (Pinned).
* **`✕` (Excluir)**: Remove o item selecionado.
* **"Limpar tudo"**: Esvazia o histórico volátil (RAM), preservando todos os itens fixados.

---

## 🛠️ Comandos de Linha de Comando (CLI)

Você também pode controlar o `winv-linux` pelo terminal ou em scripts:

```bash
# Alterna a visibilidade do popup (mesma ação do Super+V)
winv-linux --popup

# Limpa o histórico em memória (mantendo os fixados)
winv-linux --clear

# Verifica o status do daemon
winv-linux --status

# Exibe a ajuda com todas as opções
winv-linux --help
```

---

## 📂 Estrutura do Repositório

```text
winv-linux/
├── DOCS/
│   └── WINDOWS_CLIPBOARD_RE.md   # Especificação formal da engenharia reversa
├── winv/
│   ├── __init__.py
│   ├── config.py                 # Constantes e limites espelhados do Windows
│   ├── crypto.py                 # Criptografia de cofres (Scrypt + AES-256-GCM)
│   ├── tabs.py                   # Gerenciador de abas persistentes e cofres
│   ├── models.py                 # Modelos de dados e serialização de formatos
│   ├── storage.py                # Armazenamento híbrido (RAM FIFO + Disco Pinned)
│   ├── monitor.py                # Monitor de clipboard com filtro anti-loop
│   ├── ui/                       # Flyout modular em GTK3 (Dark Mode Fluent)
│   │   ├── window.py             # Janela Flyout, posicionamento X11 e foco
│   │   ├── tabs_bar.py           # Barra de abas, Kanban drag-and-drop e scroll
│   │   ├── cards.py              # Renderização dos cards, miniaturas e colagem
│   │   ├── popovers.py           # Menus, criação de abas e desbloqueio de cofre
│   │   ├── styles.py             # Folhas de estilo CSS
│   │   └── constants.py          # Constantes da interface
│   ├── updater.py                # Verificador assíncrono de updates (GitHub Releases)
│   ├── ipc.py                    # Unix Domain Socket (< 10ms de latência)
│   └── daemon.py                 # Orquestrador do processo em background
├── bin/
│   └── winv-linux                # Script executável CLI
├── systemd/
│   └── winv-linux.service        # Definição do serviço do usuário systemd
├── build_deb.sh                  # Construtor do pacote instalador oficial .deb
├── install.sh                    # Instalador universal (Mint, Ubuntu, Zorin...)
└── README.md                     # Este documento
```

---

## 🗑️ Desinstalação (Uninstallation)

Para remover completamente o `winv-linux`, parar o serviço e desvincular o atalho do teclado:

```bash
./install.sh --uninstall
```

---

## 📄 Licença

Distribuído sob a licença **MIT**. Veja `LICENSE` para mais informações.
