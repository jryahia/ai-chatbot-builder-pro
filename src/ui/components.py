"""Shared UI widgets: cards, dialogs, toasts, loading states."""

from typing import Any, Callable, Optional

import flet as ft

# ─── Design Tokens ────────────────────────────────────────────────────────────

BG = "#0f1117"
SURFACE = "#1a1d27"
CARD = "#222733"
ACCENT = "#4f8cff"
ACCENT2 = "#7c5cfc"
SUCCESS = "#34d399"
WARNING = "#fbbf24"
ERROR = "#ef4444"
TEXT = "#f1f5f9"
TEXT2 = "#94a3b8"
BORDER = "rgba(255,255,255,0.08)"
BORDER_COLOR = ft.colors.with_opacity(0.08, ft.colors.WHITE)


# ─── Typography ───────────────────────────────────────────────────────────────

def title(text: str, size: int = 24) -> ft.Text:
    return ft.Text(text, size=size, weight=ft.FontWeight.BOLD, color=TEXT)


def subtitle(text: str, size: int = 16) -> ft.Text:
    return ft.Text(text, size=size, color=TEXT2)


def label(text: str) -> ft.Text:
    return ft.Text(text, size=13, color=TEXT2)


def body(text: str, size: int = 14) -> ft.Text:
    return ft.Text(text, size=size, color=TEXT)


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
        content=ft.Text(status.upper(), size=11, weight=ft.FontWeight.W_600, color=color),
        bgcolor=ft.colors.with_opacity(0.15, color),
        border_radius=12,
        padding=ft.Padding.symmetric(horizontal=10, vertical=4),
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
        animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_IN_OUT) if on_click else None,
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

def primary_button(text: str, on_click: Callable, icon: Optional[str] = None, width: Optional[float] = None) -> ft.ElevatedButton:
    return ft.ElevatedButton(
        text=text,
        icon=icon,
        on_click=on_click,
        bgcolor=ACCENT,
        color=ft.colors.WHITE,
        width=width,
        style=ft.ButtonStyle(
            shape=ft.RoundedRectangleBorder(radius=8),
            overlay_color=ft.colors.with_opacity(0.1, ft.colors.WHITE),
        ),
    )


def secondary_button(text: str, on_click: Callable, icon: Optional[str] = None) -> ft.OutlinedButton:
    return ft.OutlinedButton(
        text=text,
        icon=icon,
        on_click=on_click,
        style=ft.ButtonStyle(
            color=TEXT,
            side=ft.BorderSide(1, ACCENT),
            shape=ft.RoundedRectangleBorder(radius=8),
        ),
    )


def danger_button(text: str, on_click: Callable, icon: Optional[str] = None) -> ft.ElevatedButton:
    return ft.ElevatedButton(
        text=text,
        icon=icon,
        on_click=on_click,
        bgcolor=ERROR,
        color=ft.colors.WHITE,
        style=ft.ButtonStyle(shape=ft.RoundedRectangleBorder(radius=8)),
    )


def icon_button(icon: str, on_click: Callable, tooltip: str = "", color: str = TEXT2) -> ft.IconButton:
    return ft.IconButton(icon=icon, on_click=on_click, tooltip=tooltip, icon_color=color)


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
        label_style=ft.TextStyle(color=TEXT2),
        text_style=ft.TextStyle(color=TEXT),
        border_color=BORDER_COLOR,
        focused_border_color=ACCENT,
        cursor_color=ACCENT,
        bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE),
        border_radius=8,
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
        label_style=ft.TextStyle(color=TEXT2),
        text_style=ft.TextStyle(color=TEXT),
        border_color=BORDER_COLOR,
        focused_border_color=ACCENT,
        bgcolor=ft.colors.with_opacity(0.05, ft.colors.WHITE),
        border_radius=8,
    )


# ─── Loading States ───────────────────────────────────────────────────────────

def loading_spinner(message: str = "Loading...") -> ft.Column:
    return ft.Column(
        [
            ft.ProgressRing(color=ACCENT, stroke_width=3),
            ft.Text(message, color=TEXT2, size=14),
        ],
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=12,
    )


def progress_bar(value: Optional[float] = None, color: str = ACCENT) -> ft.ProgressBar:
    return ft.ProgressBar(
        value=value,
        color=color,
        bgcolor=ft.colors.with_opacity(0.1, color),
        height=6,
        border_radius=3,
    )


# ─── Toast Snackbar ───────────────────────────────────────────────────────────

def show_toast(page: ft.Page, message: str, color: str = SUCCESS) -> None:
    page.snack_bar = ft.SnackBar(
        content=ft.Text(message, color=ft.colors.WHITE),
        bgcolor=color,
        duration=3000,
    )
    page.snack_bar.open = True
    page.update()


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
        dlg.open = False
        page.update()

    def _confirm(_):
        dlg.open = False
        page.update()
        on_confirm()

    dlg = ft.AlertDialog(
        modal=True,
        title=ft.Text(title_text, color=TEXT, weight=ft.FontWeight.BOLD),
        content=ft.Text(body_text, color=TEXT2),
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
                color=ft.colors.WHITE,
            ),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
        shape=ft.RoundedRectangleBorder(radius=12),
    )
    page.dialog = dlg
    dlg.open = True
    page.update()


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
    return card(
        ft.Column(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Icon(icon, color=color, size=20),
                            bgcolor=ft.colors.with_opacity(0.15, color),
                            border_radius=8,
                            padding=8,
                        ),
                    ]
                ),
                ft.Text(value, size=28, weight=ft.FontWeight.BOLD, color=TEXT),
                ft.Text(label_text, size=13, color=TEXT2),
            ],
            spacing=8,
        ),
        padding=16,
    )


# ─── Divider ─────────────────────────────────────────────────────────────────

def divider() -> ft.Divider:
    return ft.Divider(color=BORDER_COLOR, height=1)


# ─── Empty State ─────────────────────────────────────────────────────────────

def empty_state(icon: str, title_text: str, subtitle_text: str = "", action: Optional[ft.Control] = None) -> ft.Column:
    children: list[ft.Control] = [
        ft.Icon(icon, size=56, color=TEXT2),
        ft.Text(title_text, size=18, weight=ft.FontWeight.W_600, color=TEXT),
    ]
    if subtitle_text:
        children.append(ft.Text(subtitle_text, size=14, color=TEXT2, text_align=ft.TextAlign.CENTER))
    if action:
        children.append(ft.Container(content=action, margin=ft.margin.only(top=8)))

    return ft.Column(
        children,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        spacing=12,
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
        border_radius=8,
        padding=16,
        border=ft.Border.all(1, BORDER_COLOR),
        height=max_height,
    )
