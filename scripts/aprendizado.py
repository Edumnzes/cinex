"""Cinex — aprendizado contínuo com autonomia consultiva (guia: references/aprendizado.md).

A Cinex registra, analisa e PROPÕE. Nada oficial muda sem aprovação humana explícita (`aprovar --por`), e toda
mudança aprovada vira versão nova, com a anterior guardada e reversão possível.

Memória em 3 escopos, isolados:
  global  conhecimento/ no repositório (oficial, sem dado de cliente): tecnicas.json, formatos.json, regras.json,
          padrao.json; versões anteriores em conhecimento/historico/.
          ~/cinex-aprendizado/ (local): propostas globais, evidências anônimas, pesquisa, experimentos, config.
  marca   ~/instagram-legendas/<arroba>/aprendizado/: preferencias.json (oficial da marca, versionado),
          correcoes.jsonl, avaliacoes.jsonl, metricas.jsonl, combinacoes.jsonl, propostas/, historico/.
  projeto ~/reels/<projeto>/aprendizado.json: marca, formato(s), instruções, correções, avaliação, métricas.

Precedência (a mais específica vence):
  padrão < regra global < perfil do formato < preferência da marca < preferência da marca para o formato < projeto.

Uso (python scripts/aprendizado.py <comando> ...):
  status [--marca H]                                  visão geral + rotinas atrasadas (pesquisa, revisão)
  regras --formato F [--combina G] [--marca H] [--projeto P] [--json]   regras vigentes e de onde vieram
  sugerir --formato F [--combina G] [--marca H] [--objetivo "..."]       técnicas para usar e para evitar
  tecnica <id> | tecnicas [--area A] [--formato F]
  projeto <P> --marca H --formato F [--combina G] [--objetivo "..."] [--plataforma instagram]
  instrucao <P> <chave> <valor-json> --texto "..."    instrução explícita deste projeto (vence tudo)
  corrigir <P> --tipo T --area A --texto "..." [--tecnica id] [--chave k --valor v-json] [--antes v-json]
           [--texto-geral "..."]   T: erro_tecnico | preferencia_marca | preferencia_formato | decisao_projeto | melhoria_global
  avaliar <P> '<json>'                                notas 0-5 por dimensão + lentes separadas
  objetivo <P> --tipo T [--metrica M] [--meta N] [--tecnicas a,b]   objetivo mensurável do vídeo (antes de publicar)
           T: alcance | compartilhamento | salvamento | engajamento | seguidores | visitas | leads | vendas | retencao
  metricas <P> '<json>'                               desempenho real depois de publicar (Insights)
  resultados --marca H                                o que cumpriu o objetivo e o que não cumpriu (+ resultados.md)
  comparar --marca H [--formato F] [--objetivo O] [--plataforma X]
  padroes [--marca H] [--formato F] [--propor]        hipóteses a partir das correções (rascunhos com --propor)
  pesquisa add '<json>' | pesquisa list [--tipo T]
  referencia add '<json>' | referencia list [--alvo formato:<id>]   referências profissionais (meta: 10 por item)
  experimento criar '<json>' | experimento resultado <id> <variante> <P> '<json>' | experimento avaliar <id>
  propor '<json>' [--rascunho] | enviar <id> | propostas [--status S] [--marca H] | mostrar <id> [--marca H]
  aprovar <id> --por "nome" [--marca H] [--nota "..."] | rejeitar <id> --por "nome" --motivo "..." [--marca H]
  reverter <id> --por "nome" --motivo "..." [--marca H] | historico [--alvo A] [--marca H]
"""
import copy, datetime, hashlib, json, os, re, statistics, sys, uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent
CONH = HERE.parent / "conhecimento"
FILES = {"tecnicas": "tecnicas.json", "formatos": "formatos.json", "regras": "regras.json", "padrao": "padrao.json"}
TIPOS_CORRECAO = ("erro_tecnico", "preferencia_marca", "preferencia_formato", "decisao_projeto", "melhoria_global")
DIMENSOES = ("narrativa", "ritmo", "direcao_visual", "motion_graphics", "audio", "assets")
LENTES = ("qualidade_tecnica", "qualidade_editorial", "aderencia_marca")
METRICAS = ("views", "alcance", "retencao_3s_pct", "tempo_medio_s", "conclusao_pct", "reassistencias", "compart",
            "salvos", "comentarios", "curtidas", "cliques", "conversoes", "seguiu", "visitas")
STATUS = ("rascunho", "aguardando_aprovacao", "aprovada", "rejeitada", "revertida")
CONFIANCA = ("baixa", "media", "alta")
CAMPOS_PROPOSTA = ("titulo", "descricao", "escopo", "alvo", "tipo", "problema", "evidencias", "confianca", "limitacoes",
                   "efeitos_colaterais", "mudancas", "impacto_esperado")
MIN_COMPARAVEIS = 5          # abaixo disso, comparação de métricas é só hipótese
MIN_PADRAO = 3               # ocorrências (em projetos diferentes) para um padrão virar proposta


def local_root(): return Path(os.environ.get("CINEX_APRENDIZADO") or Path.home() / "cinex-aprendizado")
def brands_root(): return Path(os.environ.get("CINEX_MARCAS") or Path.home() / "instagram-legendas")
def projects_root(): return Path(os.environ.get("CINEX_ROOT") or Path.home() / "reels")
def conh_root(): return Path(os.environ.get("CINEX_CONHECIMENTO") or CONH)
def now(): return datetime.datetime.now().isoformat(timespec="seconds")
def today(): return datetime.date.today().isoformat()


def rj(p, default=None):
    p = Path(p)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else copy.deepcopy(default)


def wj(p, data):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp"); tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, p)


def append(p, rec):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f: f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def readl(p):
    p = Path(p)
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()] if p.exists() else []


def handle(h): return h.lstrip("@").strip().lower() if h else None
def brand_dir(h): return brands_root() / handle(h) / "aprendizado"
def project_file(p): return projects_root() / p / "aprendizado.json"
def marca_hash(h): return hashlib.sha256(handle(h).encode()).hexdigest()[:10]     # conta marcas sem expor o nome


