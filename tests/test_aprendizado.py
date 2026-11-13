"""Aprendizado contínuo (guia CINEX-EDICAO-E-APRENDIZADO): escopos isolados, precedência, aprovação obrigatória,
versões reversíveis, correções classificadas e experimentos que não viram regra sozinhos."""
import json, os, shutil, sys, tempfile, unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))
import aprendizado as A  # noqa: E402


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(REPO / "conhecimento", self.tmp / "conhecimento")           # nunca mexe no conhecimento real
        self.env = {k: os.environ.get(k) for k in ("CINEX_APRENDIZADO", "CINEX_MARCAS", "CINEX_ROOT", "CINEX_CONHECIMENTO")}
        os.environ.update(CINEX_APRENDIZADO=str(self.tmp / "local"), CINEX_MARCAS=str(self.tmp / "marcas"),
                          CINEX_ROOT=str(self.tmp / "reels"), CINEX_CONHECIMENTO=str(self.tmp / "conhecimento"))
        for h, nome in (("marcaum", "Marca Um Solar"), ("marcadois", "Marca Dois")):
            (self.tmp / "marcas" / h).mkdir(parents=True)
            (self.tmp / "marcas" / h / "marca.json").write_text(json.dumps({"nome": nome}), encoding="utf-8")

    def tearDown(self):
        for k, v in self.env.items():
            if v is None: os.environ.pop(k, None)
            else: os.environ[k] = v
        shutil.rmtree(self.tmp, ignore_errors=True)

    def prop(self, **kw):
        base = dict(titulo="t", descricao="d", escopo="marca", alvo="marca:marcaum", tipo="regra", problema="p",
                    evidencias=["e"], confianca="media", limitacoes="l", efeitos_colaterais="x",
                    mudancas=[dict(chave="legenda.cor_destaque", para="#FFCD28")], impacto_esperado="i")
        base.update(kw); return base


class FormatosTest(Base):
    def test_oito_perfis_independentes(self):
        f = A.formatos()
        self.assertEqual(sorted(f), sorted(["talking_head", "split_screen", "lists_rankings", "before_after",
                                            "behind_the_scenes", "myths_facts", "visualization_3d", "testimonial"]))
        tec = A.conh("tecnicas")["tecnicas"]
        for fid, p in f.items():
            for t in p["tecnicas"] + p["evitar"]: self.assertIn(t, tec, f"{fid}: técnica {t} sem catálogo")
            self.assertTrue(p["aprende"]); self.assertGreaterEqual(p["versao"], 1)

    def test_tecnicas_dizem_quando_evitar(self):
        for k, t in A.conh("tecnicas")["tecnicas"].items():
            self.assertIn(t["suporte"], ("sim", "parcial", "nao"), k)
            self.assertIn("quando_evitar", t, k)
            if t["tipo"] == "tecnica": self.assertTrue(t["quando_usar"], k)

    def test_formats_py_le_os_perfis(self):
        import formats                                            # o motor lê os mesmos 8 perfis oficiais
        self.assertEqual(sorted(formats.formats()), sorted(A.formatos()))
        self.assertEqual(formats.fmt("testimonial")["id"], "testimonial")


class PrecedenciaTest(Base):
    def test_projeto_vence_marca_que_vence_formato_que_vence_global(self):
        A.projeto_init("p1", "marcaum", "talking_head")
        r = A.resolver("talking_head", "marcaum")
        self.assertEqual(r["legenda.borda"]["valor"], False)
        self.assertTrue(r["legenda.borda"]["origem"].startswith("global"))
        self.assertEqual(r["formato.cap_y"]["valor"], 1300)
        A.aprovar(A.propor(self.prop(mudancas=[dict(chave="formato.cap_y", para=1450)]))["id"], "dono", "marcaum")
        r = A.resolver("talking_head", "marcaum")
        self.assertEqual(r["formato.cap_y"]["valor"], 1450); self.assertIn("marca @marcaum", r["formato.cap_y"]["origem"])
        pj = A.projeto_need("p1"); pj["instrucoes"]["formato.cap_y"] = dict(valor=1500); A.wj(A.project_file("p1"), pj)
        r = A.resolver(None, projeto="p1")
        self.assertEqual(r["formato.cap_y"]["valor"], 1500); self.assertEqual(r["formato.cap_y"]["origem"], "projeto p1")

    def test_preferencia_por_formato_da_marca(self):
        A.aprovar(A.propor(self.prop(alvo="marca:marcaum/formato:testimonial",
                                     mudancas=[dict(chave="legenda.max_palavras", para=2)]))["id"], "dono", "marcaum")
        self.assertEqual(A.resolver("testimonial", "marcaum")["legenda.max_palavras"]["valor"], 2)
        self.assertEqual(A.resolver("talking_head", "marcaum")["legenda.max_palavras"]["valor"], 3)

    def test_combinacao_formato_principal_vence(self):
        r = A.resolver("testimonial", combina=["before_after"])
        self.assertEqual(r["formato.montagem"]["valor"], "cut")
        s = A.sugerir("testimonial", combina=["before_after"])
        ids = [t["id"] for t in s["usar"]]
        self.assertIn("mesmo_angulo_antes_depois", ids); self.assertIn("corte_pausas_natural", ids)
        self.assertIn("efeito_sem_funcao", [t["id"] for t in s["evitar"]])


