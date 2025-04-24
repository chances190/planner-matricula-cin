# Planejador de Matrícula

Uma ferramenta de linha de comando para ajudar estudantes a planejar sua grade horária e matrícula em disciplinas.

## Características

- Carrega dados de disciplinas de um arquivo CSV
- Permite buscar disciplinas por código, nome ou horário
- Detecta automaticamente conflitos de horário
- Exibe a grade horária semanal das disciplinas selecionadas
- Salva suas seleções para uso posterior

## Instalação

1. Clone ou baixe este repositório
2. Instale as dependências:

```bash
pip install -r requirements.txt
```

## Uso

Execute o programa com o comando:

```bash
python planner.py [caminho_do_arquivo.csv]
```

Se não especificar um arquivo CSV, o programa tentará usar o primeiro CSV no diretório atual.

## Formato do CSV

O arquivo CSV deve conter as seguintes colunas:
- Órgão ofertante
- Turma
- Código
- Disciplina
- Docente
- Horário
- Sala/Lab

O CSV incluido nesse repositório foi feito a partir dos [Horário das disciplinas do semestre 2025.1](https://docs.google.com/spreadsheets/d/e/2PACX-1vSJU0kVE4IA0oB-Q81s2ln2PPbfNLNYPrjqM_18C02RXwmH_9_8JsyuA2OC27RxaML0pFWxx2sHlpnK/pubhtml), disponibilizado pelo SecGrad.

## Comandos Disponíveis

- `list` - Lista todas as disciplinas
- `print` - Mostra o cronograma
- `add <num>` - Adiciona disciplina pelo número da lista
- `add -c <código>` - Adiciona disciplina pelo código
- `add -n <nome>` - Adiciona disciplina pelo nome (busca aproximada)
- `add -t <horário>` - Adiciona disciplina pelo código de horário
- `remove <num>` - Remove disciplina pelo número da lista
- `remove -c <código>` - Remove disciplina pelo código
- `help` - Mostra ajuda
- `exit` - Sair do programa

## Códigos de Horário

Os horários são descritos pelos códigos do SIGAA:
- `2M123` = Segunda-feira, Manhã, 1ª, 2ª e 3ª horas
- `4T45` = Quarta-feira, Tarde, 4ª e 5ª horas

### Explicação dos Códigos
- **Dias**: 
    - `2` = Segunda-feira
    - `3` = Terça-feira
    - `4` = Quarta-feira
    - `5` = Quinta-feira
    - `6` = Sexta-feira
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
        - `7` = 18:00 - 18:50
    - **Noite**:
        - `1` = 18:00 - 18:50
        - `2` = 18:50 - 19:40
        - `3` = 19:40 - 20:30
        - `4` = 20:30 - 21:20
        - `5` = 21:20 - 22:10
        - `6` = 22:10 - 23:00