"""Shared UI widgets: cards, dialogs, toasts, loading states.
Premium design system — classic, chic, polished dark theme.
Glassmorphism, subtle shadows, refined typography, smooth micro-interactions.
"""

from typing import Any, Callable, Optional

import flet as ft

# ─── Design Tokens ────────────────────────────────────────────────────────────
# Classic premium dark palette — restrained, sophisticated, high-end

BG = "#0a0b0f"
SURFACE = "#12141a"
CARD = "#1a1d27"
CARD_HOVER = "#1f2230"

# Accent — refined blue that stays professional
ACCENT = "#4f8cff"
ACCENT2 = "#7c5cfc"
ACCENT3 = "#a855f7"

SUCCESS = "#34d399"
WARNING = "#fbbf24"
ERROR = "#ef4444"

TEXT = "#f1f5f9"
TEXT2 = "#94a3b8"
TEXT3 = "#64748b"

# Borders — ultra-subtle
BORDER = "rgba(255,255,255,0.06)"
BORDER_LIGHT = "rgba(255,255,255,0.10)"
BORDER_COLOR = ft.Colors.with_opacity(0.06, ft.Colors.WHITE)

# Glass
GLASS_BG = "rgba(18,20,26,0.85)"
GLASS_BORDER = "rgba(255,255,255,0.08)"


# ─── Typography ───────────────────────────────────────────────────────────────

class T:
    """Typography shortcuts — consistent text styling."""
    @staticmethod
    def h1(text: str) -> ft.Text:
        return ft.Text(text, size=26, weight=ft.FontWeight.BOLD, color=TEXT)

    @staticmethod
    def h2(text: str) -> ft.Text:
        return ft.Text(text, size=20, weight=ft.FontWeight.W_600, color=TEXT)

    @staticmethod
    def h3(text: str) -> ft.Text:
        return ft.Text(text, size=16, weight=ft.FontWeight.W_600, color=TEXT)

    @staticmethod
    def body(text: str, color: str = TEXT, size: int = 14) -> ft.Text:
        return ft.Text(text, size=size, color=color)

    @staticmethod
    def muted(text: str, size: int = 12) -> ft.Text:
        return ft.Text(text, size=size, color=TEXT2)

    @staticmethod
    def caption(text: str) -> ft.Text:
        return ft.Text(text, size=11, color=TEXT3)

    @staticmethod
    def overline(text: str) -> ft.Text:
        return ft.Text(text.upper(), size=9, weight=ft.FontWeight.W_700, color=TEXT3)


def title(text: str, size: int = 24) -> ft.Text:
    return ft.Text(text, size=size, weight=ft.FontWeight.BOLD, color=TEXT)


def subtitle(text: str, size: int = 16) -> ft.Text:
    return ft.Text(text, size=size, color=TEXT2)


def label(text: str) -> ft.Text:
    return ft.Text(text, size=13, color=TEXT2)


def body(text: str, size: int = 14) -> ft.Text:
    return ft.Text(text, size=size, color=TEXT)


def caption(text: str) -> ft.Text:
    return ft.Text(text, size=11, color=TEXT3, italic=True)


# ─── Gradient Text ────────────────────────────────────────────────────────────

def gradient_text(text: str, size: int = 28, weight=ft.FontWeight.BOLD) -> ft.Text:
    return ft.Text(
        text,
        size=size,
        weight=weight,
        color=TEXT,
    )


# ─── Status Badge ─────────────────────────────────────────────────────────────

_STATUS_COLORS = {
    "completed": SUCCESS,
    "processing": ACCENT,
    "pending": WARNING,
    "failed": ERROR,
}


