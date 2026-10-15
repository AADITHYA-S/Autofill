from __future__ import annotations

from typing import Any
import re

from PIL import ImageDraw, ImageFont

from backend.models.form_models import MatchField
from backend.models.identity_profile import IdentityProfile


class AutoFill:
    """Resolves matched fields to profile values and optionally renders values on an image."""

    def __init__(self) -> None:
        self.profile: IdentityProfile | None = None

    def set_profile(self, profile: IdentityProfile) -> None:
        self.profile = profile

    # Canonical form fields are not always named exactly like the
    # IdentityProfile attributes. Keep this mapping in the final
    # resolution layer so the semantic matcher remains responsible
    # only for identifying what the form field means.
    CANONICAL_TO_PROFILE_FIELD = {
        "phone_number": "phone",
        "father_name": "guardian_name",
        "house_flat": "house_number",
    }

    def resolve_value(self, matched_field: MatchField) -> str | None:
        if not matched_field.canonical_field or self.profile is None:
            return None

        canonical_field = matched_field.canonical_field.strip().lower()

        profile_field = self.CANONICAL_TO_PROFILE_FIELD.get(
            canonical_field,
            canonical_field,
        )

        value = getattr(self.profile, profile_field, None)

        if value is None:
            return None

        if isinstance(value, str):
            value = value.strip()
            return value if value else None

        return str(value)

    def bbox_to_pixels(self, bbox: dict[str, float], image_width: int, image_height: int) -> dict[str, int]:
        return {
            "left": int(bbox["left"] * image_width),
            "top": int(bbox["top"] * image_height),
            "width": int(bbox["width"] * image_width),
            "height": int(bbox["height"] * image_height),
        }

    @staticmethod
    def _load_font(font_size: int):
        try:
            return ImageFont.truetype("arial.ttf", font_size)
        except OSError:
            # Fallback for environments without Arial.
            return ImageFont.load_default()

    # def _draw_text(self, image: Any, value: str, bbox: dict[str, int]) -> None:
    #     if not value:
    #         return

    #     draw = ImageDraw.Draw(image)

    #     field_height = bbox["height"]
    #     if field_height >= 30:
    #         font_size = 20
    #     elif field_height >= 20:
    #         font_size = 17
    #     else:
    #         font_size = 15

    #     font = self._load_font(font_size)
    #     text_bbox = draw.textbbox((0, 0), value, font=font)
    #     text_height = text_bbox[3] - text_bbox[1]

    #     x = bbox["left"]
    #     y = bbox["top"] + (bbox["height"] - text_height) / 2

    #     draw.text((x, y), value, font=font, fill="black")

    @staticmethod
    def _is_date_field(matched_field: MatchField) -> bool:
        canonical = (matched_field.canonical_field or "").strip().lower()
        label = re.sub(r"[^a-z]", "", (matched_field.form_field.label or "").lower())
        return (
            canonical in {"date_of_birth", "dob", "birth_date", "date"}
            or label in {"dob", "birthdate", "dateofbirth"}
        )

    @staticmethod
    def _date_as_ddmmyyyy(value: str) -> str | None:
        """Normalize common date representations to the form's DDMMYYYY cells."""
        value = str(value).strip()

        # Prefer interpreting explicitly separated dates rather than guessing.
        match = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})(?:[T ].*)?", value)
        if match:
            year, month, day = match.groups()
            digits = f"{day.zfill(2)}{month.zfill(2)}{year}"
            return digits if len(digits) == 8 else None

        match = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})(?:[T ].*)?", value)
        if match:
            day, month, year = match.groups()
            return f"{day.zfill(2)}{month.zfill(2)}{year}"

        digits = re.sub(r"\D", "", value)
        if len(digits) != 8:
            return None

        # For an unseparated ISO-style date, convert YYYYMMDD to DDMMYYYY.
        if 1900 <= int(digits[:4]) <= 2100:
            return digits[6:8] + digits[4:6] + digits[:4]
        return digits

    @staticmethod
    def _group_positions(positions: list[int]) -> list[int]:
        """Collapse adjacent dark pixels into the center of each detected line."""
        if not positions:
            return []
        groups: list[list[int]] = [[positions[0]]]
        for position in positions[1:]:
            if position <= groups[-1][-1] + 1:
                groups[-1].append(position)
            else:
                groups.append([position])
        return [round(sum(group) / len(group)) for group in groups]

    def _detect_date_cells(self, image: Any, bbox: dict[str, int]) -> tuple[list[int], int, int] | None:
        """Find an eight-cell DDMMYYYY row near the detected DOB value box.

        Textract may return a bounding box around the printed D/M/Y guide text
        below the cells instead of the actual empty boxes. Search nearby rows,
        preferring the closest valid row, and validate that eight regular cells
        and their horizontal borders are present before drawing.
        """
        gray = image.convert("L")
        pixels = gray.load()
        width, height = image.size
        bbox_center_y = int(bbox["top"] + bbox["height"] / 2)
        band_radius = max(3, min(8, int(bbox["height"] * 0.20)))
        band_height = band_radius * 2 + 1
        required_dark = max(2, int(band_height * 0.70))

        # Search the value-box center first, then nearby rows above/below it.
        # The negative offsets are important for forms where Textract detects
        # the D D M M Y Y Y Y guide text below the actual boxes.
        max_offset = max(60, int(bbox["height"] * 4))
        offsets = [0]
        for step in range(4, max_offset + 1, 4):
            offsets.extend([-step, step])

        left_limit = max(0, bbox["left"] - max(30, int(bbox["height"] * 1.5)))
        right_limit = min(width, max(bbox["left"] + 500, bbox["left"] + int(bbox["height"] * 12)))
        best = None

        for offset in offsets:
            center_y = bbox_center_y + offset
            if center_y < 0 or center_y >= height:
                continue
            y0 = max(0, center_y - band_radius)
            y1 = min(height, center_y + band_radius + 1)
            actual_band_height = max(1, y1 - y0)
            threshold = max(2, int(actual_band_height * 0.70))

            vertical_positions = []
            for x in range(left_limit, right_limit):
                dark_count = sum(1 for y in range(y0, y1) if pixels[x, y] < 125)
                if dark_count >= threshold:
                    vertical_positions.append(x)
            lines = self._group_positions(vertical_positions)
            if len(lines) < 9:
                continue

            nearest = min(range(len(lines)), key=lambda i: abs(lines[i] - bbox["left"]))
            gaps_all = [lines[i + 1] - lines[i] for i in range(len(lines) - 1)]
            positive_gaps = [gap for gap in gaps_all if gap > 0]
            if not positive_gaps:
                continue
            pitch_all = sorted(positive_gaps)[len(positive_gaps) // 2]
            if lines[nearest] > bbox["left"] + pitch_all * 0.30 and nearest > 0:
                nearest -= 1

            if nearest + 9 > len(lines):
                continue
            boundaries = lines[nearest:nearest + 9]
            gaps = [boundaries[i + 1] - boundaries[i] for i in range(8)]
            pitch = sorted(gaps)[len(gaps) // 2]
            if pitch < 5 or any(gap < pitch * 0.70 or gap > pitch * 1.30 for gap in gaps):
                continue

            x0 = boundaries[0] + 2
            x1 = boundaries[-1] - 2
            if x1 <= x0:
                continue
            search_radius = max(80, int(bbox["height"] * 4))
            scan_y0 = max(0, center_y - search_radius)
            scan_y1 = min(height, center_y + search_radius + 1)
            span = max(1, x1 - x0)
            horizontal_threshold = int(span * 0.70)
            horizontal_positions = []
            for y in range(scan_y0, scan_y1):
                dark_count = sum(1 for x in range(x0, x1) if pixels[x, y] < 125)
                if dark_count >= horizontal_threshold:
                    horizontal_positions.append(y)
            horizontal_lines = self._group_positions(horizontal_positions)
            above = [y for y in horizontal_lines if y < center_y]
            below = [y for y in horizontal_lines if y > center_y]
            if not above or not below:
                continue
            top = above[-1]
            bottom = below[0]
            if bottom - top < 8 or not (top <= center_y <= bottom):
                continue

            candidate = (boundaries, top, bottom, abs(offset))
            if best is None or candidate[3] < best[3]:
                best = candidate
                if offset == 0:
                    break

        if best is None:
            return None
        return best[0], best[1], best[2]

    def _draw_characters_in_date_cells(self, image: Any, digits: str, boundaries: list[int], top: int, bottom: int) -> None:
        draw = ImageDraw.Draw(image)
        cell_height = bottom - top

        for index, char in enumerate(digits[:8]):
            left = boundaries[index]
            right = boundaries[index + 1]
            cell_width = right - left
            font = self._fit_character_font(draw, char, cell_width, cell_height)
            # Sample the form background from the inside of each cell, then
            # clear only the cell interior. The inset preserves printed borders.
            sample_x = min(right - 2, left + 4)
            sample_y = min(bottom - 2, top + 4)
            background = image.getpixel((sample_x, sample_y))
            draw.rectangle((left + 2, top + 2, right - 2, bottom - 2), fill=background)

            char_bbox = draw.textbbox((0, 0), char, font=font)
            char_width = char_bbox[2] - char_bbox[0]
            char_height = char_bbox[3] - char_bbox[1]
            x = left + ((right - left) - char_width) / 2 - char_bbox[0]
            y = top + (cell_height - char_height) / 2 - char_bbox[1]
            draw.text((x, y), char, font=font, fill="black")

    def _detect_segmented_field_cells(
        self, image: Any, bbox: dict[str, int]
    ) -> list[int] | None:
        """Detect a row of character boxes inside a field bounding box.

        Ordinary text fields usually have only their left/right borders, so
        this returns boundaries only when multiple internal vertical dividers
        are present with reasonably consistent spacing.
        """
        gray = image.convert("L")
        pixels = gray.load()
        image_width, image_height = image.size

        left = max(0, bbox["left"])
        right = min(image_width, bbox["left"] + bbox["width"])
        top = max(0, bbox["top"])
        bottom = min(image_height, bbox["top"] + bbox["height"])
        if right - left < 20 or bottom - top < 8:
            return None

        row_height = bottom - top
        # Avoid the horizontal borders, while allowing slight bbox inaccuracies.
        y0 = min(bottom - 1, top + max(1, int(row_height * 0.12)))
        y1 = max(y0 + 1, bottom - max(1, int(row_height * 0.12)))
        scan_height = y1 - y0
        min_dark = max(4, int(scan_height * 0.58))

        vertical_positions: list[int] = []
        for x in range(left, right):
            dark_count = sum(1 for y in range(y0, y1) if pixels[x, y] < 125)
            if dark_count >= min_dark:
                vertical_positions.append(x)

        boundaries = self._group_positions(vertical_positions)
        if len(boundaries) < 4:
            return None

        # Keep boundaries that form a consistent character grid. If the value
        # bbox includes extra vertical strokes, reject rather than corrupt text.
        gaps = [boundaries[i + 1] - boundaries[i] for i in range(len(boundaries) - 1)]
        positive_gaps = [gap for gap in gaps if gap > 0]
        if len(positive_gaps) < 3:
            return None
        pitch = sorted(positive_gaps)[len(positive_gaps) // 2]
        if pitch < 5:
            return None

        # Find the longest contiguous run of regularly spaced dividers.
        runs: list[list[int]] = []
        current = [boundaries[0]]
        for boundary in boundaries[1:]:
            gap = boundary - current[-1]
            if pitch * 0.65 <= gap <= pitch * 1.35:
                current.append(boundary)
            else:
                if len(current) >= 4:
                    runs.append(current)
                current = [boundary]
        if len(current) >= 4:
            runs.append(current)

        if not runs:
            return None

        run = max(runs, key=len)
        run_gaps = [run[i + 1] - run[i] for i in range(len(run) - 1)]
        run_pitch = sorted(run_gaps)[len(run_gaps) // 2]
        if any(gap < run_pitch * 0.65 or gap > run_pitch * 1.35 for gap in run_gaps):
            return None

        # A usable grid should have at least three cells, not just the two
        # outside borders of a normal rectangular input.
        if len(run) - 1 < 3:
            return None
        return run

    def _fit_character_font(
        self,
        draw: ImageDraw.ImageDraw,
        char: str,
        cell_width: int,
        cell_height: int,
    ) -> ImageFont.ImageFont:
        """Use a slightly larger font while ensuring the character fits its cell."""
        max_size = max(8, min(18, int(cell_height * 0.64), int(cell_width * 0.76)))
        min_size = 7

        for font_size in range(max_size, min_size - 1, -1):
            font = self._load_font(font_size)
            char_bbox = draw.textbbox((0, 0), char, font=font)
            char_width = char_bbox[2] - char_bbox[0]
            char_height = char_bbox[3] - char_bbox[1]
            if char_width <= cell_width - 3 and char_height <= cell_height - 3:
                return font

        return self._load_font(min_size)

    def _draw_text_in_cells(self, image: Any, value: str, cells: list[Any]) -> None:
        if not value:
            return

        draw = ImageDraw.Draw(image)
        for char, cell in zip(str(value), cells):
            bbox = self.bbox_to_pixels(cell.bbox, image.width, image.height)
            left, top = bbox["left"], bbox["top"]
            right, bottom = left + bbox["width"], top + bbox["height"]
            if bbox["width"] < 3 or bbox["height"] < 3:
                continue
            background = image.getpixel((min(right - 2, left + 3), min(bottom - 2, top + 3)))
            draw.rectangle((left + 2, top + 2, right - 2, bottom - 2), fill=background)
            font = self._fit_character_font(draw, char, bbox["width"], bbox["height"])
            char_bbox = draw.textbbox((0, 0), char, font=font)
            char_width = char_bbox[2] - char_bbox[0]
            char_height = char_bbox[3] - char_bbox[1]
            x = left + (bbox["width"] - char_width) / 2 - char_bbox[0]
            y = top + (bbox["height"] - char_height) / 2 - char_bbox[1]
            draw.text((x, y), char, font=font, fill="black")

    def _draw_text(self, image: Any, value: str, bbox: dict[str, int]) -> None:
        if not value:
            return

        draw = ImageDraw.Draw(image)

        # Field dimensions
        field_width = bbox["width"]
        field_height = bbox["height"]

        # Use a more conservative font size for ordinary fields. Many forms
        # use narrow character-grid boxes inside a larger detected value area;
        # a 20px font can make uppercase names visually crowded even when the
        # complete string technically fits the overall bounding box.
        max_font_size = max(8, min(15, int(field_height * 0.62)))
        min_font_size = 7

        # Padding so text doesn't touch the field boundaries
        horizontal_padding = 4
        vertical_padding = 2

        available_width = field_width - (horizontal_padding * 2)
        available_height = field_height - (vertical_padding * 2)

        # Start with the largest font
        font_size = max_font_size

        # Reduce font size until the complete value fits
        while font_size >= min_font_size:

            font = self._load_font(font_size)

            text_bbox = draw.textbbox(
                (0, 0),
                value,
                font=font
            )

            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

            if (
                text_width <= available_width
                and text_height <= available_height
            ):
                break

            font_size -= 1

        # If even the minimum font does not fit,
        # use the minimum readable size.
        if font_size < min_font_size:
            font_size = min_font_size
            font = self._load_font(font_size)

            text_bbox = draw.textbbox(
                (0, 0),
                value,
                font=font
            )

            text_width = text_bbox[2] - text_bbox[0]
            text_height = text_bbox[3] - text_bbox[1]

        # Center text vertically inside the field
        x = bbox["left"] + horizontal_padding

        y = (
            bbox["top"]
            + (field_height - text_height) / 2
            - text_bbox[1]
        )

        draw.text(
            (x, y),
            value,
            font=font,
            fill="black"
        )

    def fill_field(self, image: Any, matched_field: MatchField, cells: list[Any] | None = None) -> None:
        # A type mismatch is a safety stop: leave the field blank for manual review.
        if matched_field.type_compatible is False:
            return

        value = self.resolve_value(matched_field)
        if not value:
            return

        value_bbox = matched_field.form_field.value_bbox
        if value_bbox is None:
            return

        pixel_bbox = self.bbox_to_pixels(value_bbox, image.width, image.height)

        if self._is_date_field(matched_field):
            date_digits = self._date_as_ddmmyyyy(value)
            # This form uses eight separate DDMMYYYY boxes. Do not fall back to
            # drawing the entire date string if the boxes cannot be detected.
            if not date_digits:
                return
            detected = self._detect_date_cells(image, pixel_bbox)
            if detected:
                boundaries, top, bottom = detected
                self._draw_characters_in_date_cells(image, date_digits, boundaries, top, bottom)
                return
            if cells and len(cells) >= 8:
                self._draw_text_in_cells(image, date_digits, cells[:8])
                return
            # Last-resort fallback keeps the field fillable when this template's
            # cell borders cannot be detected. The preferred path above still
            # writes one digit per box whenever the row is detected reliably.
            self._draw_text(image, value, pixel_bbox)
            return

        # Character-grid fields (e.g. first name / last name boxes) need one
        # character per cell. Detect the grid directly from the image because
        # Textract may not return reliable cell_boxes for these rows.
        segmented_boundaries = self._detect_segmented_field_cells(image, pixel_bbox)
        if segmented_boundaries:
            cell_height = pixel_bbox["height"]
            top = pixel_bbox["top"]
            bottom = top + cell_height
            detected_cells = []
            for index in range(len(segmented_boundaries) - 1):
                left = segmented_boundaries[index]
                right = segmented_boundaries[index + 1]
                detected_cells.append(
                    type("DetectedCell", (), {
                        "bbox": {
                            "left": left / image.width,
                            "top": top / image.height,
                            "width": (right - left) / image.width,
                            "height": cell_height / image.height,
                        }
                    })()
                )
            self._draw_text_in_cells(image, value, detected_cells)
            return

        if cells:
            self._draw_text_in_cells(image, value, cells)
            return

        self._draw_text(image, value, pixel_bbox)

    def fill_form(
        self,
        image: Any,
        matched_fields: list[MatchField],
        cell_boxes: list[Any] | None = None,
        extractor: Any | None = None,
    ) -> Any:
        for matched_field in matched_fields:
            field_bbox = matched_field.form_field.value_bbox
            if field_bbox is None:
                continue

            cells = []
            if cell_boxes and extractor:
                cells = extractor.get_reliable_cells_for_field(field_bbox, cell_boxes)

            self.fill_field(image, matched_field, cells)

        return image

    def fill(
        self,
        image,
        textract_result,
        matched_fields,
        identity_profile,
        checkbox_options=None
    ):
        self.set_profile(identity_profile)

        print("\n========== AUTOFILL VALUES ==========")

        for matched_field in matched_fields:

            value = self.resolve_value(matched_field)

            print(
                "Label:",
                matched_field.form_field.label,
                "| Canonical:",
                matched_field.canonical_field,
                "| Value:",
                value
            )

        print("====================================\n")

        # Your existing rendering logic
        filled_image = self.fill_form(
            image,
            matched_fields
        )
        if checkbox_options:
            self.fill_checkboxes(
                filled_image,
                checkbox_options
            )

        from pathlib import Path
        from uuid import uuid4

        output_dir = Path("outputs")
        output_dir.mkdir(exist_ok=True)

        output_path = (
            output_dir /
            f"filled_form_{uuid4().hex}.png"
        )

        filled_image.save(output_path)

        return str(output_path)

    def _draw_checkbox(
        self,
        image: Any,
        checkbox_bbox: dict[str, int]
    ) -> None:

        draw = ImageDraw.Draw(image)

        left = checkbox_bbox["left"]
        top = checkbox_bbox["top"]
        width = checkbox_bbox["width"]
        height = checkbox_bbox["height"]

        # Draw a check mark using two lines.
        # This avoids depending on a font containing the ✓ character.

        x1 = left + width * 0.20
        y1 = top + height * 0.52

        x2 = left + width * 0.43
        y2 = top + height * 0.75

        x3 = left + width * 0.80
        y3 = top + height * 0.25

        line_width = max(
            2,
            int(min(width, height) * 0.12)
        )

        draw.line(
            [(x1, y1), (x2, y2), (x3, y3)],
            fill="black",
            width=line_width
        )


    def _normalize_option(self, value: str) -> str:
        if not value:
            return ""

        value = value.lower().strip()

        # Remove common punctuation
        value = value.replace(":", "")
        value = value.replace(".", "")
        value = value.replace("-", " ")

        # Normalize spaces
        value = " ".join(value.split())

        return value

    def _should_select_checkbox(
        self,
        label: str,
        checkbox_options: dict[str, Any]
    ) -> bool:

        if not label:
            return False

        label_normalized = self._normalize_option(label)

        # Gender
        if self.profile and self.profile.gender:

            profile_gender = self._normalize_option(
                self.profile.gender
            )

            if label_normalized == profile_gender:
                return True

        return False

    def fill_checkboxes(
        self,
        image: Any,
        checkbox_options: list[dict[str, Any]]
    ) -> None:

        for option in checkbox_options:

            label = option.get("label", "")
            checkbox = option.get("checkbox")

            if not checkbox:
                continue

            if not self._should_select_checkbox(
                label,
                checkbox
            ):
                continue

            pixel_bbox = self.bbox_to_pixels(
                checkbox["bbox"],
                image.width,
                image.height
            )

            self._draw_checkbox(
                image,
                pixel_bbox
            )