# Como funciona

O fluxo da v0.2 é linear. Cada etapa também roda sozinha, com o venv ativo.

```text
microfone → sample.wav → artista, título, posição → letra LRC → linha na tela
```

## 1. Gravar

`record.py` chama `sounddevice` no dispositivo de entrada padrão e grava `sample.wav`.

```bash
python record.py
```

`record_sample()` devolve o `time.time()` do começo da gravação. O app usa esse instante como âncora. A posição da letra é:

```text
posição do Shazam + (agora − começo da gravação) + ajuste manual
```

O Shazam informa em que segundo da faixa o trecho gravado começa, não o segundo em que a resposta chegou.

## 2. Reconhecer

`identify.py` manda o WAV ao shazamio (`language="pt-BR"`, `endpoint_country="BR"`). Não há chave.

```bash
python identify.py
python identify.py outro.wav
```

A saída, quando há match, é `artista - título (posição na música: N.Ns)`. Sem match, `Nenhuma música reconhecida.` O artista vem de `track.subtitle` e o título de `track.title`. A posição é `matches[0].offset`, em segundos.

## 3. Buscar a letra

`get_lyrics.py` consulta `https://lrclib.net/api/search` com o User-Agent `karaoke-hud v0.2`. O app pode gravar de um microfone escolhido no menu; `record.py` sozinho continua na entrada padrão. Prefere o resultado que traz `syncedLyrics`. Se o título com parênteses não achar nada, busca de novo sem o trecho entre parênteses ou colchetes.

```bash
python get_lyrics.py "Artista" "Título"
```

Os dois argumentos vão juntos. Sem eles, o script usa Arch Enemy / Symphony of Destruction como exemplo e imprime as linhas `[segundos] texto`.

`fetch_lyrics()` devolve `synced` (lista de `(segundo, texto)`), `plain` e `instrumental`. `None` significa que a busca não trouxe resultado.

## 4. Mostrar

`app.py` junta as três etapas. Enquanto grava e reconhece, não desenha a letra. Com linhas sincronizadas, mostra a anterior, a atual e a próxima. Sem letra utilizável, mostra a frase de erro e esconde.

A janela é transparente, sem borda, sempre por cima, e nasce oculta. Ela entra em todos os desktops (`CanJoinAllSpaces` e `FullScreenAuxiliary`). O ícone da barra de menus é o `iconTemplate.png`, 18×18 pontos, marcado como template. O ícone do Dock é essa mesma silhueta, em branco, num quadrado escuro, desenhado na abertura.

O atalho é um monitor do AppKit (`NSEvent`), global e local, criado na thread da interface. A combinação salva chama a mesma função do item **Ouvir**. ⌘⇧↓ centraliza.

No fim da letra, se **Ouvir a próxima sozinho** estiver ligado, o ciclo volta para o passo 1. Falha de reconhecimento ou faixa sem letra interrompe a cadeia.

## Configuração

`settings.py` lê e grava o JSON em `~/Library/Application Support/karaoke-hud/`. O menu da barra é só a vista dessa configuração: tamanho, cor, fundo, microfone, atalho, posição da janela e item de login. `python tests/test_settings.py` cobre o JSON, o atalho e o formato do menu sem abrir a janela.

## Testar uma etapa sem abrir o HUD

Grave com a música no ar, reconheça, e só então peça a letra:

```bash
python record.py
python identify.py
python get_lyrics.py "Artista que apareceu" "Título que apareceu"
```

`sample.wav` fica na pasta do projeto e não entra no git.