def status_badge(status: str) -> ft.Container:
    color = _STATUS_COLORS.get(status, TEXT2)
    return ft.Container(
        content=ft.Row(
            [
                ft.Container(
                    width=6, height=6,
                    border_radius=3,
                    bgcolor=color,
                ),
                ft.Text(status.upper(), size=10, weight=ft.FontWeight.W_600, color=color),
            ],
            spacing=4,
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        bgcolor=ft.Colors.with_opacity(0.12, color),
        border_radius=6,
        padding=ft.Padding.symmetric(horizontal=8, vertical=3),
    )


# ─── Glass Card ───────────────────────────────────────────────────────────────

def glass_card(
    content: ft.Control,
    padding: int = 20,
    on_click: Optional[Callable] = None,
    width: Optional[float] = None,
    height: Optional[float] = None,
    expand: bool = False,
    blur: bool = True,
) -> ft.Container:
    """Frosted glass card — subtle border, soft shadow, refined radius."""
    return ft.Container(
        content=content,
        bgcolor=GLASS_BG if blur else CARD,
        border_radius=14,
        padding=padding,
        on_click=on_click,
        width=width,
        height=height,
        expand=expand,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.WHITE)),
        ink=True if on_click else False,
        animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
        shadow=ft.BoxShadow(
            blur_radius=20,
            color="rgba(0,0,0,0.3)",
            offset=ft.Offset(0, 4),
        ),
    )


# ─── Card ─────────────────────────────────────────────────────────────────────

def card(
    content: ft.Control,
    padding: int = 20,
    bgcolor: str = CARD,
    border_radius: int = 12,
    on_click: Optional[Callable] = None,
    width: Optional[float] = None,
    height: Optional[float] = None,
    expand: bool = False,
) -> ft.Container:
    return ft.Container(
        content=content,
        bgcolor=bgcolor,
        border_radius=border_radius,
        padding=padding,
        on_click=on_click,
        width=width,
        height=height,
        expand=expand,
        border=ft.Border.all(1, BORDER_COLOR),
        animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT) if on_click else None,
    )


def card_hover(
    content: ft.Control,
    on_click: Callable,
    padding: int = 20,
    width: Optional[float] = None,
    height: Optional[float] = None,
) -> ft.Container:
    c = card(content, padding=padding, on_click=on_click, width=width, height=height)
    c.ink = True
    return c


# ─── Button Styles ────────────────────────────────────────────────────────────

def _btn_style(radius: int = 10, elevation: int = 2, overlay: Optional[str] = None) -> ft.ButtonStyle:
    return ft.ButtonStyle(
        shape=ft.RoundedRectangleBorder(radius=radius),
        overlay_color=overlay or ft.Colors.with_opacity(0.10, ft.Colors.WHITE),
        elevation=elevation,
        animation_duration=150,
    )


