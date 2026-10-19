"""Thumbnail design studio generating high-contrast 9:16 safe-zone covers with Vietnamese typography."""

import os

from PIL import Image, ImageDraw, ImageEnhance, ImageFont


class ThumbnailService:
    # 9:16 Standard Canvas Dimensions
    CANVAS_WIDTH = 1080
    CANVAS_HEIGHT = 1920

    # Safe Zone margins to avoid UI overlaps on TikTok, Instagram/Facebook Reels, and YouTube Shorts
    SAFE_TOP = 220       # Avoid back button, search bar, status bar
    SAFE_BOTTOM = 440    # Avoid channel name, video caption lines, music ticker
    SAFE_RIGHT = 150     # Avoid like, comment, bookmark, share icons
    SAFE_LEFT = 70       # Avoid edge cropping
    SAFE_WIDTH = CANVAS_WIDTH - SAFE_LEFT - SAFE_RIGHT  # 860px max width for text

    def __init__(self):
        self.font_path = self._detect_best_unicode_font()

    def _detect_best_unicode_font(self) -> str | None:
        """Detect available font with Vietnamese Unicode diacritics support."""
        candidates = [
            # Linux / Docker paths
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
            # Windows paths
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "C:/Windows/Fonts/segoeui.ttf",
            "C:/Windows/Fonts/tahoma.ttf",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def get_font(self, size: int) -> ImageFont.ImageFont:
        """Load truetype font or fallback to default."""
        if self.font_path:
            try:
                return ImageFont.truetype(self.font_path, size)
            except Exception:
                pass
        return ImageFont.load_default()

    def _wrap_text(self, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
        """Word wrap text to fit within max_width pixels."""
        words = text.split()
        if not words:
            return []

        lines = []
        current_line = []

        dummy_img = Image.new("RGB", (1, 1))
        draw = ImageDraw.Draw(dummy_img)

        for word in words:
            test_line = " ".join(current_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            line_w = bbox[2] - bbox[0]
            if line_w <= max_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(" ".join(current_line))
                    current_line = [word]
                else:
                    lines.append(word)
        if current_line:
            lines.append(" ".join(current_line))
        return lines

    def _prepare_base_frame(self, frame_path: str) -> Image.Image:
        """Load frame, resize/crop to 1080x1920 (9:16), apply subtle contrast & saturation boost."""
        with Image.open(frame_path) as img:
            img = img.convert("RGB")
            iw, ih = img.size

            # Target aspect 9:16 (0.5625)
            target_aspect = self.CANVAS_WIDTH / self.CANVAS_HEIGHT
            img_aspect = iw / ih

            if img_aspect > target_aspect:
                # Video is wider than 9:16 (e.g. 16:9), crop sides
                new_w = int(ih * target_aspect)
                left = (iw - new_w) // 2
                cropped = img.crop((left, 0, left + new_w, ih))
            else:
                # Video is narrower, crop top/bottom
                new_h = int(iw / target_aspect)
                top = (ih - new_h) // 2
                cropped = img.crop((0, top, iw, top + new_h))

            resized = cropped.resize((self.CANVAS_WIDTH, self.CANVAS_HEIGHT), Image.Resampling.LANCZOS)

            # Enhance contrast and color vibrancy for eye-catching thumbnails
            enhancer = ImageEnhance.Contrast(resized)
            resized = enhancer.enhance(1.15)
            sat_enhancer = ImageEnhance.Color(resized)
            resized = sat_enhancer.enhance(1.2)

            return resized

    def generate_three_variants(
        self,
        frame_paths: list[str],
        title: str,
        output_dir: str,
        subtitle: str | None = None,
    ) -> list[str]:
        """Generate 3 distinct 9:16 thumbnail designs from input frame paths."""
        os.makedirs(output_dir, exist_ok=True)
        if not frame_paths:
            raise ValueError("Cần ít nhất một ảnh frame để thiết kế thumbnail")

        results = []

        # Variant 1: Bold Top Hook with Gradient Banner
        f1 = frame_paths[0]
        out1 = os.path.join(output_dir, "cover_variant_1_top_hook.jpg")
        self._render_variant_1(f1, title, out1, subtitle)
        results.append(out1)

        # Variant 2: Centered Impact Question with Drop Shadow & Accent Border
        f2 = frame_paths[1] if len(frame_paths) > 1 else frame_paths[0]
        out2 = os.path.join(output_dir, "cover_variant_2_center_impact.jpg")
        self._render_variant_2(f2, title, out2)
        results.append(out2)

        # Variant 3: Lower-Third Safe Badge with High-Contrast Box
        f3 = frame_paths[2] if len(frame_paths) > 2 else frame_paths[0]
        out3 = os.path.join(output_dir, "cover_variant_3_lower_third.jpg")
        self._render_variant_3(f3, title, out3, subtitle)
        results.append(out3)

        return results

    def _render_variant_1(self, frame_path: str, title: str, output_path: str, subtitle: str | None) -> None:
        """Variant 1: Top safe-zone hook banner with dark translucent gradient."""
        base = self._prepare_base_frame(frame_path)
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)

        # Top dark gradient banner
        for y in range(700):
            alpha = int(220 * (1 - (y / 700) ** 1.5))
            draw_ov.line([(0, y), (self.CANVAS_WIDTH, y)], fill=(0, 0, 0, alpha))

        base.paste(overlay, (0, 0), overlay)
        draw = ImageDraw.Draw(base)

        font_title = self.get_font(68)
        font_badge = self.get_font(34)

        # Render Top Category Badge (e.g. HOT / BÍ QUYẾT)
        badge_text = "TỔNG HỢP NỔI BẬT"
        draw.rounded_rectangle([self.SAFE_LEFT, self.SAFE_TOP, self.SAFE_LEFT + 280, self.SAFE_TOP + 55], radius=10, fill=(255, 30, 80))
        draw.text((self.SAFE_LEFT + 20, self.SAFE_TOP + 10), badge_text, font=font_badge, fill=(255, 255, 255))

        # Render Main Title
        y_cursor = self.SAFE_TOP + 75
        lines = self._wrap_text(title.upper(), font_title, self.SAFE_WIDTH)
        for line in lines[:3]:
            # Stroke for readability
            draw.text((self.SAFE_LEFT, y_cursor), line, font=font_title, fill=(255, 255, 0), stroke_width=4, stroke_fill=(0, 0, 0))
            bbox = draw.textbbox((self.SAFE_LEFT, y_cursor), line, font=font_title)
            y_cursor += (bbox[3] - bbox[1]) + 15

        base.save(output_path, "JPEG", quality=95)

    def _render_variant_2(self, frame_path: str, title: str, output_path: str) -> None:
        """Variant 2: Centered punchy typography with high-contrast background card."""
        base = self._prepare_base_frame(frame_path)
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)

        # Center vignette
        font = self.get_font(72)
        lines = self._wrap_text(title.upper(), font, self.SAFE_WIDTH - 80)
        line_height = 95
        total_h = len(lines[:3]) * line_height + 80
        center_y = (self.CANVAS_HEIGHT // 2) - (total_h // 2)

        # Translucent dark card behind text
        card_box = [self.SAFE_LEFT, center_y, self.SAFE_LEFT + self.SAFE_WIDTH, center_y + total_h]
        draw_ov.rounded_rectangle(card_box, radius=24, fill=(10, 10, 15, 215), outline=(255, 220, 0, 255), width=6)
        base.paste(overlay, (0, 0), overlay)

        draw = ImageDraw.Draw(base)
        y_pos = center_y + 40
        for idx, line in enumerate(lines[:3]):
            color = (255, 255, 255) if idx != 1 else (255, 230, 0)
            bbox = draw.textbbox((0, 0), line, font=font)
            line_w = bbox[2] - bbox[0]
            x_pos = self.SAFE_LEFT + (self.SAFE_WIDTH - line_w) // 2
            draw.text((x_pos, y_pos), line, font=font, fill=color, stroke_width=3, stroke_fill=(0, 0, 0))
            y_pos += line_height

        base.save(output_path, "JPEG", quality=95)

    def _render_variant_3(self, frame_path: str, title: str, output_path: str, subtitle: str | None) -> None:
        """Variant 3: Lower-third high-impact badge above bottom safe-zone margin."""
        base = self._prepare_base_frame(frame_path)
        overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
        draw_ov = ImageDraw.Draw(overlay)

        # Dark gradient coming up from bottom
        for y in range(self.CANVAS_HEIGHT - 900, self.CANVAS_HEIGHT):
            ratio = (y - (self.CANVAS_HEIGHT - 900)) / 900
            alpha = int(240 * (ratio ** 1.2))
            draw_ov.line([(0, y), (self.CANVAS_WIDTH, y)], fill=(5, 5, 10, alpha))

        base.paste(overlay, (0, 0), overlay)
        draw = ImageDraw.Draw(base)

        font_title = self.get_font(64)

        # Calculate position sitting right above SAFE_BOTTOM
        lines = self._wrap_text(title, font_title, self.SAFE_WIDTH)
        y_base = self.CANVAS_HEIGHT - self.SAFE_BOTTOM - (len(lines[:3]) * 85) - 60

        # Draw red accent bar
        draw.rectangle([self.SAFE_LEFT, y_base, self.SAFE_LEFT + 14, y_base + (len(lines[:3]) * 85)], fill=(255, 45, 85))

        y_pos = y_base
        for line in lines[:3]:
            draw.text((self.SAFE_LEFT + 30, y_pos), line, font=font_title, fill=(255, 255, 255), stroke_width=3, stroke_fill=(0, 0, 0))
            y_pos += 85

        base.save(output_path, "JPEG", quality=95)


thumbnail_service = ThumbnailService()
