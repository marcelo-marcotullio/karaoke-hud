# Brief para a próxima sessão

Leia isto antes de mudar o karaoke-hud. O produto é um HUD de letra para o macOS: abre em silêncio, espera um atalho, ouve o microfone, reconhece a faixa e mostra só a letra, no tempo da música.

## O que já está decidido

- Reconhecimento com shazamio, sem chave. A posição que ele devolve é o segundo da faixa no começo da gravação. O relógio da letra é essa posição mais o tempo decorrido, mais o ajuste manual.
- A gravação dura 12 segundos, mono. Quinze segundos ou mais voltaram sem match.
- A letra vem do LRCLIB. Não grave letra de música no git.
- A tela nasce oculta. Nada aparece enquanto grava ou reconhece. A letra não rouba o foco (`orderFrontRegardless`, sem ativar o app).
- O ícone da barra de menus é `iconTemplate.png`, silhueta preta marcada como template.
- A janela acompanha todos os desktops, inclusive tela cheia. O app aparece no Dock.
- Atalho, microfone, tamanho, cor, fundo, posição, “ouvir a próxima” e abrir ao entrar ficam em `~/Library/Application Support/karaoke-hud/config.json`. Não vão para o git.
- O atalho global é um monitor do AppKit na thread da interface. pynput derruba o processo. Sem permissão de Acessibilidade o monitor não nasce; **Ouvir** no ícone continua valendo.
- Fechar não pode chamar `window.destroy()` no fio que espera o JavaScript. O processo sai com `os._exit`.
- `evaluate_js` não pode ser chamado da thread principal: ele espera essa thread e trava.
- `Karaoke HUD.app` só chama o Python do `venv` desta pasta. Não é um binário independente.
- A saída de áudio do computador ainda não é capturada. O microfone é o caminho que existe.

## Como verificar

Com o venv ativo: `python tests/test_settings.py` e `python app.py`. O app tem de continuar sem janela até o atalho. O ícone fica na barra de menus, ao lado do relógio. Conferir o menu (atalho, microfone, legenda, próxima, login) e se a letra acompanha a troca de desktop.

## O que não fazer

Não colocar `.env`, token, `sample.wav` nem o `venv` no git. Não tratar o repositório `manager` como parte deste projeto. Não inventar sucesso de reconhecimento: sem match, a frase some em poucos segundos e o app continua aberto.

## Prompt

Você continua o karaoke-hud. Leia `AGENTS.md`, `README.md` e `docs/` antes de editar. Mantenha o núcleo (gravar, reconhecer, letra, tempo) separado da casca do macOS. A letra só aparece quando existe; o app não pede a tela na abertura. Configuração nova entra no menu da barra e no `config.json`. Não commite segredo nem letra. Rode `python tests/test_settings.py` e abra o app para conferir o que a pessoa vê.