def get_dot(d, k, default=None):
    for part in k.split("."):
        if not isinstance(d, dict) or part not in d: return default
        d = d[part]
    return d


def set_dot(d, k, v):
    parts = k.split(".")
    for part in parts[:-1]: d = d.setdefault(part, {})
    if v is _REMOVE: d.pop(parts[-1], None)
    else: d[parts[-1]] = v


_REMOVE = object()


def flat(d, pre=""):
    out = {}
    for k, v in (d or {}).items():
        if isinstance(v, dict) and v and not k.startswith("_"): out.update(flat(v, f"{pre}{k}."))
        elif not k.startswith("_"): out[f"{pre}{k}"] = v
    return out


# --------------------------------------------------------------------------------------------- conhecimento
def conh(name): return rj(conh_root() / FILES[name], {"versao": 1})


def formatos(): return conh("formatos").get("formatos", {})


def formato(fid):
    f = formatos()
    if fid not in f: raise SystemExit(f"formato '{fid}' não existe. Formatos: {', '.join(sorted(f))}")
    return f[fid]


def known_brands():
    """Identificadores de todas as marcas (handle e nome), só para impedir que vazem para o escopo global."""
    out = set(); root = brands_root()
    if root.exists():
        for d in root.iterdir():
            if d.is_dir() and not d.name.startswith((".", "_")):
                out.add(d.name.lower())
                nome = (rj(d / "marca.json", {}) or {}).get("nome")
                if nome and len(nome) > 3: out.add(nome.lower())
    return out


def leaks_brand(text):
    t = (json.dumps(text, ensure_ascii=False) if not isinstance(text, str) else text).lower()
    return sorted(b for b in known_brands() if re.search(r"(?<![\w])@?" + re.escape(b) + r"(?![\w])", t))


# --------------------------------------------------------------------------------------------- marca e projeto
def prefs(h): return rj(brand_dir(h) / "preferencias.json", {"versao": 0, "regras": {}, "formatos": {}})


def projeto_get(p): return rj(project_file(p), None)


def projeto_need(p):
    d = projeto_get(p)
    if not d: raise SystemExit(f"projeto '{p}' sem aprendizado.json: rode  aprendizado.py projeto {p} --marca H --formato F")
    return d


def projeto_init(p, marca, fmt, combina=None, objetivo="", plataforma="instagram"):
    formato(fmt); [formato(c) for c in combina or []]
    d = projeto_get(p) or {"projeto": p, "criado": now(), "instrucoes": {}, "correcoes": [], "avaliacao": None, "metricas": None}
    d.update(marca=handle(marca), formato=fmt, combina=list(combina or []), objetivo=objetivo, plataforma=plataforma)
    wj(project_file(p), d)
    if combina and marca:
        append(brand_dir(marca) / "combinacoes.jsonl", dict(em=now(), projeto=p, formatos=[fmt, *combina], objetivo=objetivo))
    return d


# --------------------------------------------------------------------------------------------- resolvedor
def resolver(fmt, marca=None, projeto=None, combina=None):
    """Regras vigentes, cada uma com a camada de origem. A camada mais específica sobrescreve as anteriores."""
    if projeto:
        pj = projeto_need(projeto); fmt = fmt or pj["formato"]; marca = marca or pj.get("marca")
        combina = combina if combina is not None else pj.get("combina", [])
    layers = []
    pad = conh("padrao"); layers.append((f"padrão v{pad.get('versao', 1)}", flat(pad.get("regras", {}))))
    reg = conh("regras"); layers.append((f"global v{reg.get('versao', 1)}", {k: v["valor"] if isinstance(v, dict) and "valor" in v else v
                                                                          for k, v in flat_rules(reg.get("regras", {})).items()}))
    for fid in [*(combina or [])[::-1], fmt]:                       # o formato principal vence o combinado
        f = formato(fid); params = {f"formato.{k}": v for k, v in f.items() if k not in ("regras", "versao", "nome", "origem", "referencias")}
        layers.append((f"formato {fid} v{f.get('versao', 1)}", {**params, **flat(f.get("regras", {}))}))
    if marca:
        pr = prefs(marca)
        layers.append((f"marca @{handle(marca)} v{pr.get('versao', 0)}", flat_rules(pr.get("regras", {}))))
        layers.append((f"marca @{handle(marca)} / {fmt}", flat_rules(pr.get("formatos", {}).get(fmt, {}))))
    if projeto: layers.append((f"projeto {projeto}", {k: v["valor"] for k, v in pj.get("instrucoes", {}).items()}))
    out = {}
    for name, vals in layers:
        for k, v in vals.items():
            prev = out.get(k)
            out[k] = dict(valor=v, origem=name, sobrescreve=prev["origem"] if prev else None)
    return out


def flat_rules(d):
    """Regras guardadas como {"legenda.borda": {"valor": false, "origem": ...}} ou valores simples."""
    return {k: (v["valor"] if isinstance(v, dict) and "valor" in v else v) for k, v in (d or {}).items()}


# --------------------------------------------------------------------------------------------- técnicas
def sugerir(fmt, marca=None, combina=None, objetivo=""):
    tec = conh("tecnicas").get("tecnicas", {}); r = resolver(fmt, marca, combina=combina)
    val = lambda k: (r.get(k) or {}).get("valor") or []
    usar, evitar = [], []
    for fid in [fmt, *(combina or [])]:                    # combinação: soma as técnicas dos formatos de origem
        usar += formato(fid).get("tecnicas", []); evitar += formato(fid).get("evitar", [])
    if val("formato.tecnicas") != formato(fmt).get("tecnicas", []): usar += val("formato.tecnicas")   # marca/projeto mudou
    usar += val("tecnicas.extra"); evitar += val("tecnicas.evitar")
    evitar = list(dict.fromkeys(evitar)); usar = [t for t in dict.fromkeys(usar) if t not in evitar]
    words = set(re.findall(r"\w{4,}", objetivo.lower()))
    rel = lambda t: sum(1 for w in words if w in json.dumps(tec.get(t, {}), ensure_ascii=False).lower())
    usar.sort(key=lambda t: -rel(t))
    item = lambda t, why: dict(id=t, **{k: tec.get(t, {}).get(k) for k in ("area", "o_que", "suporte", "como_no_cinex", "limitacoes")},
                               quando_evitar=tec.get(t, {}).get("quando_evitar"), motivo=why)
    return dict(formato=fmt, combina=combina or [], marca=handle(marca),
                usar=[item(t, "perfil do formato") for t in usar if t in tec],
                evitar=[item(t, "anti-padrão do formato/marca") for t in evitar if t in tec],
                desconhecidas=[t for t in usar + evitar if t not in tec],
                cinex_nao_faz=[t for t in usar if tec.get(t, {}).get("suporte") == "nao"])


