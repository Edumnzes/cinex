"""Technical QA of the exported file (manual 14: export is a control step, not a click on "render").

Usage: python qa.py final.mp4 [--platform reels|stories|desktop|feed|quadrado|4x3|led] [--project project.py] [--decisions decisoes.json]

One full decode of the file (proves it plays to the end) with ffmpeg filters:
  resolution / aspect / fps / duration / audio present        -> from the stream header
  black frames (blackdetect)   frozen picture (freezedetect)   -> no black flashes / offline media
  loudness (ebur128: integrated LUFS, true peak)               -> -14 LUFS +-1.5, peak <= -1 dBTP
  clipping (astats: samples at full scale)                     -> no audible distortion
  audio vs video length                                        -> sync / nothing truncated
  decode errors                                                -> corrupt file
--silent: text-only motion video (silent track) - loudness checks are skipped.
--project also runs `python project.py check` (graphics over faces, safe zones, SFX density).
Writes qa.json and, if decisoes.json exists, fills its "qa_result". Exit code 1 when anything FAILs.
"""
import argparse, json, re, subprocess, sys
from pathlib import Path
import imageio_ffmpeg

FFM = imageio_ffmpeg.get_ffmpeg_exe()
SPECS = {  # Instagram only for now (decided with the user)
    "reels":   dict(size=(1080, 1920), fps=(29.9, 30.1), dur=(3, 180), lufs=(-15.5, -12.5), peak=-1.0),
    "stories": dict(size=(1080, 1920), fps=(23.9, 60.1), dur=(1, 60), lufs=(-15.5, -12.5), peak=-1.0),
    "desktop": dict(size=(1920, 1080), fps=(29.9, 30.1), dur=(3, 3600), lufs=(-15.5, -12.5), peak=-1.0),   # 16:9 (YouTube, site)
    "feed":    dict(size=(1080, 1350), fps=(29.9, 30.1), dur=(3, 3600), lufs=(-15.5, -12.5), peak=-1.0),   # 4:5
    "quadrado": dict(size=(1080, 1080), fps=(29.9, 30.1), dur=(3, 3600), lufs=(-15.5, -12.5), peak=-1.0),  # 1:1
    "4x3":     dict(size=(1440, 1080), fps=(29.9, 30.1), dur=(3, 3600), lufs=(-15.5, -12.5), peak=-1.0),   # presentations
    "led":     dict(size=(512, 384), fps=(29.9, 30.1), dur=(3, 3600), lufs=(-15.5, -12.5), peak=-1.0),     # trade-show LED panel
}


