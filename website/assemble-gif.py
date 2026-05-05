from PIL import Image
import os

OUT_DIR = '/home/zhuo/tiny-dec-internal/assets/demo-frames'
GIF_PATH = '/home/zhuo/tiny-dec-internal/assets/demo.gif'

frames = []
files = sorted(f for f in os.listdir(OUT_DIR) if f.endswith('.png'))
print(f"Found {len(files)} frames")

for f in files:
    img = Image.open(os.path.join(OUT_DIR, f))
    img = img.resize((1280, 720), Image.LANCZOS)
    img = img.convert('RGB').quantize(colors=256, method=Image.Quantize.MEDIANCUT)
    frames.append(img)

durations = []

stage_callouts = [
    0, 2, 4, 8, 5, 6, 3, 4, 4, 4, 4, 3, 3, 3, 4, 3, 3, 3, 4, 3, 3, 0
]

# Frame 0: hero
durations.append(2000)

for stage in range(1, 21):
    durations.append(1200)   # popup
    for _ in range(stage_callouts[stage]):
        durations.append(800)  # callout
    durations.append(600)    # free browse

# Complete
durations.append(2500)

print(f"Duration entries: {len(durations)}, frames: {len(frames)}")
assert len(durations) == len(frames), f"Mismatch: {len(durations)} durations vs {len(frames)} frames"

frames[0].save(
    GIF_PATH,
    save_all=True,
    append_images=frames[1:],
    duration=durations,
    loop=0,
    optimize=True,
)

total_sec = sum(durations) / 1000
size_mb = os.path.getsize(GIF_PATH) / (1024 * 1024)
print(f"GIF saved: {GIF_PATH} ({size_mb:.1f} MB, {total_sec:.0f}s total)")
