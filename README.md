# 📋 winv-mint: Windows `Win + V` Clipboard Experience for Linux Mint

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux%20Mint%20%28Cinnamon%20%2F%20X11%29-green.svg)]()
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-yellow.svg)]()

> **Português:** Implementação nativa, de altíssima performance e sem concessões da experiência completa do **Histórico da Área de Transferência do Windows (`Win + V`)** para o **Linux Mint (Cinnamon / X11)**, construída a partir de engenharia reversa detalhada dos binários do Windows (`cbdhsvc.dll` e `SuggestionUIUndocked.dll`).
>
> **English:** A native, ultra-low-latency, zero-compromise implementation of the **Windows Clipboard History (`Win + V`)** experience for **Linux Mint (Cinnamon / X11)**, engineered directly from reverse-engineered Windows internals (`cbdhsvc.dll` and `SuggestionUIUndocked.dll`).

---

## 🔬 Engenharia Reversa do Windows (Reverse Engineering Highlights)

Este projeto não é apenas "mais um gerenciador de clipboard". Ele replica a arquitetura interna e as regras de negócio exatas que a Microsoft emprega no subsistema do `Win + V`:

| Comportamento do Windows (`cbdhsvc.dll` / `SuggestionUIUndocked.dll`) | Implementação no `winv-mint` |
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

## 🚀 Instalação Rápida no Linux Mint (Quick Start)

Clone o repositório e execute o script de instalação automatizada:

```bash
git clone https://github.com/pedro/winv-mint.git
cd winv-mint
chmod +x install_mint.sh
./install_mint.sh
```

### O que o instalador faz automaticamente:
1. Instala as dependências nativas via `apt` (`python3-gi`, `gir1.2-gtk-3.0`, `gir1.2-wnck-3.0`, `xdotool`, `x11-utils`, `python3-xlib`).
2. Copia os binários para `~/.local/bin/winv-mint` e bibliotecas para `~/.local/share/winv-mint/`.
3. Cria, ativa e inicia o serviço de usuário no systemd (`systemctl --user enable --now winv-mint.service`).
4. **Registra automaticamente o atalho global `Super + V`** nas configurações do Cinnamon (`org.cinnamon.desktop.keybindings`).

Agora basta pressionar **`Super + V`** (a tecla Windows + V) em qualquer lugar do seu Linux Mint! 🎉

---

## ⌨️ Atalhos e Interação

* **`Super + V`**: Abre ou fecha o histórico na posição exata do cursor.
* **Clique ou `Enter`**: Cola o item selecionado diretamente na janela em que você estava trabalhando.
* **`Esc` ou Clicar Fora**: Fecha a janela instantaneamente.
* **📌 (Fixar / Desafixar)**: Torna o item permanente, persistindo-o mesmo após reiniciar o sistema.
* **🗑️ (Excluir)**: Remove o item selecionado.
* **"Limpar tudo"**: Esvazia o histórico volátil (RAM), preservando com segurança todos os seus itens fixados.

---

## 🛠️ Comandos de Linha de Comando (CLI)

Você também pode controlar o `winv-mint` pelo terminal ou em scripts:

```bash
# Alterna a visibilidade do popup (mesma ação do Super+V)
winv-mint --popup

# Limpa o histórico em memória (mantendo os fixados)
winv-mint --clear

# Verifica o status do daemon
winv-mint --status

# Exibe a ajuda com todas as opções
winv-mint --help
```

---

## 📂 Estrutura do Repositório

```text
winv-mint/
├── DOCS/
│   └── WINDOWS_CLIPBOARD_RE.md   # Especificação formal da engenharia reversa
├── winv/
│   ├── __init__.py
│   ├── config.py                 # Constantes e limites espelhados do Windows
│   ├── models.py                 # Modelos de dados e serialização de formatos
│   ├── storage.py                # Armazenamento híbrido (RAM FIFO + Disco Pinned)
│   ├── monitor.py                # Monitor de clipboard com filtro anti-loop
│   ├── x11_helper.py             # Captura de XID, foco e injeção do auto-paste
│   ├── ui.py                     # Flyout em GTK3 estilizado em Dark Mode
│   ├── ipc.py                    # Unix Domain Socket (< 10ms de latência)
│   └── daemon.py                 # Orquestrador do processo em background
├── bin/
│   └── winv-mint                 # Script executável CLI
├── systemd/
│   └── winv-mint.service         # Definição do serviço do usuário systemd
├── install_mint.sh               # Script de instalação com 1 clique
└── README.md                     # Este documento
```

---

## 🗑️ Desinstalação (Uninstallation)

Para remover completamente o `winv-mint`, parar o serviço e desvincular o atalho do teclado:

```bash
./install_mint.sh --uninstall
```

---

## 📄 Licença

Distribuído sob a licença **MIT**. Veja `LICENSE` para mais informações.
