# De 18% para 90%: ajustando um modelo de 1,5B para ler agendamentos no WhatsApp

Quem vende serviço pelo WhatsApp (barbearia, salão, clínica, pet shop) recebe o dia inteiro mensagens como esta:

> opa, consegue encaixar um corte e barba com o diego amanha la pras 15h?

Para um sistema de agendamento, essa frase precisa virar dado estruturado: o cliente quer **agendar**, o serviço é
**corte e barba**, o profissional é o **Diego**, a data é **amanhã** (que precisa virar uma data de calendário) e a hora
é **15:00**. Hoje, em produtos como o [ZapMark](https://github.com/HowLuks/ZapMark), esse trabalho vai para um LLM grande
por API. Funciona, mas cada mensagem custa uma chamada, depende de cota e manda a conversa do cliente para um servidor de
terceiros.

A pergunta deste projeto é simples: **um modelo pequeno, que roda em hardware próprio, dá conta dessa tarefa depois de
um ajuste fino?** Para responder, peguei o Qwen2.5-1.5B-Instruct, ajustei com LoRA em 600 mensagens e comparei o modelo
antes e depois. O código, os dados e o notebook estão em
[github.com/HowLuks/extrator-agendamentos-ptbr](https://github.com/HowLuks/extrator-agendamentos-ptbr) e o modelo em
[huggingface.co/HowLuks/qwen2.5-1.5b-extrator-agendamentos-ptbr](https://huggingface.co/HowLuks/qwen2.5-1.5b-extrator-agendamentos-ptbr).

## A tarefa

O modelo recebe a mensagem e devolve um JSON com seis campos:

| campo | valores |
|---|---|
| `intencao` | agendar, remarcar, cancelar, consultar (perguntar se há horário) ou outro |
| `servico` | o nome exato de um serviço do catálogo do negócio, ou `null` |
| `profissional` | o nome exato de um profissional do catálogo, ou `null` |
| `data` | AAAA-MM-DD, resolvendo "amanhã", "sexta" ou "dia 12" a partir de hoje |
| `hora` | HH:MM |
| `periodo` | manhã, tarde ou noite, quando o cliente não diz a hora |

Uma decisão de desenho ajudou muito: **o catálogo do negócio e a data de hoje vão no prompt de sistema**. Assim o modelo
não precisa adivinhar como o serviço se chama, só escolher de uma lista, e "amanhã" tem uma referência. É também como o
ZapMark funciona, e deixa a avaliação exata: o campo está certo ou errado, sem comparar texto livre.

## Os dados: rótulo primeiro, mensagem depois

Não há dataset público de mensagens de agendamento em português, e usar conversa de cliente real traria problema de
privacidade. A saída foi gerar os dados ao contrário do normal: **primeiro sorteio o rótulo** (negócio, intenção,
serviço, data, hora), **depois peço para um LLM escrever a mensagem** que corresponde a ele. Como o gabarito existe antes
da mensagem, ele é correto por construção.

Dois detalhes fizeram diferença:

- **Proibir os campos vazios.** Se o rótulo não tem data, a instrução diz explicitamente "NÃO mencione data nem dia da
  semana". Sem isso, o LLM completa a mensagem com um "amanhã" por conta própria e o gabarito fica errado.
- **Variar a forma, não só o conteúdo.** A data aparece como "hoje", "amanhã", "sexta", "dia 12" ou "12/03", e o estilo
  pede abreviação, falta de acento e erro de digitação leve, como gente de verdade escreve.

As mensagens foram escritas por duas fontes, registradas no campo `autor`: parte pela sessão que montou o projeto, que
conhecia o formato da tarefa, e parte por agentes independentes, que receberam só a instrução de cada mensagem, sem saber
para que ela serviria. Separar os autores na avaliação mostra se o modelo aprendeu a tarefa ou só o jeito de escrever de
quem montou os dados.

No fim ficaram 600 mensagens de treino e 300 de teste, em 8 tipos de negócio.

## O ajuste

O treino roda num notebook público do Kaggle, numa GPU T4 gratuita. A configuração é deliberadamente comum:

- **Modelo base:** Qwen2.5-1.5B-Instruct, em fp16.
- **LoRA:** rank 16, alpha 32, dropout 0,05, aplicado a todas as camadas lineares. Só o adaptador é treinado e
  publicado, e o modelo base fica intacto.
- **Treino:** 3 épocas, taxa de aprendizado 2e-4 com decaimento cosseno, lote efetivo de 16 (4 × 4 de acumulação de
  gradiente), com 10% do treino separado para validação.
- **Perda só na resposta:** o exemplo vai no formato prompt/completion, então o modelo é cobrado só pelo JSON que gera,
  não por reproduzir o prompt de sistema com o catálogo.

O notebook inteiro, com instalação, download do modelo, treino, avaliação dos dois modelos e publicação, roda em cerca
de 15 minutos.

## Resultados

Os dois modelos recebem exatamente o mesmo prompt. "Exata" é a fração de mensagens com **os seis campos certos ao mesmo
tempo**, que é o que importa na prática: um agendamento com a data errada é um agendamento errado.

| modelo | JSON válido | exata | intenção | serviço | profissional | data | hora | período |
|---|---|---|---|---|---|---|---|---|
| Qwen2.5-1.5B base | 100,0% | 18,3% | 84,7% | 82,0% | 91,7% | 50,0% | 85,7% | 65,0% |
| Qwen2.5-1.5B + LoRA | 100,0% | **89,7%** | 98,0% | 99,7% | 99,3% | 92,7% | 100,0% | 100,0% |

### O modelo base já entende o formato, mas não a tarefa

O Qwen sem ajuste devolve JSON válido em 100% dos casos: seguir um formato pedido no prompt não é o problema. O problema
aparece campo a campo. Ele acerta a intenção em 85% e o profissional em 92%, mas cai para 50% na data e 65% no período.
Como o acerto exato exige todos os campos certos juntos, esses erros se multiplicam e só 18% das mensagens saem
perfeitas.

### O ajuste resolve quase tudo, e a data é o que sobra

Com o LoRA, quatro campos passam de 99%, e hora e período chegam a 100%. A data sobe de 50% para 92,7%, mas continua
sendo o campo mais fraco, e o motivo faz sentido: é o único que exige **conta**, não leitura. Para transformar "sexta"
em uma data, o modelo precisa saber que hoje é quarta, dia 4, e somar dois dias, virando o mês se for o caso. Os outros
campos são, no fundo, reconhecer um trecho da mensagem e copiá-lo ou mapeá-lo para uma lista.

### O resultado não depende de quem escreveu as mensagens

| autor | mensagens | exata (LoRA) | exata (base) |
|---|---|---|---|
| sessão que montou o projeto | 100 | 87,0% | 21,0% |
| agentes independentes | 200 | 91,0% | 17,0% |

Se o modelo tivesse aprendido só os vícios de escrita de quem montou os dados, ele iria melhor nessas mensagens. Foi o
contrário: o acerto é até um pouco maior nas mensagens dos agentes que não sabiam da tarefa.

### O que os erros mostram

Olhar as respostas uma a uma conta mais do que a tabela. Alguns casos do teste:

**O modelo base preenche o que não foi dito.** Para "preciso remarcar meu horario, quando tem disponivel?", que não traz
data nem hora, ele respondeu `"data": "2027-01-06", "hora": "19:00", "periodo": "noite"`. Para "bom dia, consigo
marcar com o Marcos as 10h?", inventou o serviço (massagem relaxante) e a data. Ele também marca período junto com a
hora, mesmo quando os dois se contradizem: "amanha 16h30" saiu com `"periodo": "manha"`.

**O modelo base sai da lista.** O prompt diz quais são as intenções possíveis, mas ele responde "alterar" no lugar de
"remarcar". Ele escreve o serviço como `sessao_de_casal` ou `avaliacao_fisica` em vez do nome do catálogo e põe o dia
da semana no campo de período (`"periodo": "domingo"`). Também lê números ao pé da letra: "um orçamento dia 4 de manhã"
virou `"hora": "04:00"`.

**O modelo base confunde "outro" com "consultar".** "Quanto custa?", "oi, onde fica o estudio?" e "qual o endereço da
barbearia?" saíram como `consultar`, ou seja, como se o cliente perguntasse por horário livre. O ajustado acerta esses
casos.

**Os erros do ajustado são mais sutis, e alguns são instrutivos.** Com hoje em quinta, 25 de fevereiro de 2027,
"primeira consulta na quarta às 13h30" deveria virar 3 de março. O modelo respondeu `"data": "2027-02-30"`, uma data
que não existe: ele somou os dias sem virar o mês. Esse é exatamente o tipo de conta que um modelo de linguagem faz mal
e que um código de três linhas faz certo. Em outro caso, "hidratação de pelo pro thor" saiu com `"profissional":
"Thor"`: o modelo tomou o nome do cachorro por um profissional, que nem está no catálogo.

Os dois erros apontam para correções baratas fora do modelo: validar que a data existe e que o profissional está no
catálogo antes de aceitar a resposta, ou pedir ao modelo uma data relativa ("próxima quarta") e deixar a conta para o
código.

## O que isso diz (e o que ainda não diz)

Para uma tarefa estreita e bem definida, um ajuste barato muda o jogo: 15 minutos numa GPU gratuita levaram um modelo de
1,5B de inútil para útil. O adaptador ocupa uma fração do tamanho do modelo, e o modelo inteiro cabe numa máquina comum.

Mas os números ainda não permitem dizer que o modelo pequeno "substitui" o LLM grande, por três razões:

1. **Falta a referência.** O próximo passo é rodar o Gemini 2.5 Flash, o modelo que o ZapMark usa hoje, no mesmo teste.
   Sem ele, não dá para saber se 89,7% está perto ou longe do que um modelo grande consegue.
2. **O teste ainda não foi revisado à mão.** O gabarito é correto por construção, mas uma mensagem gerada pode ter
   saído ambígua ou ter escapado da instrução. A revisão manual das 300 mensagens de teste vem antes do resultado final.
3. **Os dados são sintéticos.** Mensagens escritas por LLM são mais limpas do que as reais, e treino e teste vêm do mesmo
   processo de geração. Num produto, o próximo passo seria avaliar em mensagens reais (anonimizadas) antes de trocar
   qualquer coisa.

Há também limites da própria tarefa: cada mensagem é lida sozinha, sem o histórico da conversa ("pode ser às 15h então"
depende do que veio antes), e são só 8 catálogos fixos.

## Próximos passos

- Revisar o teste à mão e rodar o Gemini no mesmo conjunto.
- Contar os erros de data por tipo (dia da semana, virada de mês, "dia N") e testar a validação da data e do catálogo
  fora do modelo.
- Testar o modelo em mensagens reais anonimizadas.

---

Código, dados e notebook: [github.com/HowLuks/extrator-agendamentos-ptbr](https://github.com/HowLuks/extrator-agendamentos-ptbr) ·
Modelo: [huggingface.co/HowLuks/qwen2.5-1.5b-extrator-agendamentos-ptbr](https://huggingface.co/HowLuks/qwen2.5-1.5b-extrator-agendamentos-ptbr)
