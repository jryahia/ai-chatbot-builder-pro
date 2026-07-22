"""Project view — document management and chat panel for AI Chatbot Builder Pro."""

import flet as ft
from typing import Callable, Optional, Any
import os


class ProjectView(ft.Container):
    """View for managing documents and chatting with a specific project."""

    def __init__(self, page: ft.Page, api_base: str = "", project_id: Optional[str] = None):
        super().__init__()
        self._page = page
        self.api_base = api_base
        self.project_id = project_id
        self.project = {}
        self.documents = []
        self.loading = ft.ProgressRing(visible=False)
        self.on_navigate = None

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

    def navigate(self, route: str, project_id_val: Optional[str] = None) -> None:
        """Delegate navigation to the parent app's handler."""
        if self.on_navigate:
            self.on_navigate(route, project_id_val)

        # Back button and title
        self.title_text = ft.Text("Project", size=22, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE)
        self.back_btn = ft.IconButton(
            ft.Icons.ARROW_BACK,
            icon_color=ft.Colors.GREY_400,
            on_click=lambda _: self.navigate("dashboard"),
        )
        self.status_text = ft.Text("", color=ft.Colors.GREEN_400, size=13)

        # Document list
        self.doc_list = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)

        # Chat panel
        self.chat_history = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO)
        self.chat_input = ft.TextField(
            hint_text="Ask a question about your documents...",
            border_color=ft.Colors.with_opacity(0.3, ft.Colors.WHITE),
            color=ft.Colors.WHITE,
            hint_style=ft.TextStyle(color=ft.Colors.GREY_500),
            multiline=False,
            expand=True,
        )
        self.send_btn = ft.IconButton(
            ft.Icons.SEND_ROUNDED,
            icon_color=ft.Colors.BLUE_400,
            on_click=self._send_message,
        )

        # Tabs
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
                        label_color=ft.Colors.WHITE,
                        unselected_label_color=ft.Colors.GREY_500,
                        indicator_color=ft.Colors.BLUE_400,
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
            padding=20,
            content=ft.Column(
                spacing=15,
                controls=[
                    ft.Row(controls=[self.back_btn, self.title_text, self.loading]),
                    self.status_text,
                    self.tabs,
                ],
                expand=True,
            ),
        )

    def did_mount(self):
        if self.project_id:
            self._load_project()

    def _build_docs_tab(self):
        # Upload zone
        self.upload_zone = ft.Container(
            padding=30,
            border_radius=12,
            border=ft.Border.all(2, ft.Colors.with_opacity(0.15, ft.Colors.BLUE), "dashed"),
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.BLUE),
            content=ft.Column(
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=10,
                controls=[
                    ft.Icon(ft.Icons.CLOUD_UPLOAD, size=40, color=ft.Colors.BLUE_400),
                    ft.Text("Drop files here or click to upload", size=14, color=ft.Colors.GREY_400),
                    ft.Text("PDF, DOCX, TXT, MD, HTML, CSV, JSON", size=11, color=ft.Colors.GREY_600),
                    ft.ElevatedButton(
                        "Select Files",
                        icon=ft.Icons.FOLDER_OPEN,
                        style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.BLUE)),
                        on_click=self._upload_files,
                    ),
                ],
            ),
        )

        # Website URL input
        self.url_input = ft.TextField(
            label="Or enter a website URL",
            hint_text="https://example.com/docs",
            border_color=ft.Colors.with_opacity(0.3, ft.Colors.WHITE),
            color=ft.Colors.WHITE,
            label_style=ft.TextStyle(color=ft.Colors.GREY_400),
            expand=True,
        )
        self.crawl_btn = ft.ElevatedButton(
            "Crawl", icon=ft.Icons.LANGUAGE,
            style=ft.ButtonStyle(color=ft.Colors.WHITE, bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.GREEN)),
            on_click=self._crawl_url,
        )

        return ft.Column(
            spacing=15,
            controls=[
                self.upload_zone,
                ft.Row(controls=[self.url_input, self.crawl_btn]),
                ft.Divider(color=ft.Colors.with_opacity(0.08, ft.Colors.WHITE), height=1),
                ft.Row(
                    controls=[
                        ft.Text("Documents", size=16, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                        ft.Container(expand=True),
                        ft.ElevatedButton(
                            "Re-embed All",
                            icon=ft.Icons.REFRESH,
                            style=ft.ButtonStyle(color=ft.Colors.AMBER_400, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.AMBER)),
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
                    padding=10,
                    border_radius=12,
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.WHITE)),
                    content=self.chat_history,
                ),
                ft.Row(
                    controls=[self.chat_input, self.send_btn],
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
                ft.Text("No documents yet. Upload files or crawl a website.", size=13, color=ft.Colors.GREY_500, italic=True)
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
            "completed": ft.Colors.GREEN_400,
            "processing": ft.Colors.YELLOW_400,
            "pending": ft.Colors.GREY_500,
            "failed": ft.Colors.RED_400,
        }
        status_color = status_colors.get(status, ft.Colors.GREY_500)

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
            padding=12,
            border_radius=8,
            bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
            border=ft.Border.all(1, ft.Colors.with_opacity(0.06, ft.Colors.WHITE)),
            content=ft.Row(
                controls=[
                    ft.Icon(icon, color=ft.Colors.BLUE_400, size=20),
                    ft.Column(
                        spacing=2,
                        controls=[
                            ft.Text(name, size=14, color=ft.Colors.WHITE),
                            ft.Row(
                                spacing=10,
                                controls=[
                                    ft.Container(
                                        padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                                        border_radius=6,
                                        bgcolor=ft.Colors.with_opacity(0.15, status_color),
                                        content=ft.Text(status.capitalize(), size=10, color=status_color),
                                    ),
                                    ft.Text(f"{chunks} chunks", size=11, color=ft.Colors.GREY_500) if chunks else ft.Text(""),
                                    ft.Text(size_str, size=11, color=ft.Colors.GREY_500) if size_str else ft.Text(""),
                                ],
                            ),
                        ],
                        expand=True,
                    ),
                    ft.IconButton(
                        ft.Icons.DELETE_OUTLINE,
                        icon_size=18,
                        icon_color=ft.Colors.RED_400,
                        on_click=lambda _, d=doc: self._delete_doc(d),
                    ),
                ],
            ),
        )

    def _upload_files(self, e):
        file_picker = ft.FilePicker(on_result=self._on_file_pick)
        self.page.overlay.append(file_picker)
        self.page.update()
        file_picker.pick_files(allow_multiple=True, allowed_extensions=["pdf", "docx", "txt", "md", "html", "csv", "json"])

    def _on_file_pick(self, e):
        if not e.files:
            return
        for f in e.files:
            try:
                self._upload_single(f)
            except Exception as ex:
                print(f"Upload error: {ex}")

    def _upload_single(self, file):
        # File upload via API
        with open(file.path, "rb") as fh:
            files = {"file": (file.name, fh, "application/octet-stream")}
            self.api_client(
                f"/api/projects/{self.project_id}/documents/upload",
                method="POST",
                files=files,
            )
        self.status_text.value = f"✅ Uploaded {file.name}"
        self.status_text.color = ft.Colors.GREEN_400
        self.update()
        self._load_project()

    def _crawl_url(self, e):
        url = self.url_input.value.strip()
        if not url:
            return
        self.status_text.value = f"🕷️ Crawling {url}..."
        self.status_text.color = ft.Colors.YELLOW_400
        self.update()
        try:
            self.api_client(
                f"/api/projects/{self.project_id}/crawl",
                method="POST",
                json={"url": url},
            )
            self.status_text.value = "✅ Website crawled!"
            self.status_text.color = ft.Colors.GREEN_400
            self.url_input.value = ""
            self._load_project()
        except Exception as ex:
            self.status_text.value = f"❌ Crawl failed: {ex}"
            self.status_text.color = ft.Colors.RED_400
        self.update()

    def _reembed_all(self, e):
        self.status_text.value = "♻️ Re-embedding all documents..."
        self.status_text.color = ft.Colors.YELLOW_400
        self.update()
        try:
            self.api_client(f"/api/projects/{self.project_id}/reembed", method="POST")
            self.status_text.value = "✅ Re-embedding complete!"
            self.status_text.color = ft.Colors.GREEN_400
        except Exception as ex:
            self.status_text.value = f"❌ Re-embed failed: {ex}"
            self.status_text.color = ft.Colors.RED_400
        self.update()

    def _delete_doc(self, doc):
        try:
            self.api_client(f"/api/projects/{self.project_id}/documents/{doc.get('id')}", method="DELETE")
            self._load_project()
        except Exception as ex:
            self.status_text.value = f"❌ Delete failed: {ex}"
            self.status_text.color = ft.Colors.RED_400
            self.update()

    def _send_message(self, e):
        msg = self.chat_input.value.strip()
        if not msg:
            return
        self.chat_input.value = ""
        self.update()

        # Add user message bubble
        self.chat_history.controls.append(
            ft.Container(
                padding=12,
                border_radius=10,
                bgcolor=ft.Colors.BLUE_700,
                content=ft.Row(
                    controls=[
                        ft.Container(expand=True),
                        ft.Column(
                            width=400,
                            controls=[
                                ft.Text(msg, color=ft.Colors.WHITE, size=14),
                                ft.Text("You", size=10, color=ft.Colors.BLUE_200, italic=True),
                            ],
                        ),
                    ],
                ),
                margin=ft.margin.only(left=100),
            )
        )
        self.chat_history.update()

        # Send to API
        try:
            result = self.api_client(
                f"/api/projects/{self.project_id}/chat",
                method="POST",
                json={"message": msg},
            )
            response_text = result.get("response", result.get("answer", "No response"))
            sources = result.get("sources", [])

            # Build response bubble
            resp_controls = [
                ft.Text("🤖 Assistant", size=10, color=ft.Colors.GREEN_300, italic=True),
                ft.Text(response_text, color=ft.Colors.WHITE, size=14),
            ]

            if sources:
                source_texts = []
                for s in sources[:3]:
                    name = s.get("filename", s.get("name", "Source"))
                    score = s.get("score", 0)
                    source_texts.append(f"📄 {name} ({score:.2f})")
                resp_controls.append(
                    ft.Container(
                        padding=8,
                        border_radius=6,
                        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN),
                        content=ft.Column(
                            spacing=2,
                            controls=[
                                ft.Text("Sources:", size=11, color=ft.Colors.GREEN_300),
                                *[ft.Text(s, size=11, color=ft.Colors.GREY_400) for s in source_texts],
                            ],
                        ),
                    )
                )

            self.chat_history.controls.append(
                ft.Container(
                    padding=12,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.GREEN),
                    content=ft.Column(controls=resp_controls),
                    margin=ft.margin.only(right=100),
                )
            )

        except Exception as ex:
            self.chat_history.controls.append(
                ft.Container(
                    padding=12,
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.RED),
                    content=ft.Text(f"❌ Error: {ex}", color=ft.Colors.RED_400, size=13),
                    margin=ft.margin.only(right=100),
                )
            )

        self.chat_history.update()
