"""Project dashboard view for the AI Chatbot Builder Pro."""

import flet as ft
from typing import Callable, Optional


class DashboardView(ft.Container):
    """Dashboard showing project grid with creation dialog."""

    def __init__(self, page: ft.Page, api_base: str = ""):
        super().__init__()
        self._page = page
        self.api_base = api_base
        self.on_navigate = None
        self.projects = []
        self.loading = ft.ProgressRing(visible=False)

    def api_client(self, path: str, method: str = "GET", **kwargs) -> any:
        """Synchronous HTTP helper — calls the API via httpx."""
        import httpx
        url = f"{self.api_base}{path}"
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
        except Exception:
            return None

    def navigate(self, route: str, project_id: Optional[str] = None) -> None:
        """Delegate navigation to the parent app's handler."""
        if self.on_navigate:
            self.on_navigate(route, project_id)

        # Create project dialog fields
        self.project_name = ft.TextField(
            label="Project Name",
            hint_text="e.g. Customer Support Bot",
            border_color=ft.Colors.with_opacity(0.3, ft.Colors.WHITE),
            color=ft.Colors.WHITE,
            label_style=ft.TextStyle(color=ft.Colors.GREY_400),
        )
        self.project_desc = ft.TextField(
            label="Description",
            hint_text="What will this chatbot do?",
            multiline=True,
            min_lines=2,
            max_lines=4,
            border_color=ft.Colors.with_opacity(0.3, ft.Colors.WHITE),
            color=ft.Colors.WHITE,
            label_style=ft.TextStyle(color=ft.Colors.GREY_400),
        )
        self.system_prompt = ft.TextField(
            label="System Prompt",
            hint_text="You are a helpful assistant that answers questions based on the provided documents...",
            multiline=True,
            min_lines=3,
            max_lines=6,
            border_color=ft.Colors.with_opacity(0.3, ft.Colors.WHITE),
            color=ft.Colors.WHITE,
            label_style=ft.TextStyle(color=ft.Colors.GREY_400),
        )

        self.create_dialog = ft.AlertDialog(
            title=ft.Text("Create New Project", color=ft.Colors.WHITE, size=18, weight=ft.FontWeight.BOLD),
            bgcolor=ft.Colors.with_opacity(0.98, ft.Colors.GREY_900),
            content=ft.Container(
                width=500,
                padding=20,
                content=ft.Column(
                    spacing=15,
                    controls=[self.project_name, self.project_desc, self.system_prompt],
                ),
            ),
            actions=[
                ft.TextButton("Cancel", on_click=self._close_dialog),
                ft.FilledButton(
                    "Create Project",
                    style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
                    on_click=self._create_project,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.project_grid = ft.GridView(
            runs_count=3,
            max_extent=350,
            spacing=15,
            run_spacing=15,
            padding=0,
        )

    async def build(self):
        """Return the dashboard container for rendering."""
        # Build content on first call
        self.content = ft.Container(
            padding=20,
            content=ft.Column(
                spacing=15,
                controls=[


                    ft.Row(
                        controls=[
                            ft.Column(
                                spacing=4,
                                controls=[
                                    ft.Text("🤖 AI Chatbot Builder", size=28, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                                    ft.Text("Create and manage AI chatbots trained on your documents.", size=14, color=ft.Colors.GREY_400),
                                ],
                                expand=True,
                            ),
                            ft.FilledButton(
                                "New Project",
                                icon=ft.Icons.ADD,
                                style=ft.ButtonStyle(
                                    color=ft.Colors.WHITE,
                                    bgcolor=ft.Colors.BLUE_700,
                                    shape=ft.RoundedRectangleBorder(radius=8),
                                ),
                                on_click=self._open_create_dialog,
                            ),
                            self.loading,
                        ]
                    ),
                    self.project_grid,
                ],
            ),
        )
        return self

    def did_mount(self):
        self._load_projects()

    def _load_projects(self):
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
                self._empty_state()
            )
            return
        for project in self.projects:
            self.project_grid.controls.append(
                self._project_card(project)
            )

    def _empty_state(self):
        return ft.Container(
            padding=60,
            border_radius=16,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=15,
                controls=[
                    ft.Icon(ft.Icons.SMART_TOY, size=64, color=ft.Colors.GREY_600),
                    ft.Text("No projects yet", size=20, weight=ft.FontWeight.W_600, color=ft.Colors.GREY_400),
                    ft.Text("Create your first AI chatbot to get started.", size=14, color=ft.Colors.GREY_500),
                    ft.FilledButton(
                        "Create Project",
                        icon=ft.Icons.ADD,
                        style=ft.ButtonStyle(bgcolor=ft.Colors.BLUE_700, color=ft.Colors.WHITE),
                        on_click=self._open_create_dialog,
                    ),
                ],
            ),
        )

    def _project_card(self, project):
        doc_count = project.get("document_count", 0)
        msg_count = project.get("message_count", 0)
        last_active = project.get("last_active", "Never")
        name = project.get("name", "Unnamed")
        desc = project.get("description", "") or "No description"
        bg_colors = ["#1a1d27", "#1d1f2a", "#1b1e28", "#1c1f2b", "#19202a"]
        bg_idx = hash(name) % len(bg_colors)

        return ft.Container(
            padding=20,
            border_radius=12,
            bgcolor=bg_colors[bg_idx],
            border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.WHITE)),
            on_click=lambda _, p=project: self.navigate("project", p.get("id")),
            ink=True,
            content=ft.Column(
                spacing=12,
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(
                                width=40,
                                height=40,
                                border_radius=10,
                                bgcolor=ft.Colors.BLUE_700,
                                alignment=ft.Alignment.CENTER,
                                content=ft.Icon(ft.Icons.SMART_TOY, color=ft.Colors.WHITE, size=20),
                            ),
                            ft.Container(expand=True),
                            ft.IconButton(
                                ft.Icons.DELETE_OUTLINE,
                                icon_size=18,
                                icon_color=ft.Colors.RED_400,
                                on_click=lambda _, p=project: self._delete_project(p),
                            ),
                        ]
                    ),
                    ft.Text(name, size=16, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                    ft.Text(desc, size=12, color=ft.Colors.GREY_500, max_lines=2),
                    ft.Divider(color=ft.Colors.with_opacity(0.08, ft.Colors.WHITE), height=1),
                    ft.Row(
                        spacing=20,
                        controls=[
                            ft.Row(
                                spacing=4,
                                controls=[
                                    ft.Icon(ft.Icons.DESCRIPTION, size=14, color=ft.Colors.BLUE_400),
                                    ft.Text(f"{doc_count} docs", size=12, color=ft.Colors.GREY_400),
                                ],
                            ),
                            ft.Row(
                                spacing=4,
                                controls=[
                                    ft.Icon(ft.Icons.CHAT, size=14, color=ft.Colors.GREEN_400),
                                    ft.Text(f"{msg_count} msgs", size=12, color=ft.Colors.GREY_400),
                                ],
                            ),
                        ],
                    ),
                ],
            ),
        )

    def _open_create_dialog(self, e):
        self._page.dialog = self.create_dialog
        self.create_dialog.open = True
        self.project_name.value = ""
        self.project_desc.value = ""
        self.system_prompt.value = ""
        self._page.update()

    def _close_dialog(self, e):
        self.create_dialog.open = False
        self._page.update()

    def _create_project(self, e):
        if not self.project_name.value:
            return
        data = {
            "name": self.project_name.value.strip(),
            "description": self.project_desc.value.strip(),
            "system_prompt": self.system_prompt.value.strip(),
        }
        try:
            result = self.api_client("/api/projects", method="POST", json=data)
            self.create_dialog.open = False
            self._page.update()
            self._load_projects()
        except Exception as ex:
            print(f"Create project failed: {ex}")

    def _delete_project(self, project):
        try:
            self.api_client(f"/api/projects/{project.get('id')}", method="DELETE")
            self._load_projects()
        except Exception as ex:
            print(f"Delete failed: {ex}")