# --------------------------------------------------------------------------------------------- correções e avaliações
def corrigir(p, tipo, area, texto, tecnica=None, chave=None, valor=None, antes=None, texto_geral=None, fonte="usuario"):
    if tipo not in TIPOS_CORRECAO: raise SystemExit(f"tipo inválido: {tipo} ({', '.join(TIPOS_CORRECAO)})")
    pj = projeto_need(p)
    rec = dict(id=uuid.uuid4().hex[:8], em=now(), projeto=p, marca=pj.get("marca"), formato=pj["formato"], tipo=tipo,
               area=area, tecnica=tecnica, chave=chave, valor=valor, antes=antes, texto=texto, fonte=fonte,
               evidencia_de_erro=tipo == "erro_tecnico")   # uma mudança manual, sozinha, não prova que a versão anterior estava errada
    pj["correcoes"].append(rec); wj(project_file(p), pj)
    if pj.get("marca"): append(brand_dir(pj["marca"]) / "correcoes.jsonl", rec)
    aviso = None
    if tipo in ("erro_tecnico", "melhoria_global", "preferencia_formato"):
        geral = texto_geral or texto; vaz = leaks_brand(geral)
        if vaz: aviso = f"não foi para a memória global: o texto cita {', '.join(vaz)}. Reescreva com --texto-geral sem a marca."
        else:
            append(local_root() / "evidencias.jsonl", dict(id=rec["id"], em=rec["em"], formato=rec["formato"], tipo=tipo, area=area,
                                                           tecnica=tecnica, chave=chave, valor=valor, texto=geral,
                                                           marca_hash=marca_hash(pj["marca"]) if pj.get("marca") else None))
    return rec, aviso


def avaliar(p, data):
    pj = projeto_need(p); dims = data.get("dimensoes", {}); lentes = data.get("lentes", {})
    for k, v in {**dims, **lentes}.items():
        nota = v["nota"] if isinstance(v, dict) else v
        if k not in DIMENSOES + LENTES: raise SystemExit(f"dimensão desconhecida: {k} (use {', '.join(DIMENSOES + LENTES)})")
        if not (isinstance(nota, (int, float)) and 0 <= nota <= 5): raise SystemExit(f"{k}: nota 0-5")
    av = dict(em=now(), dimensoes=dims, lentes=lentes, assets=data.get("assets", {}), notas=data.get("notas", ""),
              qa=data.get("qa"), versao_entregue=data.get("versao_entregue"))
    pj["avaliacao"] = av; wj(project_file(p), pj)
    if pj.get("marca"): append(brand_dir(pj["marca"]) / "avaliacoes.jsonl", dict(av, projeto=p, formato=pj["formato"], combina=pj.get("combina", [])))
    return av


def metricas(p, data):
    pj = projeto_need(p); bad = [k for k in data if k not in METRICAS + ("data", "fonte", "codigo", "url", "duracao_s", "turbinado")]
    if bad: raise SystemExit(f"métricas desconhecidas: {bad}")
    m = dict(data, registrado=now()); pj["metricas"] = m; wj(project_file(p), pj)
    if pj.get("marca"):
        append(brand_dir(pj["marca"]) / "metricas.jsonl", dict(m, projeto=p, formato=pj["formato"], combina=pj.get("combina", []),
                                                                objetivo=pj.get("objetivo", ""), plataforma=pj.get("plataforma", "")))
    return m


OBJETIVOS = {  # objetivo -> métrica que diz se cumpriu (quando o dono não define outra)
    "alcance": "views", "compartilhamento": "compart", "salvamento": "salvos", "engajamento": "comentarios",
    "seguidores": "seguiu", "visitas": "visitas", "leads": "cliques", "vendas": "conversoes", "retencao": "retencao_3s_pct"}


def definir_objetivo(p, tipo, metrica=None, meta=None, tecnicas=None):
    """Objetivo mensurável do vídeo: tipo + métrica (+ meta numérica opcional) + técnicas usadas (para comparar depois)."""
    if tipo not in OBJETIVOS: raise SystemExit(f"objetivo: {', '.join(OBJETIVOS)}")
    metrica = metrica or OBJETIVOS[tipo]
    if metrica not in METRICAS: raise SystemExit(f"métrica desconhecida: {metrica}")
    pj = projeto_need(p)
    pj["meta"] = dict(tipo=tipo, metrica=metrica, valor=meta, definido=now())
    if tecnicas: pj["tecnicas"] = list(tecnicas)
    wj(project_file(p), pj); return pj["meta"]


