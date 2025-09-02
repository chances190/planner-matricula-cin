# Planejador de Matrícula

Uma ferramenta de linha de comando para ajudar estudantes a planejar sua grade horária e matrícula em disciplinas.

## Características

- Carrega dados de disciplinas de um arquivo CSV ou de uma planilha do Google
- Permite buscar disciplinas por código, nome ou horário
- Detecta automaticamente conflitos de horário
- Exibe a grade horária semanal das disciplinas selecionadas
- Salva suas seleções para uso posterior
- Suporte a busca aproximada por nome de disciplinas
- Permite adicionar e remover disciplinas do cronograma

## Instalação

1. Clone ou baixe este repositório
2. Instale as dependências:

```bash
python -m venv env
# No Linux/MacOS:
source ./env/bin/activate
# No Windows:
.\env\Scripts\activate.ps1
```

```bash
pip install -r requirements.txt
```

## Uso

Execute o programa com o comando:

```bash
./planner.py <comando> [opções]
```

## Comandos Disponíveis

### help
Use `-h`/`--help` no comando principal ou em qualquer subcomando para ver opções detalhadas:

```bash
./planner.py -h
./planner.py <comando> -h
```

### download
Baixa dados de disciplinas do SecGrad (planilha Google publicada em formato "pubhtml") e formata como CSV.

Uso:
```bash
./planner.py download <url> [--output <arquivo>]
```

Opções:
- `<url>`: URL da planilha.
- `--output`, `-o`: arquivo CSV de saída (padrão: disciplinas.csv).

### list
Lista todas as disciplinas a partir do CSV.

Uso:
```bash
./planner.py list [--csv <arquivo>]
```

### search
Busca disciplinas por código, nome ou horário.

Uso:
```bash
./planner.py search [--csv <arquivo>] <tipo> <valor>
```

Tipos:
- `code <codigo_da_disciplina>`: busca por código exato da disciplina.
- `name <nome ...>`: busca aproximada por nome.
- `time <codigo_de_horário>`: busca por código de horário SIGAA (ex.: 2M123).

Exemplos:
```bash
./planner.py search -c disciplinas.csv code IF688
./planner.py search -c disciplinas.csv name "Teo.Implemen."
./planner.py search -c disciplinas.csv time 3T123
```

### add
Adiciona uma disciplina ao cronograma (por padrão, salva em selecoes.json). Suporta adicionar por código ou por nome (busca aproximada).

Uso:
```bash
./planner.py add [--csv <arquivo>] [--savefile <arquivo>] <tipo> <valor>
```

Tipos:
- `code <codigo_da_disiciplina>`: adiciona a turma correspondente ao código.
- `name <nome...>`: busca aproximada por nome; se houver múltiplos resultados, especifique por código.

Exemplos:
```bash
./planner.py add -c disciplinas.csv -s selecoes.json code CIN0132
./planner.py add -c disciplinas.csv name "Matemática Discreta"
```

### remove
Remove uma disciplina selecionada do cronograma. Atualmente só há remoção por código. Se houver múltiplas turmas selecionadas para o mesmo código, o comando lista as turmas para que você especifique a desejada.

Uso:
```bash
./planner.py remove [--csv <arquivo>] [--savefile <arquivo>] code <codigo_da_disciplina>
```

### schedule
Exibe as disciplinas atualmente selecionadas e imprime um cronograma semanal.

Uso:
```bash
./planner.py schedule [--csv <arquivo>] [--savefile <arquivo>]
```


## Códigos de Horário do SIGAA

Os horários são descritos pelos códigos do SIGAA. Ex.:
- `2M123`: Segunda-feira, Manhã, 1ª, 2ª e 3ª horas
- `4T45`: Quarta-feira, Tarde, 4ª e 5ª horas

### Cheatsheet

- **Dias**: 
    - `2` = Segunda-feira
    - `3` = Terça-feira
    - `4` = Quarta-feira
    - `5` = Quinta-feira
    - `6` = Sexta-feira
    - `7` = Sábado
- **Períodos**:
    - `M` = Manhã
    - `T` = Tarde
    - `N` = Noite
- **Horas**:
    - **Manhã**:
        - `1` = 06:00 - 06:50
        - `2` = 07:00 - 07:50
        - `3` = 08:00 - 08:50
        - `4` = 09:00 - 09:50
        - `5` = 10:00 - 10:50
        - `6` = 11:00 - 11:50
    - **Tarde**:
        - `1` = 12:00 - 12:50
        - `2` = 13:00 - 13:50
        - `3` = 14:00 - 14:50
        - `4` = 15:00 - 15:50
        - `5` = 16:00 - 16:50
        - `6` = 17:00 - 17:50
    - **Noite**:
        - `1` = 18:00 - 18:50
        - `2` = 18:50 - 19:40
        - `3` = 19:40 - 20:30
        - `4` = 20:30 - 21:20
        - `5` = 21:20 - 22:10
        - `6` = 22:10 - 23:00