def primary_button(text: str, on_click: Callable, icon: Optional[str] = None, width: Optional[float] = None) -> ft.ElevatedButton:
    return ft.ElevatedButton(
        content=ft.Row(
            [ft.Text(text, size=13, weight=ft.FontWeight.W_500)],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        icon=icon,
        on_click=on_click,
        bgcolor=ACCENT,
        color=ft.Colors.WHITE,
        width=width,
        style=_btn_style(elevation=3),
    )


def secondary_button(text: str, on_click: Callable, icon: Optional[str] = None) -> ft.OutlinedButton:
    return ft.OutlinedButton(
        content=ft.Row(
            [ft.Text(text, size=13, weight=ft.FontWeight.W_500)],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        icon=icon,
        on_click=on_click,
        style=ft.ButtonStyle(
            color=TEXT,
            side=ft.BorderSide(1, ft.Colors.with_opacity(0.2, ft.Colors.WHITE)),
            shape=ft.RoundedRectangleBorder(radius=10),
            overlay_color=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
            animation_duration=150,
        ),
    )


def danger_button(text: str, on_click: Callable, icon: Optional[str] = None) -> ft.ElevatedButton:
    return ft.ElevatedButton(
        content=ft.Row(
            [ft.Text(text, size=13, weight=ft.FontWeight.W_500)],
            alignment=ft.MainAxisAlignment.CENTER,
        ),
        icon=icon,
        on_click=on_click,
        bgcolor=ERROR,
        color=ft.Colors.WHITE,
        style=_btn_style(elevation=2),
    )


def icon_button(icon: str, on_click: Callable, tooltip: str = "", color: str = TEXT2) -> ft.IconButton:
    return ft.IconButton(
        icon=icon,
        on_click=on_click,
        tooltip=tooltip,
        icon_color=color,
        style=ft.ButtonStyle(
            overlay_color=ft.Colors.with_opacity(0.08, ft.Colors.WHITE),
            animation_duration=100,
        ),
    )


def ghost_button(text: str, on_click: Callable, icon: Optional[str] = None) -> ft.TextButton:
    """Subtle text-only button for secondary actions."""
    return ft.TextButton(
        text,
        icon=icon,
        on_click=on_click,
        style=ft.ButtonStyle(
            color=TEXT2,
            overlay_color=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
            animation_duration=100,
        ),
    )


# ─── Input Fields ─────────────────────────────────────────────────────────────

def text_field(
    label_text: str,
    value: str = "",
    on_change: Optional[Callable] = None,
    password: bool = False,
    multiline: bool = False,
    min_lines: int = 1,
    max_lines: Optional[int] = None,
    hint: str = "",
    expand: bool = False,
    width: Optional[float] = None,
) -> ft.TextField:
    return ft.TextField(
        label=label_text,
        value=value,
        on_change=on_change,
        password=password,
        can_reveal_password=password,
        multiline=multiline,
        min_lines=min_lines,
        max_lines=max_lines if max_lines else (10 if multiline else 1),
        hint_text=hint,
        expand=expand,
        width=width,
        label_style=ft.TextStyle(color=TEXT3, size=11),
        text_style=ft.TextStyle(color=TEXT, size=14),
        border_color=ft.Colors.with_opacity(0.12, ft.Colors.WHITE),
        focused_border_color=ACCENT,
        cursor_color=ACCENT,
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
        border_radius=10,
        focused_bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.WHITE),
    )


def dropdown(
    label_text: str,
    options: list[tuple[str, str]],
    value: Optional[str] = None,
    on_change: Optional[Callable] = None,
    width: Optional[float] = None,
) -> ft.Dropdown:
    return ft.Dropdown(
        label=label_text,
        value=value,
        options=[ft.dropdown.Option(key=k, text=v) for k, v in options],
        on_change=on_change,
        width=width,
        label_style=ft.TextStyle(color=TEXT3, size=11),
        text_style=ft.TextStyle(color=TEXT, size=14),
        border_color=ft.Colors.with_opacity(0.12, ft.Colors.WHITE),
        focused_border_color=ACCENT,
        bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
        border_radius=10,
    )


# ─── Loading States ───────────────────────────────────────────────────────────

def loading_spinner(message: str = "Loading...") -> ft.Column:
    return ft.Column(
        [
            ft.ProgressRing(color=ACCENT, stroke_width=3, width=24, height=24),
            ft.Text(message, color=TEXT2, size=13),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10,
    )


def progress_bar(value: Optional[float] = None, color: str = ACCENT) -> ft.ProgressBar:
    return ft.ProgressBar(
        value=value,
        color=color,
        bgcolor=ft.Colors.with_opacity(0.08, color),
        height=4,
        border_radius=2,
    )


# ─── Toast Snackbar ───────────────────────────────────────────────────────────

def toast(message: str, color: str = SUCCESS) -> ft.SnackBar:
    return ft.SnackBar(
        content=ft.Row(
            [
                ft.Container(
                    width=8, height=8,
                    border_radius=4,
                    bgcolor=ft.Colors.WHITE,
                ),
                ft.Text(message, color=ft.Colors.WHITE, size=13),
            ],
            spacing=8,
        ),
        bgcolor=color,
        duration=3000,
        behavior=ft.SnackBarBehavior.FLOATING,
        shape=ft.RoundedRectangleBorder(radius=10),
    )


def show_toast(page: ft.Page, message: str, color: str = SUCCESS) -> None:
    page.show_dialog(toast(message, color))


def show_error(page: ft.Page, message: str) -> None:
    show_toast(page, message, ERROR)


def show_success(page: ft.Page, message: str) -> None:
    show_toast(page, message, SUCCESS)


# ─── Confirm Dialog ───────────────────────────────────────────────────────────

def confirm_dialog(
    page: ft.Page,
    title_text: str,
    body_text: str,
    on_confirm: Callable,
    confirm_label: str = "Delete",
    confirm_color: str = ERROR,
) -> None:
    def _close(_):
        page.pop_dialog()

    def _confirm(_):
        page.pop_dialog()
        on_confirm()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text(title_text, color=TEXT, weight=ft.FontWeight.BOLD, size=18),
        content=ft.Text(body_text, color=TEXT2, size=14),
        bgcolor=SURFACE,
        actions=[
            ft.TextButton(
                "Cancel",
                on_click=_close,
                style=ft.ButtonStyle(color=TEXT2),
            ),
            ft.ElevatedButton(
                confirm_label,
                on_click=_confirm,
                bgcolor=confirm_color,
                color=ft.Colors.WHITE,
                style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=10)),
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
        shape=ft.RoundedRectangleBorder(radius=16),
    )
    page.show_dialog(dlg)


# ─── Section Header ───────────────────────────────────────────────────────────

def section_header(text: str, trailing: Optional[ft.Control] = None) -> ft.Row:
    children: list[ft.Control] = [
        ft.Text(text, size=18, weight=ft.FontWeight.BOLD, color=TEXT, expand=True),
    ]
    if trailing:
        children.append(trailing)
    return ft.Row(children, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)


# ─── Stat Card ────────────────────────────────────────────────────────────────

def stat_card(label_text: str, value: str, icon: str, color: str = ACCENT) -> ft.Container:
    return glass_card(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(icon, color=color, size=18),
                            bgcolor=ft.Colors.with_opacity(0.12, color),
                            border_radius=8,
                            padding=ft.Padding.symmetric(horizontal=8, vertical=8),
                        ),
                        ft.Container(expand=True),
                        ft.Text(value, size=24, weight=ft.FontWeight.BOLD, color=TEXT),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                ),
                ft.Container(height=4),
                ft.Text(label_text, size=12, color=TEXT2),
            ],
            spacing=2,
        ),
        padding=16,
    )


