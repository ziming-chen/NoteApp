"""Build the lab's own text fixture and flat-colour penguin image."""

from pathlib import Path

from PIL import Image, ImageDraw

from caesar import encrypt

ROOT = Path(__file__).resolve().parent


def make_inputs(data_dir: Path = ROOT / "data") -> None:
    plaintext = (data_dir / "caesar_plaintext.txt").read_text(encoding="utf-8")
    (data_dir / "caesar_ciphertext.txt").write_text(
        encrypt(plaintext, 7), encoding="utf-8"
    )

    image = Image.new("RGB", (512, 384), "#DBEAFE")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 322, 511, 383), fill="#F8FAFC")
    draw.ellipse((139, 306, 373, 353), fill="#BBCDE1")
    draw.ellipse((130, 174, 224, 294), fill="#172033")
    draw.ellipse((288, 174, 382, 294), fill="#172033")
    draw.ellipse((170, 125, 342, 332), fill="#172033")
    draw.ellipse((194, 163, 318, 316), fill="#FFFFFF")
    draw.ellipse((186, 51, 326, 195), fill="#172033")
    draw.ellipse((202, 83, 255, 146), fill="#FFFFFF")
    draw.ellipse((257, 83, 310, 146), fill="#FFFFFF")
    draw.ellipse((226, 105, 238, 123), fill="#172033")
    draw.ellipse((274, 105, 286, 123), fill="#172033")
    draw.polygon(((230, 138), (282, 138), (256, 159)), fill="#F59E0B")
    draw.ellipse((181, 307, 250, 340), fill="#F59E0B")
    draw.ellipse((263, 307, 332, 340), fill="#F59E0B")
    image.save(data_dir / "penguin.png")
    print("Created self-authored inputs: Caesar shift 7 and a 512 x 384 RGB penguin.")


if __name__ == "__main__":
    make_inputs()
