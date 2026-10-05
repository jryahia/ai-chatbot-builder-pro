"""Project view — document management and chat panel.
Refined classic design — better hierarchy, cleaner tabs, pro feel.
"""

import flet as ft
from typing import Callable, Optional, Any
import asyncio


def _fire(coro):
    """Fire-and-forget an async coroutine, returning None for Flet event handlers."""
    asyncio.ensure_future(coro)
import os

from src.ui.components import (
    ACCENT, ACCENT2, BG, CARD, SURFACE, TEXT, TEXT2, TEXT3,
    BORDER_COLOR, GLASS_BG, SUCCESS, ERROR, WARNING,
    glass_card, primary_button, secondary_button, ghost_button,
    divider, toast, status_badge, loading_spinner,
    T,
)


class ProjectView(ft.Container):
    """View for managing documents and chatting — cleaner, faster, classic."""

    def __init__(self, page: ft.Page, api_base: str = "", project_id: Optional[str] = None):
        super().__init__()
        self._page = page
        self.api_base = api_base
        self.project_id = project_id
        self.project = {}
        self.documents = []
        self.loading = ft.ProgressRing(visible=False, width=16, height=16, stroke_width=2, color=ACCENT)
        self.on_navigate = None

        self._init_ui()

    def _init_ui(self):
        """Build all UI components — called once from __init__."""
        # Header controls
        self.title_text = ft.Text("Project", size=20, weight=ft.FontWeight.BOLD, color=TEXT)
        self.back_btn = ft.IconButton(
            ft.Icons.ARROW_BACK_ROUNDED,
            icon_color=TEXT2,
            on_click=lambda _: self._go_back(),
            style=ft.ButtonStyle(overlay_color=ft.Colors.with_opacity(0.08, ft.Colors.WHITE)),
        )
        self.status_text = ft.Text("", color=SUCCESS, size=12)

        # Document list
        self.doc_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)

        # Chat panel
        self.chat_history = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)
        self.chat_input = ft.TextField(
            hint_text="Ask a question about your documents...",
            border_color=ft.Colors.with_opacity(0.12, ft.Colors.WHITE),
            color=TEXT,
            hint_style=ft.TextStyle(color=TEXT3, size=13),
            text_style=ft.TextStyle(color=TEXT, size=14),
            focused_border_color=ACCENT,
            cursor_color=ACCENT,
            bgcolor=BG,
            border_radius=10,
            multiline=False,
            expand=True,
        )
        self.send_btn = ft.IconButton(
            ft.Icons.SEND_ROUNDED,
            icon_color=ACCENT,
            on_click=self._send_message,
            style=ft.ButtonStyle(overlay_color=ft.Colors.with_opacity(0.1, ACCENT)),
        )

        # Tabs — cleaner divider styling
        self._docs_tab = self._build_docs_tab()
        self._chat_tab = self._build_chat_tab()
        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=200,
            length=2,
            expand=True,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(
                        label_color=TEXT,
                        unselected_label_color=TEXT3,
                        indicator_color=ACCENT,
                        indicator_size=3,
                        tabs=[
                            ft.Tab(label="Documents"),
                            ft.Tab(label="Chat"),
                        ],
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=[
                            self._docs_tab,
                            self._chat_tab,
                        ],
                    ),
                ],
            ),
        )

        self.content = ft.Container(
            padding=ft.Padding.symmetric(horizontal=28, vertical=20),
            content=ft.Column(
                spacing=16,
                controls=[
                    ft.Row(controls=[self.back_btn, self.title_text, self.loading]),
                    self.status_text,
                    self.tabs,
                ],
                expand=True,
            ),
        )

    def api_client(self, path: str, method: str = "GET", **kwargs) -> any:
        import httpx
        if path.startswith("/api/") and not path.startswith("/api/v1/"):
            path = path.replace("/api/", "/api/v1/", 1)
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

    async def navigate(self, route: str, project_id_val: Optional[str] = None) -> None:
        if self.on_navigate:
            await self.on_navigate(route, project_id_val)

    def render(self, project_id: Optional[str] = None) -> "ProjectView":
        if project_id is not None:
            self.project_id = project_id
        return self

    async def _go_back(self):
        await self.navigate("dashboard")

    def did_mount(self):
        if self.project_id:
            self._load_project()

    def _build_docs_tab(self):
        # ─── Premium Upload Drop Zone — drag-drop feel ──────────────────────
        self.upload_cloud_icon = ft.Container(
            content=ft.Icon(ft.Icons.CLOUD_UPLOAD_OUTLINED, size=32, color=ACCENT),
            bgcolor=ft.Colors.with_opacity(0.10, ACCENT),
            border_radius=12,
            padding=12,
        )

        self.upload_title = ft.Text(
            "Drop files or folders here",
            size=14, weight=ft.FontWeight.W_500, color=TEXT,
        )
        self.upload_subtitle = ft.Text(
            "PDF, DOCX, TXT, MD, HTML, CSV, JSON — or an entire folder",
            size=11, color=TEXT3, text_align=ft.TextAlign.CENTER,
        )
        self.upload_picker_btn = ft.ElevatedButton(
            "Choose Files",
            icon=ft.Icons.FILE_PRESENT,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.with_opacity(0.12, ACCENT),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=self._upload_files,
        )
        self.upload_folder_btn = ft.OutlinedButton(
            "Choose Folder",
            icon=ft.Icons.FOLDER_OPEN,
            style=ft.ButtonStyle(
                color=ACCENT,
                side=ft.BorderSide(1, ft.Colors.with_opacity(0.2, ACCENT)),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=self._upload_folder,
        )

        self.upload_zone = ft.Container(
            padding=28,
            border_radius=16,
            border=ft.Border.all(1.5, ft.Colors.with_opacity(0.12, ACCENT), "dashed"),
            bgcolor=ft.Colors.with_opacity(0.03, ACCENT),
            animate=ft.Animation(200, ft.AnimationCurve.EASE_IN_OUT),
            ink=False,
            shadow=ft.BoxShadow(
                blur_radius=24,
                color="rgba(79,140,255,0.06)",
                offset=ft.Offset(0, 2),
            ),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                controls=[
                    self.upload_cloud_icon,
                    self.upload_title,
                    self.upload_subtitle,
                    ft.Container(height=6),
                    ft.Row(
                        controls=[self.upload_picker_btn, self.upload_folder_btn],
                        spacing=12,
                        alignment=ft.MainAxisAlignment.CENTER,
                    ),
                ],
            ),
        )

        # ─── URL Input + Crawl ──────────────────────────────────────────────
        self.url_input = ft.TextField(
            label="Or enter a website URL",
            hint_text="https://example.com/docs",
            border_color=ft.Colors.with_opacity(0.12, ft.Colors.WHITE),
            color=TEXT,
            label_style=ft.TextStyle(color=TEXT3, size=11),
            text_style=ft.TextStyle(color=TEXT, size=14),
            focused_border_color=ACCENT,
            cursor_color=ACCENT,
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
            border_radius=10,
            expand=True,
        )
        self.crawl_btn = ft.ElevatedButton(
            "Crawl",
            icon=ft.Icons.LANGUAGE,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.with_opacity(0.12, SUCCESS),
                shape=ft.RoundedRectangleBorder(radius=8),
            ),
            on_click=self._crawl_url,
        )

        return ft.Column(
            spacing=16,
            controls=[
                self.upload_zone,
                ft.Row(controls=[self.url_input, self.crawl_btn], spacing=8),
                divider(),
                ft.Row(
                    controls=[
                        ft.Text("Documents", size=16, weight=ft.FontWeight.W_600, color=TEXT),
                        ft.Container(expand=True),
                        ghost_button(
                            "Re-embed All",
                            icon=ft.Icons.REFRESH,
                            on_click=self._reembed_all,
                        ),
                    ]
                ),
                self.doc_list,
            ],
            expand=True,
        )

    def _build_chat_tab(self):
        return ft.Column(
            spacing=10,
            controls=[
                ft.Container(
                    expand=True,
                    padding=12,
                    border_radius=12,
                    bgcolor=GLASS_BG,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.WHITE)),
                    content=self.chat_history,
                ),
                ft.Container(
                    content=ft.Row(
                        controls=[self.chat_input, self.send_btn],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    bgcolor=SURFACE,
                    border_radius=12,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=6),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.WHITE)),
                ),
            ],
            expand=True,
        )

    def _load_project(self):
        self.loading.visible = True
        self.update()
        try:
            project = self.api_client(f"/api/projects/{self.project_id}")
            self.project = project if isinstance(project, dict) else {}
            self.title_text.value = self.project.get("name", "Project")
            documents = self.api_client(f"/api/projects/{self.project_id}/documents")
            self.documents = documents if isinstance(documents, list) else []
        except Exception:
            self.project = {}
            self.documents = []
        self.loading.visible = False
        self._render_documents()
        self.update()

    def _render_documents(self):
        self.doc_list.controls.clear()
        if not self.documents:
            self.doc_list.controls.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=32, color=TEXT3),
                            ft.Text("No documents yet", size=14, weight=ft.FontWeight.W_500, color=TEXT),
                            ft.Text("Upload files or crawl a website.", size=12, color=TEXT3, italic=True),
                        ],
                        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                        spacing=6,
                    ),
                    padding=24,
                    alignment=ft.Alignment.CENTER,
                )
            )
            return
        for doc in self.documents:
            self.doc_list.controls.append(self._doc_item(doc))

    def _doc_item(self, doc):
        name = doc.get("filename", doc.get("name", "Unknown"))
        status = doc.get("status", "pending")
        chunks = doc.get("chunk_count", 0)
        size = doc.get("size", 0)

        status_colors = {
            "completed": SUCCESS,
            "processing": ACCENT,
            "pending": TEXT3,
            "failed": ERROR,
        }
        status_color = status_colors.get(status, TEXT3)

        icons = {
            "pdf": ft.Icons.PICTURE_AS_PDF,
            "docx": ft.Icons.DESCRIPTION,
            "txt": ft.Icons.TEXT_SNIPPET,
            "md": ft.Icons.TEXT_SNIPPET,
            "html": ft.Icons.CODE,
            "csv": ft.Icons.TABLE_CHART,
            "json": ft.Icons.DATA_OBJECT,
            "url": ft.Icons.LANGUAGE,
        }
        ext = name.split(".")[-1].lower() if "." in name else "url"
        icon = icons.get(ext, ft.Icons.INSERT_DRIVE_FILE)

        size_str = f"{size / 1024:.1f} KB" if size > 0 else ""

        return ft.Container(
            padding=ft.Padding.symmetric(horizontal=14, vertical=10),
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.03, ft.Colors.WHITE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.WHITE)),
            content=ft.Row(
                controls=[
                    ft.Container(
                        content=ft.Icon(icon, color=ACCENT, size=18),
                        bgcolor=ft.Colors.with_opacity(0.1, ACCENT),
                        border_radius=8,
                        padding=8,
                    ),
                    ft.Column(
                        spacing=3,
                        controls=[
                            ft.Text(name, size=13, color=TEXT, weight=ft.FontWeight.W_500),
                            ft.Row(
                                spacing=10,
                                controls=[
                                    status_badge(status),
                                    ft.Text(f"{chunks} chunks", size=11, color=TEXT3) if chunks else ft.Text(""),
                                    ft.Text(size_str, size=11, color=TEXT3) if size_str else ft.Text(""),
                                ],
                            ),
                        ],
                        expand=True,
                    ),
                    ft.IconButton(
                        ft.Icons.DELETE_OUTLINE,
                        icon_size=16,
                        icon_color=ft.Colors.with_opacity(0.4, ft.Colors.RED),
                        on_click=lambda _, d=doc: self._delete_doc(d),
                        style=ft.ButtonStyle(overlay_color=ft.Colors.with_opacity(0.08, ft.Colors.RED)),
                    ),
                ],
            ),
        )

    def _upload_files(self, e):
        file_picker = ft.FilePicker(on_result=self._on_file_pick)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.pick_files(allow_multiple=True, allowed_extensions=["pdf", "docx", "txt", "md", "html", "csv", "json"])

    def _upload_folder(self, e):
        """Open a folder picker and upload all valid documents inside."""
        folder_picker = ft.FilePicker(on_result=self._on_folder_pick)
        self.page.overlay.append(folder_picker)
        self.page.update()
        folder_picker.get_directory_path()

    def _on_folder_pick(self, e):
        if not e.path:
            return
        import os
        allowed_exts = {".pdf", ".docx", ".txt", ".md", ".html", ".csv", ".json"}
        folder_path = e.path
        files_found = []
        for root, dirs, files in os.walk(folder_path):
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in allowed_exts:
                    files_found.append(os.path.join(root, f))

        if not files_found:
            self.status_text.value = "No supported documents found in that folder"
            self.status_text.color = WARNING
            self.update()
            return

        self.status_text.value = f"Uploading {len(files_found)} files from folder..."
        self.status_text.color = WARNING
        self.update()

        success = 0
        failed = 0
        for filepath in files_found:
            try:
                filename = os.path.basename(filepath)
                with open(filepath, "rb") as fh:
                    files = {"file": (filename, fh, "application/octet-stream")}
                    self.api_client(
                        f"/api/projects/{self.project_id}/documents/upload",
                        method="POST",
                        files=files,
                    )
                success += 1
            except Exception:
                failed += 1

        if failed:
            self.status_text.value = f"Uploaded {success} files ({failed} failed) from folder"
            self.status_text.color = SUCCESS if success else ERROR
        else:
            self.status_text.value = f"All {success} files uploaded from folder"
            self.status_text.color = SUCCESS
        self.update()
        self._load_project()

    def _on_file_pick(self, e):
        if not e.files:
            return
        total = len(e.files)
        self.status_text.value = f"Uploading {total} file{'s' if total > 1 else ''}..."
        self.status_text.color = WARNING
        self.update()
        success = 0
        failed = 0
        for f in e.files:
            try:
                self._upload_single(f)
                success += 1
            except Exception:
                failed += 1
        if failed:
            self.status_text.value = f"Uploaded {success} file{'s' if success > 1 else ''} ({failed} failed)"
            self.status_text.color = SUCCESS if success else ERROR
        else:
            self.status_text.value = f"All {total} file{'s' if total > 1 else ''} uploaded"
            self.status_text.color = SUCCESS
        self.update()
        self._load_project()

    def _upload_single(self, file):
        with open(file.path, "rb") as fh:
            files = {"file": (file.name, fh, "application/octet-stream")}
            self.api_client(
                f"/api/projects/{self.project_id}/documents/upload",
                method="POST",
                files=files,
            )

    def _crawl_url(self, e):
        url = self.url_input.value.strip()
        if not url:
            return
        self.status_text.value = f"Crawling {url}..."
        self.status_text.color = WARNING
        self.update()
        try:
            self.api_client(
                f"/api/projects/{self.project_id}/crawl",
                method="POST",
                json={"url": url},
            )
            self.status_text.value = "Website crawled!"
            self.status_text.color = SUCCESS
            self.url_input.value = ""
            self._load_project()
        except Exception as ex:
            self.status_text.value = f"Crawl failed: {ex}"
            self.status_text.color = ERROR
        self.update()

    def _reembed_all(self, e):
        self.status_text.value = "Re-embedding all documents..."
        self.status_text.color = WARNING
        self.update()
        try:
            self.api_client(f"/api/projects/{self.project_id}/reembed", method="POST")
            self.status_text.value = "Re-embedding complete!"
            self.status_text.color = SUCCESS
        except Exception as ex:
            self.status_text.value = f"Re-embed failed: {ex}"
            self.status_text.color = ERROR
        self.update()

    def _delete_doc(self, doc):
        try:
            self.api_client(f"/api/projects/{self.project_id}/documents/{doc.get('id')}", method="DELETE")
            self._load_project()
        except Exception as ex:
            self.status_text.value = f"Delete failed: {ex}"
            self.status_text.color = ERROR
            self.update()

    def _send_message(self, e):
        msg = self.chat_input.value.strip()
        if not msg:
            return
        self.chat_input.value = ""
        self.update()

        # User bubble
        self.chat_history.controls.append(
            ft.Container(
                padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                border_radius=12,
                bgcolor=ft.Colors.with_opacity(0.12, ACCENT),
                content=ft.Column(
                    spacing=4,
                    controls=[
                        ft.Text(msg, color=TEXT, size=14),
                        ft.Text("You", size=10, color=ft.Colors.with_opacity(0.5, ft.Colors.WHITE), italic=True),
                    ],
                ),
                margin=ft.Margin.only(left=100),
            )
        )
        self.chat_history.update()

        try:
            result = self.api_client(
                f"/api/projects/{self.project_id}/chat",
                method="POST",
                json={"message": msg},
            )
            response_text = result.get("response", result.get("answer", "No response"))
            sources = result.get("sources", [])

            resp_controls = [
                ft.Text("Assistant", size=10, color=SUCCESS, italic=True),
                ft.Container(height=4),
                ft.Text(response_text, color=TEXT, size=14),
            ]

            if sources:
                source_texts = []
                for s in sources[:3]:
                    name = s.get("filename", s.get("name", "Source"))
                    score = s.get("score", 0)
                    source_texts.append(f"{name} ({score:.2f})")
                resp_controls.append(
                    ft.Container(
                        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
                        border_radius=8,
                        bgcolor=ft.Colors.with_opacity(0.06, SUCCESS),
                        margin=ft.Margin.only(top=8),
                        content=ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text("Sources:", size=11, color=SUCCESS),
                                *[ft.Text(s, size=11, color=TEXT3) for s in source_texts],
                            ],
                        ),
                    )
                )

            self.chat_history.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.06, SUCCESS),
                    content=ft.Column(controls=resp_controls),
                    margin=ft.Margin.only(right=100),
                )
            )

        except Exception as ex:
            self.chat_history.controls.append(
                ft.Container(
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    border_radius=12,
                    bgcolor=ft.Colors.with_opacity(0.08, ERROR),
                    content=ft.Text(f"Error: {ex}", color=ERROR, size=13),
                    margin=ft.Margin.only(right=100),
                )
            )

        self.chat_history.update()