class IsolamentoTest(Base):
    def test_marcas_nao_se_misturam(self):
        A.aprovar(A.propor(self.prop())["id"], "dono", "marcaum")
        self.assertEqual(A.resolver("talking_head", "marcaum")["legenda.cor_destaque"]["valor"], "#FFCD28")
        self.assertNotIn("legenda.cor_destaque", A.resolver("talking_head", "marcadois"))
        self.assertEqual(A.propostas(marca="marcadois"), [])
        self.assertEqual(A.propostas(), [])                       # proposta de marca não aparece na lista global

    def test_proposta_global_nao_cita_marca(self):
        with self.assertRaises(SystemExit):
            A.propor(self.prop(escopo="global", alvo="global", evidencias=["visto nos vídeos da @marcaum"]))
        with self.assertRaises(SystemExit):
            A.propor(self.prop(escopo="global", alvo="global", problema="a Marca Um Solar reclamou"))
        A.propor(self.prop(escopo="global", alvo="global", evidencias=["padrão em 4 projetos de 2 marcas"]))

    def test_correcao_global_anonima(self):
        A.projeto_init("p1", "marcaum", "talking_head")
        rec, aviso = A.corrigir("p1", "erro_tecnico", "audio", "pico acima de -1 dBTP na Marca Um Solar")
        self.assertIn("marca um solar", aviso.lower()); self.assertEqual(A.readl(A.local_root() / "evidencias.jsonl"), [])
        rec, aviso = A.corrigir("p1", "erro_tecnico", "audio", "pico na Marca Um Solar", texto_geral="pico acima de -1 dBTP")
        ev = A.readl(A.local_root() / "evidencias.jsonl")
        self.assertIsNone(aviso); self.assertEqual(len(ev), 1)
        self.assertNotIn("marcaum", json.dumps(ev)); self.assertNotIn("p1", json.dumps(ev))


class GovernancaTest(Base):
    def test_nada_muda_sem_aprovacao(self):
        pr = A.propor(self.prop())
        self.assertEqual(pr["status"], "aguardando_aprovacao"); self.assertTrue(pr["requer_aprovacao"])
        self.assertNotIn("legenda.cor_destaque", A.prefs("marcaum")["regras"])
        with self.assertRaises(SystemExit): A.aprovar(pr["id"], "", "marcaum")          # aprovação explícita, com nome

    def test_contrato_completo(self):
        p = self.prop(); p.pop("limitacoes")
        with self.assertRaises(SystemExit): A.propor(p)
        with self.assertRaises(SystemExit): A.propor(self.prop(confianca="certeza"))

    def test_rascunho_precisa_ser_enviado(self):
        pr = A.propor(self.prop(), rascunho=True)
        with self.assertRaises(SystemExit): A.aprovar(pr["id"], "dono", "marcaum")
        A.enviar(pr["id"], "marcaum"); A.aprovar(pr["id"], "dono", "marcaum")

    def test_versao_e_reversao_do_formato(self):
        f0 = A.formatos()["lists_rankings"]
        pr = A.propor(self.prop(escopo="formato", alvo="formato:lists_rankings", marca=None,
                                mudancas=[dict(chave="duracao_s", para=[15, 35])]))
        pr = A.aprovar(pr["id"], "dono")
        f1 = A.formatos()["lists_rankings"]
        self.assertEqual(f1["duracao_s"], [15, 35]); self.assertEqual(f1["versao"], f0["versao"] + 1)
        self.assertEqual(A.formatos()["talking_head"]["duracao_s"], [20, 60])           # não propaga para outros formatos
        hist = A.conh_root() / "historico" / f"formatos.v{pr['versao_anterior']}.json"
        self.assertTrue(hist.exists())
        A.reverter(pr["id"], "dono", "duração curta demais")
        f2 = A.formatos()["lists_rankings"]
        self.assertEqual(f2["duracao_s"], f0["duracao_s"]); self.assertEqual(f2["versao"], f0["versao"] + 2)
        self.assertEqual([h["acao"] for h in A.historico()], ["aprovada", "revertida"])

    def test_reverter_regra_nova_remove(self):
        pr = A.aprovar(A.propor(self.prop())["id"], "dono", "marcaum")
        A.reverter(pr["id"], "dono", "não gostei", "marcaum")
        self.assertNotIn("legenda.cor_destaque", A.prefs("marcaum")["regras"])

    def test_rejeicao_fica_registrada_e_nao_vira_regra(self):
        pr = A.propor(self.prop())
        A.rejeitar(pr["id"], "dono", "prefiro manter", "marcaum")
        self.assertEqual(A.prefs("marcaum")["regras"], {})
        self.assertEqual(A.historico(marca="marcaum")[0]["acao"], "rejeitada")


