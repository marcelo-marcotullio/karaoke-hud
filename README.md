# karaoke-hud

Pet project: um app de desktop para o macOS. Um atalho ouve a música que está tocando e mostra a letra sincronizada.

**v0.1** escuta o microfone, reconhece a faixa e acompanha a linha certa. A captura direta da saída de áudio do computador ainda não existe.

## v0.1

O app abre em silêncio. O ícone (nota e microfone) fica na barra de menus, nos itens de status ao lado do relógio. ⌘⇧K, ou **Ouvir** nesse ícone, grava 12 segundos do microfone e reconhece a faixa sem mostrar nada. A letra só entra na tela quando chega. Passe o mouse para ajustar o tempo. **Esc**, **Fechar** ou **Sair** encerra.

| Peça | O que faz |
|---|---|
| `app.py` | Janela, atalho, ícone da barra de menus e o fluxo inteiro. |
| `record.py` | Grava 12 segundos do dispositivo de entrada padrão em `sample.wav`, 44,1 kHz, mono. |
| `identify.py` | Reconhece o áudio com o [shazamio](https://github.com/shazamio/ShazamIO). Devolve artista, título e a posição do trecho na música. Não usa chave. |
| `get_lyrics.py` | Busca a letra sincronizada no [LRCLIB](https://lrclib.net/). |
| `Karaoke HUD.app` | Casca do macOS que abre o `app.py` com o Python do `venv` desta pasta. |
| `iconTemplate.png` | Ícone da barra de menus. Silhueta preta, tratada como template pelo sistema. |

A posição que o Shazam devolve é o instante do começo da gravação. O relógio da letra anda a partir daí.

## How-tos

- [Instalação](docs/instalacao.md) — Python, venv, permissões e o `.app`.
- [Como usar](docs/como-usar.md) — atalho, letra, ajuste de tempo e o que a tela faz.
- [Como funciona](docs/como-funciona.md) — o caminho do áudio até a linha na tela, e como testar cada etapa.

## O que a v0.1 não faz

- Não captura a saída de áudio do computador. A escuta é o microfone do dispositivo de entrada padrão.
- Não embute o Python. `Karaoke HUD.app` depende do `venv` ao lado dele. Um binário que rode em outro Mac sem esta pasta pede um empacotador como o py2app.
- Não tem tela de configurações. Atalho, microfone, cor, posição e “ouvir a próxima” ficam para uma versão seguinte.
- Não aparece no Dock. O processo fica como item da barra de menus.
