# Como usar

1. Abra o app (`python app.py` ou `Karaoke HUD.app`).
2. Nada aparece no meio da tela. O ícone de nota e microfone fica na barra de menus, nos itens de status ao lado do relógio. Se a barra de menus estiver em ocultação automática, leve o ponteiro até a borda superior da tela.
3. Toque a música no ambiente, de um jeito que o microfone ouça.
4. Aperte ⌘⇧K, ou clique no ícone e escolha **Ouvir**.
5. Espere os 12 segundos de gravação. A tela continua vazia enquanto ele grava e reconhece.
6. Se houver letra sincronizada, a linha atual aparece no centro, com a anterior e a próxima mais fracas. A janela fica por cima das outras e não rouba o foco.
7. No fim da última linha, mais 6 segundos, a letra some. O app continua aberto, esperando o próximo atalho.

## Ajuste de tempo

Passe o mouse sobre a letra. Aparece uma faixa com **−1s**, **−0.1s**, **+0.1s**, **+1s**. O deslocamento vale só para a escuta atual. A faixa também mostra **esc fecha** e **Fechar**.

## Quando não há letra

Uma frase fica na tela por cerca de 3,5 segundos e some:

- `Não reconheci a música.` — o Shazam não devolveu faixa.
- `Artista — Título. Sem letra.` — a faixa foi reconhecida e o LRCLIB não tem letra sincronizada utilizável (também no caso de instrumental).

## Encerrar

- **Esc** ou **Fechar**, com a letra na tela.
- **Sair** no menu do ícone. O atalho desse item é ⌘Q com o menu aberto.

Fechar a letra não encerra o app. **Sair**, **Esc** e **Fechar** encerram o processo.

## Ouvir de novo

⌘⇧K ou **Ouvir** no meio de uma letra começa outra gravação. A letra atual some na hora. O app não encadeia a música seguinte sozinho: cada escuta é um gesto seu.

## O que o microfone precisa ouvir

A v0.1 grava o dispositivo de entrada padrão do macOS, 12 segundos, mono, 44,1 kHz. Doze segundos é a janela que o reconhecimento aceita; gravações de 15 segundos ou mais voltaram sem match. Não há seletor de microfone nesta versão. Se o Mac tiver mais de uma entrada (microfone interno, iPhone, webcam), a ativa é a padrão do sistema, em Ajustes do Sistema, Som, Entrada.
