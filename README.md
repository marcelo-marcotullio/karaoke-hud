# karaoke-hud

Pet project: um app de desktop para o macOS. Um atalho ouve a música que está tocando e mostra a letra sincronizada.

**v0.2** escuta o microfone, reconhece a faixa e acompanha a linha certa. A letra fica por cima de qualquer desktop. A captura direta da saída de áudio do computador ainda não existe.

## v0.2

O app abre em silêncio e aparece no Dock. O ícone (nota e microfone) fica na barra de menus, nos itens de status ao lado do relógio. ⌘⇧K, ou **Ouvir** nesse ícone, grava 12 segundos do microfone e reconhece a faixa sem mostrar nada. A letra só entra na tela quando chega, com um fundo leve para continuar legível. No fim da faixa ele ouve de novo sozinho. Passe o mouse para ajustar o tempo. Arraste a letra; o lugar fica salvo. **Esc**, **Fechar** ou **Sair** encerra.

O menu do ícone também troca o tamanho e a cor da letra, o microfone, o atalho e se o app abre ao entrar na sessão.

| Peça | O que faz |
|---|---|
| `app.py` | Janela, atalho, ícone da barra de menus e o fluxo inteiro. |
| `settings.py` | Configuração local: atalho, legenda, microfone, posição, início de sessão. |
| `record.py` | Grava 12 segundos em `sample.wav`, 44,1 kHz, mono. |
| `identify.py` | Reconhece o áudio com o [shazamio](https://github.com/shazamio/ShazamIO). Não usa chave. |
| `get_lyrics.py` | Busca a letra sincronizada no [LRCLIB](https://lrclib.net/). |
| `Karaoke HUD.app` | Casca do macOS que abre o `app.py` com o Python do `venv` desta pasta. |
| `iconTemplate.png` | Ícone da barra de menus. |
| `AGENTS.md` | Brief para quem for continuar o projeto, pessoa ou modelo. |

A posição que o Shazam devolve é o instante do começo da gravação. O relógio da letra anda a partir daí.

## How-tos

- [Instalação](docs/instalacao.md) — Python, venv, permissões e o `.app`.
- [Como usar](docs/como-usar.md) — atalho, letra, menu e o que a tela faz.
- [Como funciona](docs/como-funciona.md) — o caminho do áudio até a linha na tela.

## O que a v0.2 não faz

- Não captura a saída de áudio do computador. A escuta é o microfone.
- Não embute o Python. `Karaoke HUD.app` depende do `venv` ao lado dele.
- Não tem versão para Windows ou Linux. O núcleo em Python é o que dá para levar; a janela, o atalho e o ícone são a casca do macOS.
