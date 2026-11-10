# Instalação

macOS 12 ou mais novo. Python 3.11 ou mais novo. O `shazamio` não instala no Python 3.9 que vem com o sistema. Nesta máquina o venv foi criado com o Python 3.14 do Homebrew.

## Ambiente

```bash
cd karaoke-hud
python3.14 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

`requirements.txt` fixa `shazamio==0.9.0` e `pywebview==6.2.1`. O resto (`sounddevice`, `soundfile`, `requests`) fica na versão que o pip resolver.

## Abrir

Pelo terminal, com o venv ativo:

```bash
python app.py
```

Ou dois cliques em `Karaoke HUD.app`.

O `.app` não é um binário congelado. O executável `Contents/MacOS/karaoke-hud` sobe três níveis, entra na pasta do projeto e roda `venv/bin/python app.py`. O pacote tem de continuar dentro de `karaoke-hud/`, ao lado de `venv/` e `app.py`. Levar a pasta inteira para outro lugar no mesmo Mac preserva esse caminho relativo.

O pacote não é assinado. Na primeira abertura o macOS pode recusar. Confirme em Ajustes do Sistema, Privacidade e Segurança.

## Permissões

**Microfone.** Na primeira gravação o sistema pede acesso ao microfone. Sem isso a identificação não tem áudio.

**Acessibilidade.** ⌘⇧K fora da janela do app usa um monitor global de teclado. O macOS só entrega esse monitor se o programa que lançou o Python estiver em Ajustes do Sistema, Privacidade e Segurança, Acessibilidade. Sem essa permissão o terminal imprime `Atalho global indisponível` e o atalho de fora não dispara. **Ouvir**, no ícone da barra de menus, continua funcionando.

## O que não entra no git

`.env`, `venv/` e `*.wav` estão no `.gitignore`. `sample.wav` é a gravação local da última escuta. A v0.1 não lê chave de API: o reconhecimento vai pelo shazamio, sem token.
