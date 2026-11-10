# Como usar

1. Abra o app (`python app.py` ou `Karaoke HUD.app`).
2. Nada aparece no meio da tela. O ícone de nota e microfone fica na barra de menus, nos itens de status ao lado do relógio. O ícone do app também entra no Dock, para achar o processo em qualquer desktop. Se a barra de menus estiver em ocultação automática, leve o ponteiro até a borda superior da tela.
3. Toque a música no ambiente, de um jeito que o microfone ouça.
4. Aperte ⌘⇧K, ou clique no ícone e escolha **Ouvir**.
5. Espere os 12 segundos de gravação. A tela continua vazia enquanto ele grava e reconhece.
6. Se houver letra sincronizada, a linha atual aparece no centro, com a anterior e a próxima mais fracas, sobre um fundo escuro leve. A janela fica por cima das outras, em qualquer desktop, e não rouba o foco.
7. No fim da última linha, mais 6 segundos, a letra some. Com **Ouvir a próxima sozinho** ligado (é o padrão), ele grava de novo na hora. Se for outra música, a letra troca. Se não reconhecer, a frase some e ele para.

## Menu do ícone

- **Ouvir** faz uma escuta agora. O atalho mostrado é o que está valendo.
- **Ouvir a próxima sozinho** liga ou desliga a escuta automática no fim da faixa.
- **Centralizar** (⌘⇧↓) devolve a letra para o centro, perto da borda de baixo, e esquece o lugar salvo.
- **Tamanho** e **Cor** mudam a legenda. **Fundo atrás da letra** liga o retângulo escuro.
- **Microfone** lista as entradas do Mac. **Padrão do sistema** segue o que estiver em Ajustes do Sistema, Som, Entrada.
- **Atalho** espera a próxima combinação, com pelo menos uma tecla modificadora. Esc cancela.
- **Abrir ao entrar** registra o app no início da sessão. Vale no próximo login.
- **Sair** encerra o processo.

Arrastar a letra guarda a posição em `~/Library/Application Support/karaoke-hud/config.json`.

## Ajuste de tempo

Passe o mouse sobre a letra. Aparece uma faixa com **−1s**, **−0.1s**, **+0.1s**, **+1s**. O deslocamento vale só para a escuta atual.

## Quando não há letra

Uma frase fica na tela por cerca de 3,5 segundos e some:

- `Não reconheci a música.` — o Shazam não devolveu faixa.
- `Artista — Título. Sem letra.` — a faixa foi reconhecida e o LRCLIB não tem letra sincronizada utilizável.

Nesses dois casos ele não encadeia outra escuta.

## Encerrar

- **Esc** ou **Fechar**, com a letra na tela.
- **Sair** no menu do ícone, ou pelo ícone do Dock.

Fechar a letra não encerra o app. **Sair**, **Esc** e **Fechar** encerram o processo.

## O que o microfone precisa ouvir

A gravação é mono. Doze segundos é a janela que o reconhecimento aceita. Não há captura da saída de áudio do computador: o som precisa chegar ao microfone escolhido.
