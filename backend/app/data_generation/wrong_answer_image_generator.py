from __future__ import annotations

import random
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont


IMAGE_SIZE = (900, 540)
BACKGROUND = (255, 253, 247)
INK = (32, 37, 44)
LIGHT_GRAY = (224, 228, 235)
RED = (218, 48, 62)
BLUE = (40, 99, 180)


class WrongAnswerImageGenerator:
    """Creates simple synthetic wrong-answer worksheet PNGs."""

    def __init__(self, seed: int = 20260526) -> None:
        self.rng = random.Random(seed)

    def generate_image(
        self,
        output_path: str | Path,
        student_hash: str,
        task_id: str,
        knowledge_point: str,
        question: str,
        error_type: str,
    ) -> str:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        image = Image.new("RGB", IMAGE_SIZE, BACKGROUND)
        draw = ImageDraw.Draw(image)
        font_title = _load_font(26)
        font_body = _load_font(22)
        font_small = _load_font(18)
        font_red = _load_font(24)

        self._draw_paper_lines(draw)
        draw.text((40, 32), "Synthetic Math Wrong-Answer Sample", fill=BLUE, font=font_title)
        draw.text((40, 76), f"Task: {task_id}    Student: {student_hash}", fill=(96, 104, 116), font=font_small)
        draw.text((40, 122), f"Question: {question}", fill=INK, font=font_body)

        wrong_steps = _wrong_steps_for(knowledge_point, error_type)
        y = 178
        for idx, step in enumerate(wrong_steps, start=1):
            draw.text((70, y), f"{idx}. {step}", fill=INK, font=font_body)
            y += 58

        self._draw_teacher_marks(draw, y_start=180, line_count=len(wrong_steps), font=font_red)
        draw.text(
            (70, 452),
            f"Teacher note: check {error_type}; redo the key step.",
            fill=RED,
            font=font_red,
        )
        draw.rectangle((35, 28, 865, 500), outline=(232, 236, 242), width=2)

        image.save(output_path, format="PNG")
        return str(output_path)

    def _draw_paper_lines(self, draw: ImageDraw.ImageDraw) -> None:
        for y in range(112, 500, 42):
            draw.line((38, y, 862, y), fill=LIGHT_GRAY, width=1)

    def _draw_teacher_marks(
        self,
        draw: ImageDraw.ImageDraw,
        y_start: int,
        line_count: int,
        font: ImageFont.ImageFont,
    ) -> None:
        mark_y = y_start + self.rng.randint(0, max(1, line_count - 1)) * 58
        draw.line((42, mark_y + 8, 58, mark_y + 36), fill=RED, width=5)
        draw.line((58, mark_y + 36, 92, mark_y - 4), fill=RED, width=5)
        draw.ellipse((735, mark_y - 10, 830, mark_y + 42), outline=RED, width=4)
        draw.text((740, mark_y + 50), "Why?", fill=RED, font=font)
        draw.arc((680, 338, 840, 442), start=200, end=340, fill=RED, width=4)
        draw.polygon([(836, 404), (812, 400), (824, 424)], fill=RED)


def _wrong_steps_for(knowledge_point: str, error_type: str) -> list[str]:
    if knowledge_point == "quadratic vertex form":
        return [
            "y=(x-2)^2-3, so the vertex is (-2, -3).",
            "Axis of symmetry: x=-2.",
            "The graph moves left 2 and down 3.",
        ]
    if knowledge_point == "linear equation solving":
        return [
            "3x+5=20",
            "3x=20+5",
            "x=25/3",
        ]
    if knowledge_point == "fraction simplification":
        return [
            "6/8 = (6+2)/(8+2)",
            "6/8 = 8/10",
            "Answer: 4/5",
        ]
    if knowledge_point == "proportional relationship":
        return [
            "4 notebooks cost 12, so add 3 notebooks.",
            "12+3=15",
            "7 notebooks cost 15 yuan.",
        ]
    if knowledge_point == "function graph interpretation":
        return [
            "Slope = (2-0)/(6-2)",
            "Slope = 2/4",
            "Answer: 1/2",
        ]
    if knowledge_point == "arithmetic sequence":
        return [
            "a_n = a_1 + n*d",
            "a_10 = 3 + 10*2",
            "a_10 = 23",
        ]
    return [
        f"Wrong reasoning pattern: {error_type}.",
        "Skipped the rule check.",
        "Final answer copied too early.",
    ]


def _load_font(size: int) -> ImageFont.ImageFont:
    candidates = (
        "arial.ttf",
        "DejaVuSans.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    )
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()
