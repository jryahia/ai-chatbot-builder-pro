"""Widget customization page: color picker, position, embed code, API key generation."""

from typing import Callable, Optional

import flet as ft
import httpx

from src.config import settings
from src.ui.components import (
    ACCENT,
    ACCENT2,
    BG,
    BORDER_COLOR,
    CARD,
    ERROR,
    SUCCESS,
    SURFACE,
    TEXT,
    TEXT2,
    card,
    code_block,
    danger_button,
    divider,
    icon_button,
    label,
    primary_button,
    secondary_button,
    section_header,
    show_error,
    show_success,
    text_field,
    title,
)


class EmbedView:
    def __init__(
        self,
        page: ft.Page,
        project_id: str,
        navigate: Callable[[str, Optional[str]], None],
    ) -> None:
        self.page = page
        self.project_id = project_id
        self.navigate = navigate
        self.api_base = settings.api_base_url

        # Widget config state
        self.primary_color: str = "#4f8cff"
        self.widget_bg_color: str = "#1a1d27"
        self.widget_text_color: str = "#f1f5f9"
        self.position: str = "bottom-right"
        self.welcome_message: str = "Hi! How can I help you?"
        self.placeholder_text: str = "Type a message..."
        self.bot_name: str = "Assistant"
        self.suggested_questions: list[str] = []
        self.show_sources: bool = True
        self.widget_width: int = 380
        self.widget_height: int = 600

        # API keys state
        self.api_keys: list[dict] = []

        # Embed code state
        self.script_tag: str = ""
        self.iframe_tag: str = ""

        # Controls that update reactively
        self._primary_preview = ft.Container(
            width=32, height=32, bgcolor=self.primary_color, border_radius=6,
            border=ft.Border.all(1, BORDER_COLOR),
        )
        self._bg_preview = ft.Container(
            width=32, height=32, bgcolor=self.widget_bg_color, border_radius=6,
            border=ft.Border.all(1, BORDER_COLOR),
        )
        self._text_preview = ft.Container(
            width=32, height=32, bgcolor=self.widget_text_color, border_radius=6,
            border=ft.Border.all(1, BORDER_COLOR),
        )
        self._questions_column = ft.Column(spacing=8, controls=[])
        self._api_keys_column = ft.Column(spacing=8, controls=[])
        self._script_display = ft.Text(
            "",
            font_family="monospace",
            size=11,
            color="#a8b5c9",
            selectable=True,
        )
        self._iframe_display = ft.Text(
            "",
            font_family="monospace",
            size=11,
            color="#a8b5c9",
            selectable=True,
        )
        self._copy_script_btn = ft.IconButton(
            icon=ft.icons.COPY_OUTLINED,
            tooltip="Copy script tag",
            icon_color=TEXT2,
            on_click=self._copy_script,
        )
        self._copy_iframe_btn = ft.IconButton(
            icon=ft.icons.COPY_OUTLINED,
            tooltip="Copy iframe tag",
            icon_color=TEXT2,
            on_click=self._copy_iframe,
        )
        self._new_key_name_field = text_field("API Key Name", hint="e.g. Production Widget")
        self._position_group = ft.RadioGroup(
            content=ft.Column(
                [
                    ft.Radio(value="bottom-right", label="Bottom Right", fill_color=ACCENT),
                    ft.Radio(value="bottom-left", label="Bottom Left", fill_color=ACCENT),
                    ft.Radio(value="top-right", label="Top Right", fill_color=ACCENT),
                    ft.Radio(value="top-left", label="Top Left", fill_color=ACCENT),
                ],
                spacing=4,
            ),
            value=self.position,
            on_change=self._on_position_change,
        )
        self._show_sources_switch = ft.Switch(
            value=self.show_sources,
            active_color=ACCENT,
            on_change=self._on_sources_change,
        )

    # ─── Event Handlers ───────────────────────────────────────────────────────

    def _on_primary_color_change(self, e: ft.ControlEvent) -> None:
        val = e.control.value.strip()
        if val.startswith("#") and len(val) in (4, 7):
            self.primary_color = val
            self._primary_preview.bgcolor = val
            self._primary_preview.update()

    def _on_bg_color_change(self, e: ft.ControlEvent) -> None:
        val = e.control.value.strip()
        if val.startswith("#") and len(val) in (4, 7):
            self.widget_bg_color = val
            self._bg_preview.bgcolor = val
            self._bg_preview.update()

    def _on_text_color_change(self, e: ft.ControlEvent) -> None:
        val = e.control.value.strip()
        if val.startswith("#") and len(val) in (4, 7):
            self.widget_text_color = val
            self._text_preview.bgcolor = val
            self._text_preview.update()

    def _on_position_change(self, e: ft.ControlEvent) -> None:
        self.position = e.control.value

    def _on_sources_change(self, e: ft.ControlEvent) -> None:
        self.show_sources = e.control.value

    def _on_welcome_change(self, e: ft.ControlEvent) -> None:
        self.welcome_message = e.control.value

    def _on_placeholder_change(self, e: ft.ControlEvent) -> None:
        self.placeholder_text = e.control.value

    def _on_bot_name_change(self, e: ft.ControlEvent) -> None:
        self.bot_name = e.control.value

    def _on_width_change(self, e: ft.ControlEvent) -> None:
        try:
            self.widget_width = int(e.control.value)
        except ValueError:
            pass

    def _on_height_change(self, e: ft.ControlEvent) -> None:
        try:
            self.widget_height = int(e.control.value)
        except ValueError:
            pass

    def _add_question(self, e: ft.ControlEvent) -> None:
        dialog_field = text_field("Suggested Question", hint="e.g. What are your hours?")

        def _confirm(_: ft.ControlEvent) -> None:
            question = dialog_field.value.strip()
            if question:
                self.suggested_questions.append(question)
                self._refresh_questions()
            dlg.open = False
            self.page.update()

        def _cancel(_: ft.ControlEvent) -> None:
            dlg.open = False
            self.page.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Add Suggested Question", color=TEXT, weight=ft.FontWeight.BOLD),
            content=dialog_field,
            bgcolor=SURFACE,
            actions=[
                ft.TextButton("Cancel", on_click=_cancel, style=ft.ButtonStyle(color=TEXT2)),
                ft.ElevatedButton(
                    "Add", on_click=_confirm, bgcolor=ACCENT, color=ft.colors.WHITE,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    def _remove_question(self, question: str) -> None:
        if question in self.suggested_questions:
            self.suggested_questions.remove(question)
            self._refresh_questions()

    def _refresh_questions(self) -> None:
        self._questions_column.controls.clear()
        for q in self.suggested_questions:
            q_copy = q
            self._questions_column.controls.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Icon(ft.icons.CHAT_BUBBLE_OUTLINE, size=16, color=TEXT2),
                            ft.Text(q, size=13, color=TEXT, expand=True),
                            ft.IconButton(
                                icon=ft.icons.CLOSE,
                                icon_size=16,
                                icon_color=ERROR,
                                tooltip="Remove",
                                on_click=lambda _, question=q_copy: self._remove_question(question),
                            ),
                        ],
                        spacing=8,
                    ),
                    bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE),
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    border=ft.Border.all(1, BORDER_COLOR),
                )
            )
        self._questions_column.update()

    async def _generate_embed_code(self, e: ft.ControlEvent) -> None:
        widget_config = {
            "primary_color": self.primary_color,
            "background_color": self.widget_bg_color,
            "text_color": self.widget_text_color,
            "position": self.position,
            "welcome_message": self.welcome_message,
            "placeholder_text": self.placeholder_text,
            "bot_name": self.bot_name,
            "suggested_questions": self.suggested_questions,
            "show_sources": self.show_sources,
            "width": self.widget_width,
            "height": self.widget_height,
        }
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.api_base}/api/v1/projects/{self.project_id}/embed-widget",
                    json=widget_config,
                )
                resp.raise_for_status()
                data = resp.json()
            self.script_tag = data.get("script_tag", "")
            self.iframe_tag = data.get("iframe_tag", "")
            self._script_display.value = self.script_tag
            self._iframe_display.value = self.iframe_tag
            self._script_display.update()
            self._iframe_display.update()
            show_success(self.page, "Embed code generated!")
        except Exception as ex:
            show_error(self.page, f"Failed to generate embed code: {ex}")

    async def _create_api_key(self, e: ft.ControlEvent) -> None:
        name = self._new_key_name_field.value.strip()
        if not name:
            show_error(self.page, "API key name is required.")
            return
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    f"{self.api_base}/api/v1/projects/{self.project_id}/api-keys",
                    json={"name": name, "rate_limit_per_minute": 60, "rate_limit_per_day": 10000},
                )
                resp.raise_for_status()
                key_data = resp.json()

            raw_key = key_data.get("raw_key", "")
            self._show_raw_key_dialog(key_data["name"], raw_key)
            self._new_key_name_field.value = ""
            self._new_key_name_field.update()
            await self._load_api_keys()
        except Exception as ex:
            show_error(self.page, f"Failed to create API key: {ex}")

    def _show_raw_key_dialog(self, name: str, raw_key: str) -> None:
        key_field = ft.TextField(
            value=raw_key,
            read_only=True,
            password=False,
            text_style=ft.TextStyle(color=SUCCESS, font_family="monospace", size=12),
            bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE),
            border_color=BORDER_COLOR,
            border_radius=8,
        )

        def _close(_: ft.ControlEvent) -> None:
            dlg.open = False
            self.page.update()

        async def _copy_key(_: ft.ControlEvent) -> None:
            await self.page.set_clipboard_async(raw_key)
            show_success(self.page, "API key copied to clipboard!")

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text(f'API Key: "{name}"', color=TEXT, weight=ft.FontWeight.BOLD),
            content=ft.Column(
                [
                    ft.Text("Copy this key now — it will not be shown again.", color=WARNING, size=13),
                    ft.Container(height=8),
                    key_field,
                    ft.ElevatedButton(
                        "Copy to Clipboard",
                        icon=ft.icons.COPY,
                        on_click=_copy_key,
                        bgcolor=ACCENT,
                        color=ft.colors.WHITE,
                        width=200,
                    ),
                ],
                spacing=12,
            ),
            bgcolor=SURFACE,
            actions=[ft.TextButton("Done", on_click=_close, style=ft.ButtonStyle(color=TEXT2))],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=12),
        )
        self.page.dialog = dlg
        dlg.open = True
        self.page.update()

    async def _revoke_api_key(self, key_id: str) -> None:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.delete(
                    f"{self.api_base}/api/v1/projects/{self.project_id}/api-keys/{key_id}"
                )
                resp.raise_for_status()
            await self._load_api_keys()
            show_success(self.page, "API key revoked.")
        except Exception as ex:
            show_error(self.page, f"Failed to revoke key: {ex}")

    async def _copy_script(self, e: ft.ControlEvent) -> None:
        if self.script_tag:
            await self.page.set_clipboard_async(self.script_tag)
            show_success(self.page, "Script tag copied!")
        else:
            show_error(self.page, "Generate embed code first.")

    async def _copy_iframe(self, e: ft.ControlEvent) -> None:
        if self.iframe_tag:
            await self.page.set_clipboard_async(self.iframe_tag)
            show_success(self.page, "Iframe tag copied!")
        else:
            show_error(self.page, "Generate embed code first.")

    # ─── Data Loading ─────────────────────────────────────────────────────────

    async def _load_api_keys(self) -> None:
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self.api_base}/api/v1/projects/{self.project_id}/api-keys"
                )
                resp.raise_for_status()
                self.api_keys = resp.json()
            self._render_api_keys()
        except Exception:
            self.api_keys = []

    def _render_api_keys(self) -> None:
        self._api_keys_column.controls.clear()
        if not self.api_keys:
            self._api_keys_column.controls.append(
                ft.Text("No API keys yet. Create one below.", size=13, color=TEXT2)
            )
        else:
            for key in self.api_keys:
                key_id = key["id"]
                self._api_keys_column.controls.append(
                    ft.Container(
                        content=ft.Row(
                            [
                                ft.Icon(ft.icons.KEY_OUTLINED, size=18, color=ACCENT),
                                ft.Column(
                                    [
                                        ft.Text(key["name"], size=14, weight=ft.FontWeight.W_500, color=TEXT),
                                        ft.Text(
                                            f"{key.get('key_prefix', '')}••••••••  ·  "
                                            f"{key.get('total_requests', 0)} requests",
                                            size=12,
                                            color=TEXT2,
                                        ),
                                    ],
                                    spacing=2,
                                    expand=True,
                                ),
                                ft.Container(
                                    content=ft.Text(
                                        "ACTIVE" if key.get("is_active") else "REVOKED",
                                        size=11,
                                        weight=ft.FontWeight.W_600,
                                        color=SUCCESS if key.get("is_active") else ERROR,
                                    ),
                                    bgcolor=ft.colors.with_opacity(
                                        0.12,
                                        SUCCESS if key.get("is_active") else ERROR,
                                    ),
                                    border_radius=10,
                                    padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                                ),
                                ft.IconButton(
                                    icon=ft.icons.DELETE_OUTLINE,
                                    icon_color=ERROR,
                                    tooltip="Revoke key",
                                    on_click=lambda _, kid=key_id: self.page.run_task(
                                        self._revoke_api_key, kid
                                    ),
                                ),
                            ],
                            spacing=12,
                        ),
                        bgcolor=ft.colors.with_opacity(0.04, ft.colors.WHITE),
                        border_radius=10,
                        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
                        border=ft.Border.all(1, BORDER_COLOR),
                    )
                )
        self._api_keys_column.update()

    # ─── Section Builders ─────────────────────────────────────────────────────

    def _build_color_section(self) -> ft.Control:
        primary_field = text_field("Primary Color (hex)", value=self.primary_color, on_change=self._on_primary_color_change, width=180)
        bg_field = text_field("Background Color (hex)", value=self.widget_bg_color, on_change=self._on_bg_color_change, width=180)
        text_field_ctrl = text_field("Text Color (hex)", value=self.widget_text_color, on_change=self._on_text_color_change, width=180)

        return card(
            ft.Column(
                [
                    section_header("Colors"),
                    ft.Container(height=4),
                    ft.Row([primary_field, ft.Container(width=8), self._primary_preview], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Row([bg_field, ft.Container(width=8), self._bg_preview], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                    ft.Row([text_field_ctrl, ft.Container(width=8), self._text_preview], vertical_alignment=ft.CrossAxisAlignment.CENTER),
                ],
                spacing=16,
            ),
            padding=20,
        )

    def _build_position_section(self) -> ft.Control:
        return card(
            ft.Column(
                [
                    section_header("Widget Position"),
                    ft.Container(height=4),
                    self._position_group,
                ],
                spacing=12,
            ),
            padding=20,
        )

    def _build_messages_section(self) -> ft.Control:
        return card(
            ft.Column(
                [
                    section_header("Messages & Labels"),
                    ft.Container(height=4),
                    text_field("Bot Name", value=self.bot_name, on_change=self._on_bot_name_change),
                    text_field("Welcome Message", value=self.welcome_message, on_change=self._on_welcome_change, multiline=True, min_lines=2, max_lines=4),
                    text_field("Input Placeholder", value=self.placeholder_text, on_change=self._on_placeholder_change),
                    ft.Row(
                        [
                            ft.Text("Show Sources", size=14, color=TEXT),
                            self._show_sources_switch,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                ],
                spacing=14,
            ),
            padding=20,
        )

    def _build_dimensions_section(self) -> ft.Control:
        return card(
            ft.Column(
                [
                    section_header("Dimensions"),
                    ft.Container(height=4),
                    ft.Row(
                        [
                            text_field("Width (px)", value=str(self.widget_width), on_change=self._on_width_change, width=140),
                            ft.Container(width=16),
                            text_field("Height (px)", value=str(self.widget_height), on_change=self._on_height_change, width=140),
                        ],
                    ),
                ],
                spacing=12,
            ),
            padding=20,
        )

    def _build_questions_section(self) -> ft.Control:
        return card(
            ft.Column(
                [
                    section_header(
                        "Suggested Questions",
                        trailing=ft.IconButton(
                            icon=ft.icons.ADD_CIRCLE_OUTLINE,
                            icon_color=ACCENT,
                            tooltip="Add question",
                            on_click=self._add_question,
                        ),
                    ),
                    ft.Container(height=4),
                    ft.Text("Questions shown as quick reply chips in the widget.", size=12, color=TEXT2),
                    self._questions_column,
                ],
                spacing=12,
            ),
            padding=20,
        )

    def _build_api_keys_section(self) -> ft.Control:
        return card(
            ft.Column(
                [
                    section_header("API Keys"),
                    ft.Container(height=4),
                    ft.Text(
                        "API keys authenticate embed widget requests. Keep them secret.",
                        size=12,
                        color=TEXT2,
                    ),
                    self._api_keys_column,
                    divider(),
                    ft.Row(
                        [
                            ft.Container(content=self._new_key_name_field, expand=True),
                            ft.Container(width=12),
                            primary_button(
                                "Generate Key",
                                on_click=lambda e: self.page.run_task(self._create_api_key, e),
                                icon=ft.icons.KEY,
                            ),
                        ],
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                ],
                spacing=14,
            ),
            padding=20,
        )

    def _build_embed_code_section(self) -> ft.Control:
        return card(
            ft.Column(
                [
                    section_header(
                        "Embed Code",
                        trailing=primary_button(
                            "Generate",
                            on_click=lambda e: self.page.run_task(self._generate_embed_code, e),
                            icon=ft.icons.CODE,
                        ),
                    ),
                    ft.Container(height=4),
                    ft.Text(
                        "Paste one of these snippets into your website's HTML.",
                        size=12,
                        color=TEXT2,
                    ),
                    ft.Container(height=8),
                    ft.Row(
                        [
                            ft.Text("Script Tag", size=13, weight=ft.FontWeight.W_600, color=TEXT, expand=True),
                            self._copy_script_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(
                        content=ft.Column(
                            [self._script_display],
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        bgcolor="#0d1117",
                        border_radius=8,
                        padding=14,
                        border=ft.Border.all(1, BORDER_COLOR),
                        height=80,
                    ),
                    ft.Container(height=8),
                    ft.Row(
                        [
                            ft.Text("iFrame Tag", size=13, weight=ft.FontWeight.W_600, color=TEXT, expand=True),
                            self._copy_iframe_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    ft.Container(
                        content=ft.Column(
                            [self._iframe_display],
                            scroll=ft.ScrollMode.AUTO,
                        ),
                        bgcolor="#0d1117",
                        border_radius=8,
                        padding=14,
                        border=ft.Border.all(1, BORDER_COLOR),
                        height=80,
                    ),
                ],
                spacing=12,
            ),
            padding=20,
        )

    # ─── Public Build ─────────────────────────────────────────────────────────

    def build(self) -> ft.Control:
        self.page.run_task(self._load_api_keys)

        left_col = ft.Column(
            [
                self._build_color_section(),
                self._build_position_section(),
                self._build_messages_section(),
                self._build_dimensions_section(),
                self._build_questions_section(),
            ],
            spacing=16,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

        right_col = ft.Column(
            [
                self._build_api_keys_section(),
                self._build_embed_code_section(),
            ],
            spacing=16,
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

        return ft.Column(
            [
                ft.Container(
                    content=ft.Row(
                        [
                            ft.IconButton(
                                icon=ft.icons.ARROW_BACK,
                                icon_color=TEXT2,
                                tooltip="Back to project",
                                on_click=lambda _: self.navigate("/project", self.project_id),
                            ),
                            ft.Container(width=4),
                            ft.Column(
                                [
                                    title("Widget Customization", size=22),
                                    ft.Text(
                                        "Configure your embeddable chatbot widget",
                                        size=13,
                                        color=TEXT2,
                                    ),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                        ],
                        spacing=8,
                    ),
                    padding=ft.Padding.only(bottom=16),
                ),
                ft.Row(
                    [
                        ft.Container(content=left_col, expand=True),
                        ft.Container(width=20),
                        ft.Container(content=right_col, expand=True),
                    ],
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
            ],
            spacing=0,
            expand=True,
        )