class AprendizadoTest(Base):
    def test_correcoes_viram_hipotese_e_rascunho(self):
        for i in range(3):
            A.projeto_init(f"p{i}", "marcaum", "talking_head")
            A.corrigir(f"p{i}", "preferencia_marca", "legendas", "destaque amarelo", chave="legenda.cor_destaque", valor="#FFCD28")
        r = A.padroes("marcaum", propor_=True)
        self.assertEqual(r["padroes"][0]["n"], 3); self.assertEqual(r["padroes"][0]["confianca"], "media")
        pr = A.rj(A.prop_path(r["propostas_criadas"][0], "marcaum"))
        self.assertEqual(pr["status"], "rascunho")                                     # nunca aplica sozinho
        self.assertNotIn("legenda.cor_destaque", A.prefs("marcaum")["regras"])

    def test_padrao_global_exige_duas_marcas(self):
        for i, h in enumerate(["marcaum"] * 3):
            A.projeto_init(f"p{i}", h, "talking_head")
            A.corrigir(f"p{i}", "erro_tecnico", "legendas", "legenda sobre o rosto", chave="formato.cap_y", valor=1450)
        g = A.padroes()["padroes"][0]
        self.assertEqual(g["marcas"], 1); self.assertFalse(g["generalizavel"])
        A.projeto_init("q", "marcadois", "talking_head")
        A.corrigir("q", "erro_tecnico", "legendas", "legenda sobre o rosto", chave="formato.cap_y", valor=1450)
        self.assertTrue(A.padroes()["padroes"][0]["generalizavel"])

    def test_decisao_pontual_nao_vai_para_global(self):
        A.projeto_init("p1", "marcaum", "talking_head")
        A.corrigir("p1", "decisao_projeto", "cortes", "tirar a frase X neste vídeo")
        self.assertEqual(A.readl(A.local_root() / "evidencias.jsonl"), [])
        self.assertEqual(len(A.projeto_need("p1")["correcoes"]), 1)

    def test_avaliacao_separa_lentes(self):
        A.projeto_init("p1", "marcaum", "talking_head")
        av = A.avaliar("p1", {"dimensoes": {"narrativa": 4, "ritmo": 3}, "lentes": {"qualidade_tecnica": 5, "aderencia_marca": 4}})
        self.assertEqual(av["lentes"]["qualidade_tecnica"], 5)
        with self.assertRaises(SystemExit): A.avaliar("p1", {"dimensoes": {"narrativa": 7}})
        with self.assertRaises(SystemExit): A.avaliar("p1", {"dimensoes": {"views": 3}})

    def test_comparacao_so_com_comparaveis(self):
        for i in range(3):
            A.projeto_init(f"p{i}", "marcaum", "talking_head", objetivo="alcance")
            A.metricas(f"p{i}", {"views": 1000 * (i + 1), "compart": 10})
        A.projeto_init("x", "marcaum", "testimonial", objetivo="alcance"); A.metricas("x", {"views": 99999})
        c = A.comparar("marcaum", "talking_head", "alcance")
        self.assertEqual(c["n"], 3); self.assertEqual(c["medianas"]["views"], 2000); self.assertIn("hipótese", c["conclusao"])
        self.assertEqual(A.comparar("marcadois")["n"], 0)

    def test_experimento_pequeno_e_inconclusivo(self):
        e = A.experimento_criar(dict(hipotese="frase de impacto segura mais nos 3 s", formato="talking_head",
                                     variantes={"A": "frase de impacto", "B": "direto na fala", "C": "B-roll com narração"},
                                     constantes=["mesmo tema", "mesma duração"], metrica_principal="retencao_3s_pct"))
        A.experimento_resultado(e["id"], "A", "p1", {"retencao_3s_pct": 70})
        A.experimento_resultado(e["id"], "B", "p2", {"retencao_3s_pct": 40})
        self.assertIn("inconclusivo", A.experimento_avaliar(e["id"])["avaliacao"]["conclusao"])
        self.assertEqual(A.propostas(), [])

    def test_pesquisa_exige_origem(self):
        with self.assertRaises(SystemExit): A.pesquisa_add({"tecnica": "whip_pan"})
        r = A.pesquisa_add(dict(fonte="https://exemplo", tecnica="whip_pan", formatos=["behind_the_scenes"], tipo="tendencia",
                                custo="medio", adequacao="obra", comparacao_padrao="hoje usamos corte seco"))
        self.assertEqual(r["status"], "achado"); self.assertTrue(r["data_consulta"])

    def test_status_e_rotinas(self):
        s = A.status("marcaum")
        self.assertIn("atrasada", s["rotinas"]["pesquisa_de_tendencias"])
        A.marcar_rotina("pesquisa")
        self.assertIn("em dia", A.status()["rotinas"]["pesquisa_de_tendencias"])