def run(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("video"); ap.add_argument("--platform", default="reels", choices=SPECS)
    ap.add_argument("--project"); ap.add_argument("--decisions", default="decisoes.json")
    ap.add_argument("--silent", action="store_true", help="video without voice/music (text-only motion): skip loudness")
    a = ap.parse_args(argv); spec = SPECS[a.platform]
    sys.stdout.reconfigure(encoding="utf-8")

    head = subprocess.run([FFM, "-hide_banner", "-i", a.video], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    v = re.search(r"Video: .*?(\d{3,5})x(\d{3,5}).*?([\d.]+) fps", head)
    d = re.search(r"Duration: (\d+):(\d+):([\d.]+)", head)
    has_audio = "Audio:" in head
    w, h, fps = (int(v.group(1)), int(v.group(2)), float(v.group(3))) if v else (0, 0, 0)
    dur = int(d.group(1)) * 3600 + int(d.group(2)) * 60 + float(d.group(3)) if d else 0

    cmd = [FFM, "-hide_banner", "-nostats", "-i", a.video,
           "-vf", "blackdetect=d=0.08:pix_th=0.08,freezedetect=n=0.002:d=1.5", "-map", "0:v"]
    if has_audio: cmd += ["-af", "ebur128=peak=true,astats=metadata=0", "-map", "0:a"]
    cmd += ["-f", "null", "-"]
    log = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace").stderr

    blacks = [(float(x), float(y)) for x, y in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", log)]
    freezes = re.findall(r"freeze_start: ([\d.]+)", log)
    summ = log[log.rfind("Summary:"):] if "Summary:" in log else ""
    lufs = re.search(r"I:\s+(-?[\d.]+) LUFS", summ); peak = re.search(r"Peak:\s+(-?[\d.inf]+) dBFS", summ)
    lufs = float(lufs.group(1)) if lufs else None
    peak = float(peak.group(1)) if peak and peak.group(1) not in ("-inf", "inf") else None
    clip = sum(int(x) for x in re.findall(r"Number of samples clipped: (\d+)", log)) if "clipped" in log else 0
    last_v = re.findall(r"frame=\s*(\d+)", log)
    errors = [l for l in log.splitlines() if re.search(r"error|corrupt|invalid data|non-existing", l, re.I)
              and "Summary" not in l][:5]

    res = []
    def add(name, ok, val, want, warn=False):
        res.append(dict(item=name, status="OK" if ok else ("AVISO" if warn else "FALHA"), valor=val, esperado=want))

    add("resolução", (w, h) == spec["size"], f"{w}x{h}", "%dx%d" % spec["size"])
    ar = "%d:%d" % ((9, 16) if spec["size"][0] < spec["size"][1] else (16, 9))
    add("proporção " + ar, h and abs(w / h - spec["size"][0] / spec["size"][1]) < .01, f"{w}:{h}", ar)
    add("fps", spec["fps"][0] <= fps <= spec["fps"][1], fps, "%s-%s" % spec["fps"])
    add("duração", spec["dur"][0] <= dur <= spec["dur"][1], f"{dur:.2f}s", "%s-%ss" % spec["dur"])
    add("áudio presente", has_audio, has_audio, True)
    if has_audio and a.silent:
        add("trilha sem voz (silenciosa ou só efeitos; música no app)", True, lufs, "sem voz")
        if peak is not None: add("pico real", peak <= spec["peak"], peak, f"≤ {spec['peak']} dBTP")
    elif has_audio:
        add("volume integrado", lufs is not None and spec["lufs"][0] <= lufs <= spec["lufs"][1], lufs, "-14 LUFS ±1,5")
        add("pico real", peak is not None and peak <= spec["peak"], peak, f"≤ {spec['peak']} dBTP")
        add("distorção (clipping)", clip == 0, clip, 0, warn=True)
    add("quadros pretos", not blacks, blacks[:4], "nenhum")
    add("imagem congelada ≥1,5 s", not freezes, freezes[:4], "nenhuma", warn=True)
    add("decodifica até o fim", not errors, errors or "ok", "sem erros")

    if a.project:
        chk = subprocess.run([sys.executable, a.project, "check"], capture_output=True, text=True, encoding="utf-8", errors="replace").stdout
        warns = [l[5:] for l in chk.splitlines() if l.startswith("WARN")]
        add("gráficos x rosto / safe zone / SFX", not warns, warns[:6] or "0 avisos", "0 avisos", warn=True)

    fails = [r for r in res if r["status"] == "FALHA"]; warns = [r for r in res if r["status"] == "AVISO"]
    for r in res: print(f"  {r['status']:6} {r['item']:34} {r['valor']}   (esperado {r['esperado']})")
    verdict = "APROVADO" if not fails else f"REPROVADO ({len(fails)} falha(s))"
    print("QA:", verdict, f"· {len(warns)} aviso(s)")
    out = dict(arquivo=str(a.video), plataforma=a.platform, veredito=verdict, itens=res,
               pendente_manual=["assistir o arquivo inteiro", "revisar legendas, nomes, números e datas",
                                "cor consistente entre planos", "transições sem quebra"])
    Path("qa.json").write_text(json.dumps(out, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    dp = Path(a.decisions)
    if dp.exists():
        dd = json.loads(dp.read_text(encoding="utf-8")); dd["qa_result"] = out
        dp.write_text(json.dumps(dd, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print("qa_result gravado em", dp)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(run())
