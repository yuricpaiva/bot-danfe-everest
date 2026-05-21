# Espelho PostgreSQL - 505_previsao_impostos_saida

Projeto Python para sincronizar a tabela MySQL `c2025029`.`505_previsao_impostos_saida` do Everest para a tabela PostgreSQL `raw.tb_505_previsao_impostos_saida`.

A estratégia inicial é refresh por janela de data usando a coluna `D. Lançamento`: a rotina apaga no PostgreSQL os registros da janela `[data_inicio, data_fim)` e insere novamente os dados extraídos do MySQL. Nenhuma escrita é feita no MySQL.

## Configuração

Crie o ambiente virtual e instale as dependências:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Copie `.env.example` para `.env` e preencha as credenciais:

```env
MYSQL_HOST=seu_host_mysql
MYSQL_PORT=3306
MYSQL_DATABASE=c2025029
MYSQL_USER=seu_usuario
MYSQL_PASSWORD=sua_senha
MYSQL_CHARSET=latin1

POSTGRES_HOST=seu_host_postgres
POSTGRES_PORT=5438
POSTGRES_DATABASE=everest_impostos_db
POSTGRES_USER=admin
POSTGRES_PASSWORD=sua_senha
POSTGRES_SCHEMA=raw
POSTGRES_TABLE=tb_505_previsao_impostos_saida

CHUNK_SIZE=5000
MYSQL_SOURCE_TABLE=505_previsao_impostos_saida
DATE_COLUMN=D. Lançamento
LOG_LEVEL=INFO
```

## Criar tabela destino

O arquivo esperado é `sql/create_tb_505_previsao_impostos_saida.sql`. Se `inventario_mysql.json` estiver disponível, ele pode ser usado como referência para revisar o DDL final.

Também é possível gerar o DDL consultando `INFORMATION_SCHEMA.COLUMNS` no MySQL, em modo leitura:

```bash
python src/load_505_previsao_impostos_saida.py --data-inicio 1900-01-01 --data-fim 1900-01-02 --write-create-sql
```

Para gerar o SQL e já criar a tabela no PostgreSQL:

```bash
python src/load_505_previsao_impostos_saida.py --data-inicio 2025-01-01 --data-fim 2025-02-01 --write-create-sql --create-table
```

## Carga inicial

Rode por períodos menores para reduzir risco operacional. Exemplo mensal:

```bash
python src/load_505_previsao_impostos_saida.py --data-inicio 2025-01-01 --data-fim 2025-02-01
python src/load_505_previsao_impostos_saida.py --data-inicio 2025-02-01 --data-fim 2025-03-01
```

A data final é exclusiva. A janela `2025-01-01` até `2025-02-01` carrega registros com `D. Lançamento >= 2025-01-01` e `< 2025-02-01`.

## Atualização por período

Para recarregar uma janela recente:

```bash
python src/load_505_previsao_impostos_saida.py --data-inicio 2026-05-01 --data-fim 2026-05-21
```

Se houver erro durante a exclusão ou inserção, a transação no PostgreSQL é revertida com rollback.

## Agendamento no cron

Exemplo para rodar diariamente às 03:00 recarregando os últimos 7 dias:

```bash
0 3 * * * cd /caminho/bot-danfe && /caminho/bot-danfe/.venv/bin/python src/load_505_previsao_impostos_saida.py --data-inicio "$(date -d '7 days ago' +\%F)" --data-fim "$(date -d 'tomorrow' +\%F)" >> logs/load_505.log 2>&1
```

Crie a pasta de logs antes:

```bash
mkdir -p logs
```
