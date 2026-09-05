"""Generate the independent PW3 landscape V9 visual mockup."""

from pathlib import Path

from app import LANDSCAPE_HEIGHT, LANDSCAPE_WIDTH, PALETTE, load_fixture, prepare_data, render_landscape_v9


if __name__ == "__main__":
    data, degraded = prepare_data(load_fixture("fixtures/demo.json"))
    target = Path("public/pages/landscape-mockup-v9.png")
    target.parent.mkdir(parents=True, exist_ok=True)
    image = render_landscape_v9(data)
    image.save(target, format="PNG", bits=4, optimize=True)
    print(f"generated {target} {LANDSCAPE_WIDTH}x{LANDSCAPE_HEIGHT} palette={len(PALETTE)} degraded={degraded}")
