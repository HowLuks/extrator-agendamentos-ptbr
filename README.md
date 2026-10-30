# Extrator de agendamentos em português

Um modelo pequeno (Qwen2.5-1.5B-Instruct ajustado com LoRA) que lê a mensagem de WhatsApp de um cliente e devolve o
pedido de agendamento em JSON. A comparação é com o próprio Qwen sem ajuste e com o Gemini 2.5 Flash, que é o modelo
usado hoje no atendente do [ZapMark](https://github.com/HowLuks/ZapMark).

```
Hoje: sexta-feira, 13 de novembro de 2026 · Barbearia · Serviços: corte, barba, corte e barba... · Profissionais: Rafael, Diego, Thiago

"opa, consegue encaixar um corte e barba com o diego amanha la pras 15h?"

{"intencao": "agendar", "servico": "corte e barba", "profissional": "Diego",
 "data": "2026-11-14", "hora": "15:00", "periodo": null}
```

## Por que

Num produto de agendamento pelo WhatsApp, cada mensagem passa por um LLM grande via API: custa por chamada, depende de
cota e manda a conversa do cliente para fora. Extrair intenção, serviço, data e hora é uma tarefa estreita, e a pergunta
do projeto é se um modelo de 1,5B ajustado chega perto do Gemini nela, rodando em hardware próprio.

## Como funciona

- **Saída:** `intencao` (agendar, remarcar, cancelar, consultar, outro), `servico` e `profissional` (nomes exatos do
  catálogo do negócio), `data` (AAAA-MM-DD), `hora` (HH:MM) e `periodo` (manha, tarde, noite, quando não há hora).
- **Prompt:** o catálogo do negócio e a data de hoje vão no prompt de sistema ([extrator/prompt.py](extrator/prompt.py)),
  como no ZapMark. Assim o modelo escolhe nomes de uma lista e resolve "amanhã" ou "sexta" para uma data, e a avaliação é
  exata, sem comparar texto livre. O mesmo prompt é usado para todos os modelos.
- **Dados sintéticos:** o rótulo é sorteado primeiro ([extrator/dados.py](extrator/dados.py)) e a mensagem é escrita
  depois a partir dele. O gabarito fica correto por construção e não há dado de cliente real. Os campos vazios são
  proibidos explicitamente na instrução ("NÃO mencione data"), senão o LLM completa sozinho e o gabarito fica errado.
- **Autores:** parte das mensagens foi escrita pelo Gemini e parte pelo Claude (campo `autor`). Isso permite medir se o
  Gemini vai melhor nas mensagens que ele mesmo escreveu.
- **Teste revisado à mão:** só entram na avaliação as mensagens do teste conferidas uma a uma.

## Resultados

_Pendente: preenchido depois da revisão do teste e do treino no Kaggle._

| modelo | JSON válido | exata | intenção | serviço | profissional | data | hora | período |
|---|---|---|---|---|---|---|---|---|
| Qwen2.5-1.5B base | | | | | | | | |
| Qwen2.5-1.5B + LoRA | | | | | | | | |
| Gemini 2.5 Flash | | | | | | | | |

"Exata" é a fração de mensagens com todos os campos certos.

## Estrutura

```
extrator/        catálogos, sorteio dos rótulos, prompt, leitura da resposta e métricas
scripts/         gerar_dados.py, revisar_teste.py, avaliar_gemini.py
dados/           treino.jsonl e teste.jsonl (um exemplo por linha)
notebooks/       treino_kaggle.ipynb: LoRA, avaliação e publicação no Hugging Face
resultados/      respostas e métricas do Gemini
tests/           testes do núcleo, sem rede
```

## Como rodar

Geração de dados e avaliação do Gemini, local (Python 3.10+):

```bash
pip install -r requirements.txt
cp .env.example .env                                         # coloque a GEMINI_API_KEY
python scripts/gerar_dados.py gemini --conjunto treino       # escreve as mensagens que faltam; retoma de onde parou
python scripts/revisar_teste.py                              # revisão manual do teste
python scripts/avaliar_gemini.py                             # métricas do Gemini no teste revisado
python tests/test_extrator.py
```

O plano gratuito da API do Gemini dá poucas requisições por dia; os scripts param quando a cota acaba e continuam do
ponto em que pararam na próxima execução.

Treino: abra `notebooks/treino_kaggle.ipynb` no Kaggle com GPU T4, internet ligada e o secret `HF_TOKEN`.

## Limitações

- Mensagens escritas por LLMs são mais limpas que as reais.
- Cada mensagem é lida sozinha, sem o histórico da conversa.
- Os catálogos são poucos e fixos (8 tipos de negócio).
