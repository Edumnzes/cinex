"""Planar tracking for "text stuck to the scene": follow a surface (wall, screen, floor) marked by 4 corners.

    from plane_track import track
    quads = track("cut.mp4", t_mark=12.0, t0=10.0, t1=15.0, quad=[[x, y], ...])   # quad normalised 0..1, clockwise from top-left

Returns {frame_index: [[x, y] * 4]} in pixels of the video for every frame in [t0, t1].
Every frame is matched against the MARKED frame (SIFT features of the background around the surface, people removed
with the MediaPipe matte), and a homography (RANSAC) maps the marked quad into it. Matching to the reference instead of
frame-to-frame means no drift and recovery after a cut. Frames that can't be matched hold the last good quad; a short
centred moving average removes jitter.
"""
import re, subprocess
import numpy as np, cv2, imageio_ffmpeg

FF = imageio_ffmpeg.get_ffmpeg_exe()


def _probe(src):
    e = subprocess.run([FF, "-hide_banner", "-i", str(src)], capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    w, h = map(int, re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", e).groups())
    return w, h, float(re.search(r"([\d.]+) fps", e).group(1))


def _frames(src, ss, n, w, h, aw):
    ah = int(round(aw * h / w / 2) * 2)
    p = subprocess.Popen([FF, "-loglevel", "error", "-ss", f"{ss:.3f}", "-i", str(src), "-frames:v", str(n), "-vf", f"scale={aw}:{ah}",
                          "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    out = []
    while True:
        b = p.stdout.read(aw * ah * 3)
        if len(b) < aw * ah * 3: break
        out.append(np.frombuffer(b, np.uint8).reshape(ah, aw, 3))
    return out, aw / w


class _People:
    """Binary 'not a person' mask (MediaPipe matte); everything allowed if the model is unavailable."""
    def __init__(self):
        try:
            import sys; from pathlib import Path; sys.path.insert(0, str(Path(__file__).resolve().parent))
            from reels_lib import _Matte; self.m = _Matte()
        except Exception: self.m = None
    def background(self, rgb):
        if self.m is None: return np.full(rgb.shape[:2], 255, np.uint8)
        self.m.prev = None                                   # independent frames here: no temporal smoothing
        a = self.m.alpha(rgb, 0)[..., 0]
        return cv2.erode(((a < .3) * 255).astype(np.uint8), np.ones((9, 9), np.uint8))


def track(src, t_mark, t0, t1, quad, analysis_w=540, smooth=5, every=1):
    w, h, fps = _probe(src)
    n = int(round((t1 - t0) * fps)) + 1
    frames, k = _frames(src, t0, n, w, h, analysis_w)
    if not frames: return {}
    H, W = frames[0].shape[:2]
    m = min(len(frames) - 1, max(0, int(round((t_mark - t0) * fps))))
    q0 = np.float32(quad) * np.float32([W, H])
    people = _People(); sift = cv2.SIFT_create(1500)
    # reference: background features in a generous region around the surface on the marked frame
    reg = np.zeros((H, W), np.uint8); c = q0.mean(0)
    cv2.fillConvexPoly(reg, np.clip((q0 - c) * 1.8 + c, 0, [W - 1, H - 1]).astype(np.int32), 255)
    ref = frames[m]; rmask = cv2.bitwise_and(reg, people.background(ref))
    kr, dr = sift.detectAndCompute(cv2.cvtColor(ref, cv2.COLOR_RGB2GRAY), rmask)
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    quads, last, held = [], q0.copy(), 0
    for i, fr in enumerate(frames):
        if i == m or dr is None or len(kr) < 8: quads.append(q0.copy() if i == m else last.copy()); continue
        if i % every and quads: quads.append(last.copy()); continue
        g = cv2.cvtColor(fr, cv2.COLOR_RGB2GRAY)
        kc, dc = sift.detectAndCompute(g, people.background(fr))
        Hm = None
        if dc is not None and len(kc) >= 8:
            good = [a for a, b in (x for x in matcher.knnMatch(dr, dc, k=2) if len(x) == 2) if a.distance < .72 * b.distance]
            if len(good) >= 10:
                A = np.float32([kr[g_.queryIdx].pt for g_ in good]); B = np.float32([kc[g_.trainIdx].pt for g_ in good])
                Hm, inl = cv2.findHomography(A, B, cv2.RANSAC, 3.0)
                if Hm is not None and inl.sum() < 8: Hm = None
        if Hm is not None:
            q = cv2.perspectiveTransform(q0.reshape(-1, 1, 2), Hm).reshape(4, 2)
            if cv2.contourArea(q) > .2 * cv2.contourArea(q0) and cv2.isContourConvex(q.astype(np.float32)): last = q; held = 0
            else: held += 1
        else: held += 1
        quads.append(last.copy())
    arr = np.stack(quads)
    if smooth > 1 and len(arr) > smooth:
        pad = np.pad(arr, ((smooth // 2, smooth // 2), (0, 0), (0, 0)), mode="edge")
        arr = np.stack([pad[i:i + smooth].mean(0) for i in range(len(arr))])
    f0 = int(round(t0 * fps))
    return {f0 + i: (arr[i] / k).tolist() for i in range(len(arr))}