# ─── Divider ─────────────────────────────────────────────────────────────────

def divider() -> ft.Divider:
    return ft.Divider(color=ft.Colors.with_opacity(0.06, ft.Colors.WHITE), height=1)


# ─── Card Surface ─────────────────────────────────────────────────────────────

def card_surface(
    content: ft.Control,
    padding: int = 20,
    on_click: Optional[Callable] = None,
    width: Optional[float] = None,
    height: Optional[float] = None,
    expand: bool = False,
) -> ft.Container:
    return glass_card(content, padding=padding, on_click=on_click, width=width, height=height, expand=expand)


# ─── Info Row (label: value) ──────────────────────────────────────────────────

def info_row(label_text: str, value_text: str, value_color: str = TEXT) -> ft.Row:
    return ft.Row(
        [
            ft.Text(label_text, size=13, color=TEXT2, expand=True),
            ft.Text(value_text, size=13, weight=ft.FontWeight.W_500, color=value_color),
        ],
        spacing=8,
    )


# ─── Empty State ─────────────────────────────────────────────────────────────

def empty_state(icon: str, title_text: str, subtitle_text: str = "", action: Optional[ft.Control] = None) -> ft.Column:
    children: list[ft.Control] = [
        ft.Container(
            content=ft.Icon(icon, size=48, color=TEXT3),
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
            border_radius=16,
            padding=16,
        ),
        ft.Text(title_text, size=16, weight=ft.FontWeight.W_600, color=TEXT),
    ]
    if subtitle_text:
        children.append(ft.Text(subtitle_text, size=13, color=TEXT2, text_align=ft.TextAlign.CENTER))
    if action:
        children.append(ft.Container(content=action, margin=ft.Margin(left=0, right=0, top=8, bottom=0)))

    return ft.Column(
        children,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=10,
    )


# ─── Code Block ──────────────────────────────────────────────────────────────

def code_block(code: str, max_height: float = 300) -> ft.Container:
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(
                    code,
                    font_family="monospace",
                    size=12,
                    color="#a8b5c9",
                    selectable=True,
                ),
            ],
            scroll=ft.ScrollMode.AUTO,
        ),
        bgcolor="#0d1117",
        border_radius=10,
        padding=16,
        border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.WHITE)),
        height=max_height,
    )
