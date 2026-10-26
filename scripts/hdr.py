"""HDR → SDR for phone footage (iPhone records HLG by default; some Android/action cams record PQ).

    from hdr import tonemap, vf
    tonemap(src)                  # "" for SDR, else an ffmpeg filter chain that converts to Rec.709 SDR
    vf(src, "scale=...", ...)     # joins the non-empty parts with "," and puts the tone map last

Without this, HLG/PQ read as Rec.709 looks washed out with wrong colours. The chain linearises the source
(npl 203 nits = HLG/PQ reference white), maps it to bt709 primaries, tone maps with Hable (desat=0 keeps
skin saturated) and re-encodes as bt709 tv-range. Put it AFTER scale/crop: tone mapping runs in float, so
doing it on the 1080p frame instead of 4K is ~4x faster and looks the same.

    python hdr.py <video> ...     # prints the transfer of each file and whether it gets tone mapped
"""
import re, subprocess, sys
from functools import lru_cache
import imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()
TRC = {"arib-std-b67": "arib-std-b67", "smpte2084": "smpte2084"}    # HLG, PQ


@lru_cache(maxsize=256)
def transfer(src):
    """Transfer characteristic of the first video stream ("arib-std-b67", "smpte2084", "bt709", "" unknown)."""
    e = subprocess.run([FF, "-hide_banner", "-i", str(src)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace").stderr
    m = re.search(r"Video:[^\n]*?, [a-z0-9_]+\(([^)]*)\)", e)    # the pix_fmt's: yuv420p10le(tv, bt2020nc/bt2020/arib-std-b67)
    if not m: return ""
    for p in (x.strip() for x in m.group(1).split(",")):     # "tv", "space/primaries/transfer" (or one name), "progressive"
        if "/" in p: return p.split("/")[-1]
        if p.startswith(("bt", "smpte", "arib", "iec")): return p
    return ""


def is_hdr(src):
    return transfer(src) in TRC


def tonemap(src):
    t = TRC.get(transfer(src))
    if not t: return ""
    return (f"zscale=tin={t}:min=bt2020nc:pin=bt2020:t=linear:npl=203,format=gbrpf32le,zscale=p=bt709,"
            f"tonemap=tonemap=hable:desat=0,zscale=t=bt709:m=bt709:r=tv,format=yuv420p")


def vf(src, *parts):
    return ",".join(p for p in (*parts, tonemap(src)) if p)


if __name__ == "__main__":
    for f in sys.argv[1:]:
        t = transfer(f); print(f"{f}: {t or '?'}" + ("  -> tone map para SDR" if t in TRC else ""))
