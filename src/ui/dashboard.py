"""Project dashboard view for the AI Chatbot Builder Pro.
Classic chic design — refined grid, premium cards, smooth interactions.
"""

import flet as ft
import structlog
from typing import Callable, Optional
import asyncio
import time

logger = structlog.get_logger(__name__)

# Connection-only retry budget for calls made while the background API server is
# still binding its socket. Worst case adds ~1s before giving up.
_STARTUP_RETRIES = 3
_STARTUP_RETRY_DELAY = 0.5


def _fire(coro):
    """Fire-and-forget an async coroutine, returning None for Flet event handlers."""
    asyncio.ensure_future(coro)

from src.ui.components import (
    ACCENT, ACCENT2, ACCENT3, BG, CARD, SURFACE, TEXT, TEXT2, TEXT3,
    BORDER_COLOR, GLASS_BG, SUCCESS,
    glass_card, primary_button, divider, empty_state, toast,
    section_header, gradient_text,
)


class DashboardView(ft.Container):
    """Dashboard showing project grid with creation dialog — refined, classic."""

    def __init__(self, page: ft.Page, api_base: str = ""):
        super().__init__()
        self._page = page
        self.api_base = api_base
        self.on_navigate = None
        self.projects = []
        self.loading = ft.ProgressRing(visible=False, width=18, height=18, stroke_width=2, color=ACCENT)

        # ─── Create Dialog Fields ─────────────────────────────────────────────
        shared_input_style = dict(
            border_color=ft.Colors.with_opacity(0.12, ft.Colors.WHITE),
            color=TEXT,
            label_style=ft.TextStyle(color=TEXT3, size=11),
            text_style=ft.TextStyle(color=TEXT, size=14),
            focused_border_color=ACCENT,
            cursor_color=ACCENT,
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
            border_radius=10,
            focused_bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.WHITE),
        )

        self.project_name = ft.TextField(
            label="Project Name",
            hint_text="e.g. Customer Support Bot",
            **shared_input_style,
        )
        self.project_desc = ft.TextField(
            label="Description",
            hint_text="What will this chatbot do?",
            multiline=True,
            min_lines=2,
            max_lines=4,
            **shared_input_style,
        )
        self.system_prompt = ft.TextField(
            label="System Prompt",
            hint_text="You are a helpful assistant that answers questions based on the provided documents...",
            multiline=True,
            min_lines=3,
            max_lines=6,
            **shared_input_style,
        )

        # ─── Create Dialog ────────────────────────────────────────────────────
        self.create_dialog = ft.AlertDialog(
            title=ft.Text("Create New Project", color=TEXT, size=18, weight=ft.FontWeight.BOLD),
            bgcolor=SURFACE,
            content=ft.Container(
                width=500,
                padding=ft.Padding.symmetric(horizontal=28, vertical=12),
                content=ft.Column(
                    spacing=16,
                    controls=[self.project_name, self.project_desc, self.system_prompt],
                ),
            ),
            actions=[
                ft.TextButton(
                    "Cancel",
                    on_click=self._close_dialog,
                    style=ft.ButtonStyle(color=TEXT2),
                ),
                ft.FilledButton(
                    "Create Project",
                    style=ft.ButtonStyle(
                        bgcolor=ACCENT,
                        color=ft.Colors.WHITE,
                        shape=ft.RoundedRectangleBorder(radius=10),
                    ),
                    on_click=self._create_project,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            shape=ft.RoundedRectangleBorder(radius=16),
        )

        # ─── Project Grid ─────────────────────────────────────────────────────
        self.project_grid = ft.GridView(
            runs_count=3,
            max_extent=340,
            spacing=16,
            run_spacing=16,
            padding=0,
        )

    def api_client(self, path: str, method: str = "GET", **kwargs) -> any:
        import httpx
        if path.startswith("/api/") and not path.startswith("/api/v1/"):
            path = path.replace("/api/", "/api/v1/", 1)
        url = f"{self.api_base}{path}"

        # The API server starts in a background thread, so the first calls made
        # right after launch can hit a socket that is not listening yet. Retry
        # only on connection failures — an HTTP status (404, 500, ...) is a real
        # answer from a live server and must not be retried.
        for attempt in range(_STARTUP_RETRIES):
            try:
                if method == "GET":
                    r = httpx.get(url, timeout=10)
                elif method == "POST":
                    r = httpx.post(url, json=kwargs.get("json"), timeout=10)
                elif method == "DELETE":
                    r = httpx.delete(url, timeout=10)
                elif method == "PUT":
                    r = httpx.put(url, json=kwargs.get("json"), timeout=10)
                else:
                    return None
                r.raise_for_status()
                return r.json()
            except (httpx.ConnectError, httpx.ConnectTimeout):
                if attempt == _STARTUP_RETRIES - 1:
                    return None
                time.sleep(_STARTUP_RETRY_DELAY)
            except Exception:
                return None
        return None

    def navigate(self, route: str, project_id: Optional[str] = None) -> None:
        if self.on_navigate:
            self.on_navigate(route, project_id)

    def render(self):
        """Return the dashboard container for rendering."""
        self.content = ft.Container(
            padding=ft.Padding.symmetric(horizontal=28, vertical=20),
            content=ft.Column(
                spacing=20,
                controls=[

                    # Header section — refined spacing
                    ft.Container(
                        content=ft.Row(
                            controls=[
                                ft.Column(
                                    spacing=4,
                                    controls=[
                                        ft.Text("AI Chatbot Builder", size=26, weight=ft.FontWeight.BOLD, color=TEXT),
                                        ft.Text("Create and manage AI chatbots trained on your documents.", size=14, color=TEXT2),
                                    ],
                                    expand=True,
                                ),
                                ft.Container(
                                    content=ft.Row(
                                        controls=[
                                            self.loading,
                                            ft.FilledButton(
                                                "New Project",
                                                icon=ft.Icons.ADD,
                                                style=ft.ButtonStyle(
                                                    color=ft.Colors.WHITE,
                                                    bgcolor=ACCENT,
                                                    shape=ft.RoundedRectangleBorder(radius=10),
                                                    elevation=2,
                                                ),
                                                on_click=self._open_create_dialog,
                                            ),
                                        ],
                                        spacing=10,
                                    ),
                                ),
                            ],
                        ),
                    ),

                    divider(),

                    # Project grid
                    self.project_grid,
                ],
                expand=True,
            ),
        )
        return self

    def load_projects(self):
        self.loading.visible = True
        self.update()
        try:
            result = self.api_client("/api/projects")
            self.projects = result if isinstance(result, list) else []
        except Exception:
            self.projects = []
        self.loading.visible = False
        self._render_grid()
        self.update()

    def _render_grid(self):
        self.project_grid.controls.clear()
        if not self.projects:
            self.project_grid.controls.append(
                ft.Container(
                    content=empty_state(
                        ft.Icons.SMART_TOY_OUTLINED,
                        "No projects yet",
                        "Create your first AI chatbot to get started.",
                        action=ft.FilledButton(
                            "Create Project",
                            icon=ft.Icons.ADD,
                            style=ft.ButtonStyle(
                                color=ft.Colors.WHITE,
                                bgcolor=ACCENT,
                                shape=ft.RoundedRectangleBorder(radius=10),
                            ),
                            on_click=self._open_create_dialog,
                        ),
                    ),
                    bgcolor=GLASS_BG,
                    border_radius=16,
                    padding=60,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.WHITE)),
                    expand=True,
                )
            )
            return
        for project in self.projects:
            self.project_grid.controls.append(self._project_card(project))

    def _empty_state(self):
        return ft.Container(
            padding=60,
            border_radius=16,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.WHITE)),
            bgcolor=GLASS_BG,
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=15,
                controls=[
                    ft.Icon(ft.Icons.SMART_TOY_OUTLINED, size=48, color=TEXT3),
                    ft.Text("No projects yet", size=18, weight=ft.FontWeight.W_600, color=TEXT),
                    ft.Text("Create your first AI chatbot to get started.", size=13, color=TEXT2),
                    ft.Container(height=8),
                    ft.FilledButton(
                        "Create Project",
                        icon=ft.Icons.ADD,
                        style=ft.ButtonStyle(
                            color=ft.Colors.WHITE,
                            bgcolor=ACCENT,
                            shape=ft.RoundedRectangleBorder(radius=10),
                        ),
                        on_click=self._open_create_dialog,
                    ),
                ],
            ),
        )

    def _project_card(self, project):
        stats = project.get("stats") or {}
        doc_count = stats.get("doc_count", project.get("document_count", 0))
        msg_count = stats.get("message_count", project.get("message_count", 0))
        last_active = stats.get("last_active") or "Never"
        name = project.get("name", "Unnamed")
        desc = project.get("description", "") or "No description"

        # Subtle accent variations per card
        accent_variants = [ACCENT, ACCENT2, ACCENT3, SUCCESS]
        accent_color = accent_variants[hash(name) % len(accent_variants)]

        return ft.Container(
            padding=20,
            border_radius=14,
            bgcolor=CARD,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.WHITE)),
            on_click=lambda e, p=project: self._open_project(p),
            ink=True,
            animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
            shadow=ft.BoxShadow(
                blur_radius=16,
                color="rgba(0,0,0,0.25)",
                offset=ft.Offset(0, 3),
            ),
            content=ft.Column(
                spacing=14,
                controls=[
                    # Icon + delete row
                    ft.Row(
                        controls=[
                            ft.Container(
                                width=38,
                                height=38,
                                border_radius=10,
                                bgcolor=ft.Colors.with_opacity(0.12, accent_color),
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.SMART_TOY, color=accent_color, size=18),
                            ),
                            ft.Container(expand=True),
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE,
                                icon_size=16,
                                icon_color=ft.Colors.with_opacity(0.4, ft.Colors.RED),
                                on_click=lambda _, p=project: self._delete_project(p),
                                style=ft.ButtonStyle(
                                    overlay_color=ft.Colors.with_opacity(0.08, ft.Colors.RED),
                                ),
                            ),
                        ]
                    ),
                    # Name & description
                    ft.Text(name, size=16, weight=ft.FontWeight.W_600, color=TEXT),
                    ft.Text(desc, size=12, color=TEXT2, max_lines=2),
                    # Divider
                    ft.Divider(color=ft.Colors.with_opacity(0.06, ft.Colors.WHITE), height=1),
                    # Stats row
                    ft.Row(
                        spacing=16,
                        controls=[
                            ft.Row(
                                spacing=4,
                                controls=[
                                    ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=14, color=TEXT3),
                                    ft.Text(f"{doc_count} docs", size=11, color=TEXT2),
                                ],
                            ),
                            ft.Row(
                                spacing=4,
                                controls=[
                                    ft.Icon(ft.Icons.CHAT_OUTLINED, size=14, color=TEXT3),
                                    ft.Text(f"{msg_count} msgs", size=11, color=TEXT2),
                                ],
                            ),
                            ft.Container(expand=True),
                            ft.Container(
                                content=ft.Icon(ft.Icons.ARROW_FORWARD, size=14,
                                                color=ft.Colors.with_opacity(0.3, ft.Colors.WHITE)),
                            ),
                        ],
                    ),
                ],
            ),
        )

    def _open_project(self, project):
        self.navigate("project", project.get("id"))

    def _open_create_dialog(self, e):
        self.project_name.value = ""
        self.project_desc.value = ""
        self.system_prompt.value = ""
        self._page.show_dialog(self.create_dialog)

    def _close_dialog(self, e):
        self._page.pop_dialog()

    def _create_project(self, e):
        if not self.project_name.value:
            return
        data = {
            "name": self.project_name.value.strip(),
            "description": self.project_desc.value.strip(),
            "system_prompt": self.system_prompt.value.strip(),
        }
        try:
            self.api_client("/api/projects", method="POST", json=data)
        except Exception as ex:
            logger.error("Create project failed", error=str(ex))
        self._page.pop_dialog()
        self.load_projects()

    def _delete_project(self, project):
        try:
            self.api_client(f"/api/projects/{project.get('id')}", method="DELETE")
            self.load_projects()
        except Exception as ex:
            logger.error("Delete project failed", error=str(ex))
