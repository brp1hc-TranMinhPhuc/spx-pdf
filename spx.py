# -*- coding: utf-8 -*-
import argparse
from pathlib import Path
import fitz


def find_first_existing_font(candidates):
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def resolve_default_fonts():
    windows_fonts = Path(r"C:\Windows\Fonts")
    bold_candidates = [
        windows_fonts / "arialbd.ttf",
        windows_fonts / "tahomabd.ttf",
        Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ]
    viet_candidates = [
        windows_fonts / "arialbd.ttf",
        windows_fonts / "arial.ttf",
        windows_fonts / "tahoma.ttf",
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    font_bold = find_first_existing_font(bold_candidates)
    font_viet = find_first_existing_font(viet_candidates)
    if not font_bold:
        raise FileNotFoundError("Khong tim thay font in dam phu hop.")
    if not font_viet:
        raise FileNotFoundError("Khong tim thay font ho tro tieng Viet phu hop.")
    return font_bold, font_viet


def update_pdf(input_pdf, output_pdf, font_bold):
    doc = fitz.open(str(input_pdf))
    try:
        if doc.page_count == 0:
            raise ValueError("File PDF khong co trang nao.")

        white = (1, 1, 1)
        black = (0, 0, 0)

        for page in doc:
            all_words = page.get_text("words")

            # ── 1) Xử lý "SL: N" ──────────────────────────────────────────
            instances = page.search_for("SL:")

            for rect in instances:
                # Tìm index của word "SL:"
                sl_idx = None
                for i, w in enumerate(all_words):
                    if w[4].strip() in ("SL:", "SL") \
                            and abs(w[0] - rect.x0) < 5 \
                            and abs(w[1] - rect.y0) < 5:
                        sl_idx = i
                        break

                if sl_idx is None or sl_idx + 1 >= len(all_words):
                    continue

                next_w = all_words[sl_idx + 1]
                if not next_w[4].strip().isdigit():
                    continue

                quantity = int(next_w[4].strip())
                if quantity < 2:
                    continue  # SL:1 -> giữ nguyên

                full_text = f"SL: {quantity}"
                bold_font_sl = fitz.Font(fontfile=font_bold)

                # Vùng bao phủ cả "SL:" lẫn số gốc (dù cùng dòng hay khác dòng)
                x0 = rect.x0
                y0 = min(rect.y0, next_w[1])
                x1 = next_w[2]          # ✅ cạnh phải của số gốc – không vượt sang QR
                y1 = max(rect.y1, next_w[3])

                erase_rect = fitz.Rect(x0, y0, x1, y1)
                page.draw_rect(erase_rect, color=white, fill=white)

                # Tính fontsize vừa khớp chiều cao dòng "SL:" gốc
                line_h = rect.height          # chiều cao 1 dòng
                fontsize = line_h * 0.85      # 0.85 để không vượt ô

                # ✅ Nếu text rộng hơn vùng cho phép thì thu nhỏ thêm
                text_w = bold_font_sl.text_length(full_text, fontsize=fontsize)
                avail_w = x1 - x0
                if text_w > avail_w:
                    fontsize *= avail_w / text_w
                    text_w = avail_w

                # Baseline = y1 của dòng "SL:" (cùng dòng với chữ gốc)
                baseline_y = rect.y1 - 1

                tw = fitz.TextWriter(page.rect)
                tw.append(
                    (x0, baseline_y),
                    full_text,
                    font=bold_font_sl,
                    fontsize=fontsize,
                )
                tw.write_text(page, color=black)

            # ── 2) Xử lý "Combo": in đậm + gạch chân ─────────────────────
            combo_instances = page.search_for("Combo")

            for rect in combo_instances:
                combo_rect = fitz.Rect(rect)
                bold_font = fitz.Font(fontfile=font_bold)
                target_size = combo_rect.height * 1.05
                text_w = bold_font.text_length("Combo", fontsize=target_size)

                max_w = combo_rect.width * 1.3
                if text_w > max_w:
                    target_size *= max_w / text_w
                    text_w = max_w

                fit_size = target_size

                erase_rect = fitz.Rect(
                    combo_rect.x0, combo_rect.y0,
                    combo_rect.x0 + text_w + 1, combo_rect.y1
                )
                page.draw_rect(erase_rect, color=white, fill=white)

                tw2 = fitz.TextWriter(page.rect)
                tw2.append(
                    (combo_rect.x0, combo_rect.y1 - 1),
                    "Combo",
                    font=bold_font,
                    fontsize=fit_size,
                )
                tw2.write_text(page, color=black)

                page.draw_line(
                    fitz.Point(combo_rect.x0, combo_rect.y1 + 1),
                    fitz.Point(combo_rect.x0 + text_w, combo_rect.y1 + 1),
                    color=black, width=1.0,
                )

        output_pdf.parent.mkdir(parents=True, exist_ok=True)
        doc.save(str(output_pdf))
    finally:
        doc.close()


def parse_args():
    parser = argparse.ArgumentParser(description="Edit Shopee SPX shipping label")
    parser.add_argument("input_pdf", nargs="?", help="Input PDF path")
    parser.add_argument("output_pdf", nargs="?", help="Output PDF path")
    parser.add_argument("--font-bold", dest="font_bold", help="Bold font file path")
    parser.add_argument("--font-viet", dest="font_viet", help="Vietnamese-capable font file path")
    return parser.parse_args()


def main():
    args = parse_args()
    script_dir = Path(__file__).resolve().parent
    input_pdf  = Path(args.input_pdf)  if args.input_pdf  else script_dir / "test.pdf"
    output_pdf = Path(args.output_pdf) if args.output_pdf else script_dir / "label_updated.pdf"

    if not input_pdf.exists():
        raise FileNotFoundError(f"Khong tim thay file input: {input_pdf}")

    default_bold, default_viet = resolve_default_fonts()
    font_bold = args.font_bold or default_bold

    update_pdf(input_pdf, output_pdf, font_bold=font_bold)
    print(f"Da luu: {output_pdf}")


if __name__ == "__main__":
    main()