class ResultadosTest(Base):
    def test_cumpriu_ou_nao(self):
        dados = [("a", 5000, ["cold_open"]), ("b", 4000, ["cold_open"]), ("c", 900, []), ("d", 800, []), ("e", 3000, ["cold_open"])]
        for p, views, tec in dados:
            A.projeto_init(p, "marcaum", "talking_head")
            A.definir_objetivo(p, "alcance", tecnicas=tec)
            A.metricas(p, {"views": views})
        A.projeto_init("m", "marcaum", "testimonial"); A.definir_objetivo("m", "compartilhamento", meta=50)
        A.metricas("m", {"compart": 20})
        r = A.resultados("marcaum")
        v = {x["projeto"]: x["veredito"] for x in r["por_video"]}
        self.assertEqual(v["a"], "cumpriu"); self.assertEqual(v["d"], "não cumpriu")
        self.assertEqual(v["m"], "não cumpriu")                         # meta definida: 20 < 50
        self.assertTrue(any("cold_open" in p["o_que"] and "cumpriram" in p["leitura"] for p in r["pistas"]))
        self.assertTrue((A.brand_dir("marcaum") / "resultados.md").exists())
        self.assertEqual(A.resultados("marcadois")["videos"], 0)        # outra marca não vê nada

    def test_sem_base_com_poucos_videos(self):
        A.projeto_init("a", "marcaum", "myths_facts"); A.definir_objetivo("a", "seguidores"); A.metricas("a", {"seguiu": 3})
        self.assertEqual(A.resultados("marcaum")["por_video"][0]["veredito"], "sem base")
        with self.assertRaises(SystemExit): A.definir_objetivo("a", "fama")


class ReferenciasTest(Base):
    def test_referencia_conferida_e_contagem(self):
        ok = dict(url="https://www.instagram.com/reel/abc/", autor="@editor", plataforma="Instagram", tipo="criador",
                  alvos=["formato:talking_head", "tecnica:cold_open"], insight="Abre com a frase mais forte antes do contexto.")
        A.referencia_add(ok)
        with self.assertRaises(SystemExit): A.referencia_add(ok)                                  # url repetida
        with self.assertRaises(SystemExit): A.referencia_add(dict(ok, url="https://x.y/1", alvos=["formato:tiktok"]))
        with self.assertRaises(SystemExit): A.referencia_add(dict(ok, url="https://x.y/2", insight="x" * 401))
        with self.assertRaises(SystemExit): A.referencia_add(dict(ok, url="http://x.y/3"))
        r = A.referencias()
        self.assertEqual(r["total"], 1); self.assertEqual(r["faltando"]["formato:talking_head"], 9)
        self.assertEqual(len(A.referencias("tecnica:cold_open")), 1)


class DesempenhoTest(Base):
    def test_aplicar_vira_proposta_e_nao_muda_a_marca(self):
        import importlib, desempenho as D
        importlib.reload(D)                                      # ROOT lido de CINEX_MARCAS
        for i in range(8):
            D.upsert("marcaum", dict(codigo=f"c{i}", views=5000 if i < 4 else 500, compart=50 if i < 4 else 2, seguiu=5 if i < 4 else 0,
                                    duracao_s=28, tags=dict(formato="testimonial" if i < 4 else "talking_head")))
        r = D.apply("marcaum")
        self.assertEqual(r["status"], "aguardando_aprovacao")
        self.assertEqual(A.prefs("marcaum")["regras"], {})
        self.assertFalse((self.tmp / "marcas" / "marcaum" / "marca.json").read_text(encoding="utf-8").count("formatos_preferidos"))
        A.aprovar(r["proposta"], "dono", "marcaum")
        self.assertIn("testimonial", A.resolver("talking_head", "marcaum")["marca.formatos_preferidos"]["valor"])


if __name__ == "__main__":
    unittest.main()