def resultados(marca, min_base=3):
    """O que cumpriu o objetivo e o que não cumpriu, por vídeo publicado da marca. Sem meta numérica, o vídeo é comparado
    com a mediana dos outros vídeos da marca no MESMO formato (precisa de min_base vídeos; senão 'sem base').
    Depois mostra o que os que cumpriram têm em comum (formato, técnicas, notas) — como pista, não como causa."""
    root = projects_root(); rows = []
    for f in sorted(root.glob("*/aprendizado.json")) if root.exists() else []:
        pj = rj(f)
        if pj.get("marca") != handle(marca) or not pj.get("metricas"): continue
        rows.append(pj)
    out = []
    for pj in rows:
        meta = pj.get("meta") or {}; k = meta.get("metrica") or OBJETIVOS.get(pj.get("objetivo", ""), "views")
        v = pj["metricas"].get(k)
        pares = [o["metricas"].get(k) for o in rows if o is not pj and o["formato"] == pj["formato"]
                 and isinstance(o["metricas"].get(k), (int, float)) and not o["metricas"].get("turbinado")]
        alvo, base = meta.get("valor"), "meta definida"
        if alvo is None and len(pares) >= min_base: alvo, base = statistics.median(pares), f"mediana de {len(pares)} vídeos do formato"
        if not isinstance(v, (int, float)): veredito = "sem dado"
        elif alvo is None: veredito = "sem base"
        else: veredito = "cumpriu" if v >= alvo else "não cumpriu"
        out.append(dict(projeto=pj["projeto"], formato=pj["formato"], combina=pj.get("combina", []),
                        objetivo=meta.get("tipo") or pj.get("objetivo") or "?", metrica=k, valor=v, alvo=alvo, base=base,
                        veredito=veredito, turbinado=bool(pj["metricas"].get("turbinado")),
                        tecnicas=pj.get("tecnicas", []), lentes=(pj.get("avaliacao") or {}).get("lentes", {})))
    sim = [r for r in out if r["veredito"] == "cumpriu"]; nao = [r for r in out if r["veredito"] == "não cumpriu"]
    def freq(rs, key):
        c = {}
        for r in rs:
            for x in (r[key] if isinstance(r[key], list) else [r[key]]): c[x] = c.get(x, 0) + 1
        return c
    pistas = []
    for key in ("formato", "tecnicas"):
        a, b = freq(sim, key), freq(nao, key)
        for x in set(a) | set(b):
            pa = a.get(x, 0) / len(sim) if sim else 0; pb = b.get(x, 0) / len(nao) if nao else 0
            if abs(pa - pb) >= .3 and a.get(x, 0) + b.get(x, 0) >= 2:
                pistas.append(dict(o_que=f"{key}: {x}", nos_que_cumpriram=f"{a.get(x, 0)}/{len(sim)}", nos_que_nao=f"{b.get(x, 0)}/{len(nao)}",
                                   leitura="aparece mais nos que cumpriram" if pa > pb else "aparece mais nos que não cumpriram"))
    aviso = ("Poucos vídeos: leia como pista, não como regra." if len(out) < MIN_COMPARAVEIS else
             "Correlação, não causa: tema, horário e música também mudam o resultado.")
    rep = dict(marca=handle(marca), videos=len(out), cumpriu=len(sim), nao_cumpriu=len(nao),
               sem_base=sum(r["veredito"] in ("sem base", "sem dado") for r in out), por_video=out, pistas=pistas, aviso=aviso)
    md = [f"# Resultados — @{handle(marca)} ({today()})", "", f"{len(sim)} cumpriram, {len(nao)} não cumpriram, "
          f"{rep['sem_base']} sem base. {aviso}", "", "| vídeo | formato | objetivo | métrica | valor | alvo | resultado |", "|---|---|---|---|---|---|---|"]
    md += [f"| {r['projeto']} | {r['formato']} | {r['objetivo']} | {r['metrica']} | {r['valor']} | "
           f"{'' if r['alvo'] is None else round(r['alvo'], 1)} ({r['base']}) | {r['veredito']}{' (turbinado)' if r['turbinado'] else ''} |" for r in out]
    if pistas: md += ["", "## Pistas", *[f"- {p['o_que']}: {p['leitura']} ({p['nos_que_cumpriram']} × {p['nos_que_nao']})" for p in pistas]]
    (brand_dir(marca)).mkdir(parents=True, exist_ok=True); (brand_dir(marca) / "resultados.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return rep


def comparar(marca, fmt=None, objetivo=None, plataforma=None):
    """Só compara o que é comparável: mesma marca, mesmo formato, plataforma e objetivo. Poucos casos = hipótese."""
    rows = [r for r in readl(brand_dir(marca) / "metricas.jsonl") if not r.get("turbinado")
            and (not fmt or r["formato"] == fmt) and (not objetivo or r.get("objetivo") == objetivo)
            and (not plataforma or r.get("plataforma") == plataforma)]
    latest = {r["projeto"]: r for r in rows}; rows = list(latest.values())
    med = {k: statistics.median([r[k] for r in rows if isinstance(r.get(k), (int, float))])
           for k in METRICAS if sum(isinstance(r.get(k), (int, float)) for r in rows) >= 1}
    return dict(n=len(rows), filtros=dict(formato=fmt, objetivo=objetivo, plataforma=plataforma), medianas=med,
                conclusao="hipótese apenas: menos de %d vídeos comparáveis" % MIN_COMPARAVEIS if len(rows) < MIN_COMPARAVEIS
                else "amostra mínima atingida; ainda assim, correlação não é causa", projetos=[r["projeto"] for r in rows])


def padroes(marca=None, fmt=None, propor_=False):
    """Agrupa correções repetidas em hipóteses. Marca: só as dela. Global: evidências anônimas, exige 2+ marcas."""
    if marca:
        src = [r for r in readl(brand_dir(marca) / "correcoes.jsonl") if r["tipo"] in ("preferencia_marca", "preferencia_formato")]
    else: src = readl(local_root() / "evidencias.jsonl")
    src = [r for r in src if not fmt or r["formato"] == fmt]
    groups = {}
    for r in src:
        key = (r["tipo"], r.get("formato") if r["tipo"] == "preferencia_formato" else None, r["area"], r.get("chave"),
               json.dumps(r.get("valor"), ensure_ascii=False))
        g = groups.setdefault(key, dict(tipo=r["tipo"], formato=key[1], area=r["area"], chave=r.get("chave"), valor=r.get("valor"),
                                        casos=[], marcas=set(), exemplos=[]))
        g["casos"].append(r.get("projeto") or r["id"]); g["marcas"].add(r.get("marca_hash") or r.get("marca"))
        if len(g["exemplos"]) < 3: g["exemplos"].append(r["texto"])
    out, criadas = [], []
    for g in groups.values():
        n = len(set(g["casos"])); nm = len(g["marcas"] - {None})
        conf = "alta" if n >= 6 else "media" if n >= MIN_PADRAO else "baixa"
        generalizavel = bool(marca) or nm >= 2
        item = dict(g, marcas=nm, n=n, confianca=conf, generalizavel=generalizavel)
        item.pop("casos")
        out.append(item)
        if propor_ and g["chave"] and n >= MIN_PADRAO and generalizavel:
            alvo = (f"marca:{handle(marca)}" + (f"/formato:{g['formato']}" if g["formato"] else "")) if marca else \
                   (f"formato:{g['formato']}" if g["formato"] else "global")
            criadas.append(propor(dict(
                titulo=f"{g['area']}: {g['chave']} = {g['valor']}", descricao=f"Padrão visto em {n} correções.",
                escopo="marca" if marca else ("formato" if g["formato"] else "global"), alvo=alvo, marca=handle(marca),
                formato=g["formato"], tipo="regra", problema="A mesma correção se repete nas edições.",
                evidencias=g["exemplos"], amostra=f"{n} projetos" + ("" if marca else f", {nm} marcas"),
                comparabilidade="correções classificadas do mesmo tipo e área", confianca=conf,
                limitacoes="Correções manuais mostram preferência, não provam erro; não há métrica de desempenho ligada.",
                efeitos_colaterais="Pode não servir a vídeos com outro objetivo.",
                mudancas=[dict(chave=g["chave"], para=g["valor"])], impacto_esperado="Menos correções repetidas."), rascunho=True)["id"])
    out.sort(key=lambda g: -g["n"])
    return dict(padroes=out, propostas_criadas=criadas)


# --------------------------------------------------------------------------------------------- pesquisa e experimentos
def pesquisa_add(data):
    req = ("fonte", "tecnica", "formatos", "tipo", "custo", "adequacao", "comparacao_padrao")
    miss = [k for k in req if not data.get(k)]
    if miss: raise SystemExit(f"faltam campos: {miss}")
    if data["tipo"] not in ("tendencia", "tecnica_consistente", "indefinido"): raise SystemExit("tipo: tendencia | tecnica_consistente | indefinido")
    rec = dict(data, id=uuid.uuid4().hex[:8], data_consulta=data.get("data_consulta") or today(), status="achado")
    append(local_root() / "pesquisa.jsonl", rec); return rec


REF_CAMPOS = ("url", "autor", "plataforma", "alvos", "insight", "tipo")
REF_TIPOS = ("criador", "estudo", "documentacao", "curso", "caso_real")
META_REFS = 10                      # referências desejadas por formato e por técnica


def referencia_add(data):
    """Uma referência profissional para um formato ou técnica (pesquisa, não regra). Só entra depois de aberta e conferida:
    url, autor, plataforma, alvos ["formato:<id>" | "tecnica:<id>" | "geral:instagram|retencao|metricas"], insight (com as nossas palavras, sem copiar o texto
    do autor), tipo (criador | estudo | documentacao | curso | caso_real). Vira oficial só por proposta aprovada."""
    miss = [k for k in REF_CAMPOS if not data.get(k)]
    if miss: raise SystemExit(f"faltam campos: {miss}")
    if data["tipo"] not in REF_TIPOS: raise SystemExit(f"tipo: {', '.join(REF_TIPOS)}")
    if not str(data["url"]).startswith("https://"): raise SystemExit("url precisa começar com https://")
    if len(data["insight"]) > 400: raise SystemExit("insight longo demais: resuma com as suas palavras (até 400 caracteres)")
    for a in data["alvos"]:
        kind, _, i = a.partition(":")
        if kind == "formato": formato(i)
        elif kind == "tecnica":
            if i not in conh("tecnicas")["tecnicas"]: raise SystemExit(f"técnica desconhecida: {i}")
        elif kind == "geral":                         # plataforma e distribuição: vale para todos, não conta por item
            if i not in ("instagram", "retencao", "metricas"): raise SystemExit("geral: instagram | retencao | metricas")
        else: raise SystemExit(f"alvo inválido: {a}")
    p = local_root() / "referencias.jsonl"
    if any(r["url"] == data["url"] for r in readl(p)): raise SystemExit("essa url já está registrada")
    rec = dict(data, id=uuid.uuid4().hex[:8], data_consulta=data.get("data_consulta") or today(), conferida=True)
    append(p, rec); return rec


def referencias(alvo=None):
    rows = readl(local_root() / "referencias.jsonl")
    if alvo: return [r for r in rows if alvo in r["alvos"]]
    alvos = [f"formato:{k}" for k in formatos()] + [f"tecnica:{k}" for k in conh("tecnicas")["tecnicas"]]
    cont = {a: sum(a in r["alvos"] for r in rows) for a in alvos}
    return dict(total=len(rows), meta_por_item=META_REFS, completos=sum(v >= META_REFS for v in cont.values()), itens=len(alvos),
                faltando={a: META_REFS - v for a, v in cont.items() if v < META_REFS})


def exp_path(eid, marca=None): return (brand_dir(marca) if marca else local_root()) / "experimentos" / f"{eid}.json"


def exp_find(eid):
    p = local_root() / "experimentos" / f"{eid}.json"
    if p.exists(): return p
    for d in brands_root().glob(f"*/aprendizado/experimentos/{eid}.json"): return d
    raise SystemExit(f"experimento {eid} não encontrado")


def experimento_criar(data):
    req = ("hipotese", "formato", "variantes", "constantes", "metrica_principal")
    miss = [k for k in req if not data.get(k)]
    if miss: raise SystemExit(f"faltam campos: {miss}")
    if len(data["variantes"]) < 2: raise SystemExit("um experimento precisa de 2+ variantes")
    formato(data["formato"])
    eid = "E-" + datetime.datetime.now().strftime("%Y%m%d") + "-" + uuid.uuid4().hex[:4]
    e = dict(data, id=eid, criado=now(), status="ativo", resultados=[], minimo_por_variante=data.get("minimo_por_variante", 3),
             marca=handle(data.get("marca")))
    wj(exp_path(eid, e["marca"]), e); return e


def experimento_resultado(eid, variante, projeto, data):
    p = exp_find(eid); e = rj(p)
    if variante not in e["variantes"]: raise SystemExit(f"variante desconhecida: {variante}")
    e["resultados"].append(dict(variante=variante, projeto=projeto, metricas=data, em=now())); wj(p, e); return e


def experimento_avaliar(eid):
    p = exp_find(eid); e = rj(p); k = e["metrica_principal"]; por = {}
    for r in e["resultados"]:
        if isinstance(r["metricas"].get(k), (int, float)): por.setdefault(r["variante"], []).append(r["metricas"][k])
    res = {v: dict(n=len(por.get(v, [])), mediana=statistics.median(por[v]) if por.get(v) else None) for v in e["variantes"]}
    ok = all(r["n"] >= e["minimo_por_variante"] for r in res.values())
    meds = sorted((r["mediana"], v) for v, r in res.items() if r["mediana"] is not None)
    diff = (meds[-1][0] - meds[0][0]) / meds[0][0] if ok and len(meds) >= 2 and meds[0][0] else 0
    if not ok: concl = f"inconclusivo: falta amostra (mínimo {e['minimo_por_variante']} por variante)"
    elif diff < .2: concl = "inconclusivo: diferença menor que 20%"
    else: concl = f"sinal a favor de '{meds[-1][1]}' (+{diff:.0%} em {k}); continua hipótese até virar proposta aprovada"
    e.update(avaliacao=dict(em=now(), por_variante=res, conclusao=concl), status="concluido" if ok else e["status"]); wj(p, e)
    return e


# --------------------------------------------------------------------------------------------- central de melhorias
def prop_dir(marca=None): return (brand_dir(marca) if marca else local_root()) / "propostas"


def prop_path(pid, marca=None):
    p = prop_dir(marca) / f"{pid}.json"
    if not p.exists(): raise SystemExit(f"proposta {pid} não encontrada" + ("" if marca else " (proposta de marca? passe --marca)"))
    return p


def parse_alvo(alvo):
    """global | padrao | formato:<id> | tecnica:<id> | combinacao:<id> | marca:<h> | marca:<h>/formato:<id> | projeto:<p>"""
    if alvo in ("global", "padrao"): return dict(kind=alvo)
    m = re.fullmatch(r"marca:@?([\w.]+)(?:/formato:(\w+))?", alvo)
    if m: return dict(kind="marca", marca=handle(m[1]), formato=m[2])
    m = re.fullmatch(r"(formato|tecnica|combinacao|projeto):([\w.+-]+)", alvo)
    if m: return dict(kind=m[1], id=m[2])
    raise SystemExit(f"alvo inválido: {alvo}")


def target_doc(alvo):
    """-> (arquivo, documento, nó a alterar, pasta de histórico)."""
    a = parse_alvo(alvo)
    if a["kind"] in ("global", "padrao"):
        path = conh_root() / FILES["regras" if a["kind"] == "global" else "padrao"]; doc = rj(path, {"versao": 0, "regras": {}})
        return path, doc, doc.setdefault("regras", {}), conh_root() / "historico"
    if a["kind"] in ("formato", "tecnica", "combinacao"):
        name = "tecnicas" if a["kind"] == "tecnica" else "formatos"; path = conh_root() / FILES[name]; doc = rj(path, {"versao": 0})
        key = {"formato": "formatos", "tecnica": "tecnicas", "combinacao": "combinacoes"}[a["kind"]]
        coll = doc.setdefault(key, {})
        if a["kind"] == "formato" and a["id"] not in coll: raise SystemExit(f"formato '{a['id']}' não existe (aprovação não cria formato novo)")
        return path, doc, coll.setdefault(a["id"], {}), conh_root() / "historico"
    if a["kind"] == "marca":
        path = brand_dir(a["marca"]) / "preferencias.json"; doc = rj(path, {"versao": 0, "regras": {}, "formatos": {}})
        if a["formato"]: formato(a["formato"])
        node = doc.setdefault("formatos", {}).setdefault(a["formato"], {}) if a["formato"] else doc.setdefault("regras", {})
        return path, doc, node, brand_dir(a["marca"]) / "historico"
    path = project_file(a["id"]); doc = projeto_need(a["id"])
    return path, doc, doc.setdefault("instrucoes", {}), None


def rules_style(alvo):
    """Regras globais/marca/projeto guardam a chave inteira ("legenda.borda") com valor+origem; perfis usam caminho."""
    return parse_alvo(alvo)["kind"] in ("global", "padrao", "marca", "projeto")


def propor(data, rascunho=False):
    miss = [k for k in CAMPOS_PROPOSTA if data.get(k) in (None, "", [])]
    if miss: raise SystemExit(f"proposta incompleta, faltam: {miss}")
    if data["confianca"] not in CONFIANCA: raise SystemExit(f"confianca: {CONFIANCA}")
    for m in data["mudancas"]:
        if "chave" not in m or not ("para" in m or m.get("remover")): raise SystemExit("cada mudança precisa de 'chave' e 'para' (ou 'remover': true)")
    a = parse_alvo(data["alvo"]); marca = a.get("marca")
    if a["kind"] in ("global", "padrao", "formato", "tecnica", "combinacao"):
        vaz = leaks_brand({k: data.get(k) for k in ("titulo", "descricao", "problema", "evidencias", "mudancas", "amostra")})
        if vaz: raise SystemExit(f"proposta global não pode citar marca ({', '.join(vaz)}): descreva o padrão de forma geral")
    target_doc(data["alvo"])                                                     # valida o alvo antes de guardar
    pid = "P-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:4]
    pr = dict(data, id=pid, marca=marca, criada=now(), status="rascunho" if rascunho else "aguardando_aprovacao",
              requer_aprovacao=True, decisao=None, versao_anterior=None, versao_nova=None, aplicado=None)
    wj(prop_dir(marca) / f"{pid}.json", pr); return pr


def enviar(pid, marca=None):
    p = prop_path(pid, marca); pr = rj(p)
    if pr["status"] != "rascunho": raise SystemExit(f"só rascunho pode ser enviado (status: {pr['status']})")
    pr["status"] = "aguardando_aprovacao"; wj(p, pr); return pr


def _snapshot(path, doc, hist):
    if hist and path.exists():
        wj(hist / f"{path.stem}.v{doc.get('versao', 0)}.json", doc)


def aprovar(pid, por, marca=None, nota=""):
    if not por: raise SystemExit("aprovação precisa de --por (quem aprovou)")
    p = prop_path(pid, marca); pr = rj(p)
    if pr["status"] != "aguardando_aprovacao": raise SystemExit(f"status {pr['status']}: só 'aguardando_aprovacao' pode ser aprovada")
    path, doc, node, hist = target_doc(pr["alvo"]); _snapshot(path, doc, hist)
    antes, style = [], rules_style(pr["alvo"])
    for m in pr["mudancas"]:
        k = m["chave"]
        if style:
            antes.append(dict(chave=k, existia=k in node, valor=copy.deepcopy(node.get(k))))
            if m.get("remover"): node.pop(k, None)
            else: node[k] = dict(valor=m["para"], origem=f"proposta {pid}", aprovado_por=por, desde=today())
        else:
            cur = get_dot(node, k, _REMOVE)
            antes.append(dict(chave=k, existia=cur is not _REMOVE, valor=None if cur is _REMOVE else copy.deepcopy(cur)))
            set_dot(node, k, _REMOVE if m.get("remover") else m["para"])
    old = doc.get("versao", 0); doc["versao"] = old + 1
    if parse_alvo(pr["alvo"])["kind"] in ("formato", "tecnica"): node["versao"] = node.get("versao", 0) + 1
    wj(path, doc)
    pr.update(status="aprovada", decisao=dict(por=por, em=now(), nota=nota), versao_anterior=old, versao_nova=doc["versao"],
              aplicado=dict(arquivo=str(path), antes=antes))
    wj(p, pr); _log(pr, "aprovada", por, nota); return pr


def rejeitar(pid, por, motivo, marca=None):
    if not (por and motivo): raise SystemExit("rejeição precisa de --por e --motivo")
    p = prop_path(pid, marca); pr = rj(p)
    if pr["status"] not in ("rascunho", "aguardando_aprovacao"): raise SystemExit(f"status {pr['status']} não pode ser rejeitada")
    pr.update(status="rejeitada", decisao=dict(por=por, em=now(), motivo=motivo)); wj(p, pr); _log(pr, "rejeitada", por, motivo)
    return pr      # rejeição fica no histórico; não vira regra contrária automaticamente


def reverter(pid, por, motivo, marca=None):
    if not (por and motivo): raise SystemExit("reversão precisa de --por e --motivo")
    p = prop_path(pid, marca); pr = rj(p)
    if pr["status"] != "aprovada": raise SystemExit(f"só proposta aprovada pode ser revertida (status: {pr['status']})")
    path, doc, node, hist = target_doc(pr["alvo"]); _snapshot(path, doc, hist); style = rules_style(pr["alvo"])
    for a in pr["aplicado"]["antes"]:                              # devolve só as chaves desta proposta, como versão nova
        if style:
            if a["existia"]: node[a["chave"]] = a["valor"]
            else: node.pop(a["chave"], None)
        else: set_dot(node, a["chave"], a["valor"] if a["existia"] else _REMOVE)
    doc["versao"] = doc.get("versao", 0) + 1
    if parse_alvo(pr["alvo"])["kind"] in ("formato", "tecnica"): node["versao"] = node.get("versao", 0) + 1
    wj(path, doc)
    pr.update(status="revertida", reversao=dict(por=por, em=now(), motivo=motivo, versao=doc["versao"])); wj(p, pr)
    _log(pr, "revertida", por, motivo); return pr


def _log(pr, acao, por, nota):
    append((brand_dir(pr["marca"]) if pr.get("marca") else local_root()) / "decisoes_propostas.jsonl",
           dict(em=now(), proposta=pr["id"], alvo=pr["alvo"], acao=acao, por=por, nota=nota))


def propostas(status=None, marca=None):
    rows = [rj(p) for p in sorted(prop_dir(marca).glob("*.json"))] if prop_dir(marca).exists() else []
    return [dict(id=r["id"], status=r["status"], alvo=r["alvo"], titulo=r["titulo"], confianca=r["confianca"], criada=r["criada"])
            for r in rows if not status or r["status"] == status]


def historico(alvo=None, marca=None):
    rows = readl((brand_dir(marca) if marca else local_root()) / "decisoes_propostas.jsonl")
    return [r for r in rows if not alvo or r["alvo"] == alvo]


# --------------------------------------------------------------------------------------------- status e rotinas
def config(): return rj(local_root() / "config.json", {"pesquisa_dias": 30, "revisao_dias": 7, "ultima_pesquisa": None, "ultima_revisao": None})


def status(marca=None):
    c = config(); hoje = datetime.date.today()
    late = lambda key, dias: c.get(key) is None or (hoje - datetime.date.fromisoformat(c[key])).days >= dias
    out = dict(conhecimento={k: conh(k).get("versao") for k in FILES}, formatos=sorted(formatos()),
               propostas_globais=len(propostas("aguardando_aprovacao")), pesquisa=len(readl(local_root() / "pesquisa.jsonl")),
               evidencias_globais=len(readl(local_root() / "evidencias.jsonl")),
               rotinas=dict(pesquisa_de_tendencias=("atrasada" if late("ultima_pesquisa", c["pesquisa_dias"]) else "em dia") + f" (a cada {c['pesquisa_dias']} dias)",
                            revisao_do_aprendizado=("atrasada" if late("ultima_revisao", c["revisao_dias"]) else "em dia") + f" (a cada {c['revisao_dias']} dias)"))
    if marca:
        pr = prefs(marca)
        out["marca"] = dict(handle=handle(marca), versao_preferencias=pr.get("versao"), regras=len(pr.get("regras", {})),
                            formatos_com_preferencia=sorted(k for k, v in pr.get("formatos", {}).items() if v),
                            correcoes=len(readl(brand_dir(marca) / "correcoes.jsonl")),
                            avaliacoes=len(readl(brand_dir(marca) / "avaliacoes.jsonl")),
                            metricas=len(readl(brand_dir(marca) / "metricas.jsonl")),
                            propostas_aguardando=len(propostas("aguardando_aprovacao", marca)))
    return out


def marcar_rotina(qual):
    c = config(); c[{"pesquisa": "ultima_pesquisa", "revisao": "ultima_revisao"}[qual]] = today(); wj(local_root() / "config.json", c)


# --------------------------------------------------------------------------------------------- CLI
def _opt(args, name, default=None):
    if name in args:
        i = args.index(name)
        if i + 1 < len(args): return args[i + 1]
    return default


def _multi(args, name): return [args[i + 1] for i, a in enumerate(args) if a == name and i + 1 < len(args)]


def _pos(args):
    out, skip = [], False
    for a in args:
        if skip: skip = False; continue
        if a.startswith("--"): skip = a not in ("--json", "--propor", "--rascunho"); continue
        out.append(a)
    return out


def _show(x): print(json.dumps(x, ensure_ascii=False, indent=1, default=list))


def _regras_txt(r):
    for k in sorted(r):
        v = r[k]; extra = f"  (sobrescreve {v['sobrescreve']})" if v["sobrescreve"] else ""
        print(f"{k:32} = {json.dumps(v['valor'], ensure_ascii=False)[:70]:72} ← {v['origem']}{extra}")


def main(argv):
    if not argv or argv[0] in ("-h", "--help", "help"): print(__doc__); return
    cmd, args = argv[0], argv[1:]; pos = _pos(args); mk = _opt(args, "--marca")
    J = lambda s: json.loads(s) if s is not None else None
    if cmd == "status": _show(status(mk))
    elif cmd == "rotina": marcar_rotina(pos[0]); print("ok")
    elif cmd == "regras":
        r = resolver(_opt(args, "--formato"), mk, _opt(args, "--projeto"), _multi(args, "--combina") or None)
        _show(r) if "--json" in args else _regras_txt(r)
    elif cmd == "sugerir": _show(sugerir(_opt(args, "--formato"), mk, _multi(args, "--combina"), _opt(args, "--objetivo", "")))
    elif cmd == "tecnica": _show(conh("tecnicas")["tecnicas"].get(pos[0]) or f"técnica '{pos[0]}' não existe")
    elif cmd == "tecnicas":
        t = conh("tecnicas")["tecnicas"]; a = _opt(args, "--area"); f = _opt(args, "--formato")
        keep = set(formato(f).get("tecnicas", []) + formato(f).get("evitar", [])) if f else None
        for k, v in sorted(t.items(), key=lambda kv: (kv[1]["area"], kv[0])):
            if (not a or v["area"] == a) and (keep is None or k in keep):
                print(f"{v['area']:22} {k:38} {v['tipo']:11} suporte={v['suporte']:8} {v['o_que'][:70]}")
    elif cmd == "projeto":
        _show(projeto_init(pos[0], mk, _opt(args, "--formato"), _multi(args, "--combina"), _opt(args, "--objetivo", ""),
                           _opt(args, "--plataforma", "instagram")))
    elif cmd == "instrucao":
        p, k, v = pos[0], pos[1], J(pos[2]); pj = projeto_need(p)
        pj["instrucoes"][k] = dict(valor=v, texto=_opt(args, "--texto", ""), em=now()); wj(project_file(p), pj); print("ok")
    elif cmd == "corrigir":
        rec, aviso = corrigir(pos[0], _opt(args, "--tipo"), _opt(args, "--area"), _opt(args, "--texto"), _opt(args, "--tecnica"),
                              _opt(args, "--chave"), J(_opt(args, "--valor")), J(_opt(args, "--antes")), _opt(args, "--texto-geral"))
        _show(rec); aviso and print("AVISO:", aviso)
    elif cmd == "avaliar": _show(avaliar(pos[0], J(pos[1])))
    elif cmd == "metricas": _show(metricas(pos[0], J(pos[1])))
    elif cmd == "objetivo":
        s = _opt(args, "--meta"); t = _opt(args, "--tecnicas")
        _show(definir_objetivo(pos[0], _opt(args, "--tipo"), _opt(args, "--metrica"), float(s) if s else None,
                               [x.strip() for x in t.split(",")] if t else None))
    elif cmd == "resultados": _show(resultados(mk))
    elif cmd == "comparar": _show(comparar(mk, _opt(args, "--formato"), _opt(args, "--objetivo"), _opt(args, "--plataforma")))
    elif cmd == "padroes": _show(padroes(mk, _opt(args, "--formato"), "--propor" in args))
    elif cmd == "pesquisa":
        if pos[0] == "add": _show(pesquisa_add(J(pos[1])))
        else:
            t = _opt(args, "--tipo"); _show([r for r in readl(local_root() / "pesquisa.jsonl") if not t or r["tipo"] == t])
    elif cmd == "referencia":
        if pos[0] == "add": _show(referencia_add(J(pos[1])))
        else: _show(referencias(_opt(args, "--alvo")))
    elif cmd == "experimento":
        sub = pos[0]
        if sub == "criar": _show(experimento_criar(J(pos[1])))
        elif sub == "resultado": _show(experimento_resultado(pos[1], pos[2], pos[3], J(pos[4])))
        elif sub == "avaliar": _show(experimento_avaliar(pos[1])["avaliacao"])
    elif cmd == "propor": _show(propor(J(pos[0]), "--rascunho" in args))
    elif cmd == "enviar": _show(enviar(pos[0], mk))
    elif cmd == "propostas": _show(propostas(_opt(args, "--status"), mk))
    elif cmd == "mostrar": _show(rj(prop_path(pos[0], mk)))
    elif cmd == "aprovar": _show(aprovar(pos[0], _opt(args, "--por"), mk, _opt(args, "--nota", "")))
    elif cmd == "rejeitar": _show(rejeitar(pos[0], _opt(args, "--por"), _opt(args, "--motivo"), mk))
    elif cmd == "reverter": _show(reverter(pos[0], _opt(args, "--por"), _opt(args, "--motivo"), mk))
    elif cmd == "historico": _show(historico(_opt(args, "--alvo"), mk))
    else: print(__doc__)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main(sys.argv[1:])
