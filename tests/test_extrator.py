"""Testes do núcleo (sem rede). Rodar com: python tests/test_extrator.py  (ou pytest)"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from extrator.dados import CAMPOS, DIAS_SEMANA, sortear_conjunto  # noqa: E402
from extrator.metricas import avaliar  # noqa: E402
from extrator.prompt import ler_resposta, mensagens_extracao, resposta_esperada  # noqa: E402


def test_sorteio_deterministico_e_consistente():
    a, b = sortear_conjunto("t", 300, 7), sortear_conjunto("t", 300, 7)
    assert a == b
    for ex in a:
        r, hoje = ex["rotulo"], date.fromisoformat(ex["hoje"])
        assert set(r) == set(CAMPOS)
        assert not (r["hora"] and r["periodo"])
        assert (r["data"] is None) == (ex["dica"]["data"] is None)
        if r["servico"]:
            assert r["servico"] in ex["negocio"]["servicos"]
        if r["data"]:
            alvo, dica = date.fromisoformat(r["data"]), ex["dica"]["data"]
            assert alvo >= hoje
            if dica in DIAS_SEMANA:
                assert 1 <= (alvo - hoje).days <= 7 and DIAS_SEMANA[alvo.weekday()] == dica
            if dica.startswith("dia "):
                assert alvo.day == int(dica[4:]) and alvo.day != hoje.day


def test_ler_resposta():
    texto = '```json\n{"intencao": "Agendar", "servico": "corte", "profissional": null, "data": "2026-11-05", "hora": "9:00", "periodo": "manhã"}\n```'
    assert ler_resposta(texto) == {"intencao": "agendar", "servico": "corte", "profissional": None,
                                   "data": "2026-11-05", "hora": "09:00", "periodo": "manha"}
    assert ler_resposta("não sei") is None
    assert ler_resposta("{quebrado") is None
    assert ler_resposta('{"intencao": "outro"}')["hora"] is None


def test_metricas():
    ex = sortear_conjunto("t", 2, 1)
    certo = ler_resposta(resposta_esperada(ex[0]["rotulo"]))
    m = avaliar(ex, [certo, None])
    assert m["exata"] == 0.5 and m["json_valido"] == 0.5 and m["intencao"] == 0.5


def test_prompt_tem_catalogo():
    ex = sortear_conjunto("t", 1, 3)[0] | {"mensagem": "oi"}
    sistema, usuario = mensagens_extracao(ex)
    assert ex["negocio"]["servicos"][0] in sistema["content"] and usuario["content"] == "oi"


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
    print("ok")
