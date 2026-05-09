"""Chat panel component for AI Chatbot Builder Pro."""

import flet as ft
from typing import Callable, Optional, Any, List


class ChatPanel(ft.Container):
    """Reusable streaming chat interface with source citations."""

    def __init__(
        self,
        send_message: Callable,
        project_name: str = "Chat",
        height: Optional[int] = None,
    ):
        super().__init__()
        self.send_message = send_message
        self.project_name = project_name
        self.messages: List[dict] = []
        self.is_loading = False
        self.custom_height = height

        self.chat_area = ft.Column(
            spacing=8,
            scroll=ft.ScrollMode.AUTO,
        )

        self.message_input = ft.TextField(
            hint_text="Type your message...",
            border_color=ft.Colors.with_opacity(0.3, ft.Colors.WHITE),
            color=ft.Colors.WHITE,
            hint_style=ft.TextStyle(color=ft.Colors.GREY_500),
            multiline=False,
            expand=True,
            on_submit=self._on_submit,
        )
        self.send_button = ft.IconButton(
            ft.Icons.SEND_ROUNDED,
            icon_color=ft.Colors.BLUE_400,
            on_click=self._on_submit,
        )
        self.loading_indicator = ft.ProgressRing(visible=False, width=18, height=18)

        self.content = ft.Column(
            spacing=10,
            controls=[
                # Header
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=16, vertical=12),
                    border_radius=10,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
                    content=ft.Row(
                        controls=[
                            ft.Icon(ft.Icons.SMART_TOY, color=ft.Colors.BLUE_400, size=20),
                            ft.Text(self.project_name, size=16, weight=ft.FontWeight.W_600, color=ft.Colors.WHITE),
                            ft.Container(expand=True),
                            ft.IconButton(
                                ft.Icons.DELETE_SWEEP,
                                icon_size=18,
                                icon_color=ft.Colors.GREY_500,
                                tooltip="Clear chat",
                                on_click=self._clear_chat,
                            ),
                        ]
                    ),
                ),
                # Chat area
                ft.Container(
                    expand=True,
                    padding=10,
                    border_radius=10,
                    border=ft.border.all(1, ft.Colors.with_opacity(0.08, ft.Colors.WHITE)),
                    bgcolor=ft.Colors.with_opacity(0.02, ft.Colors.WHITE),
                    content=self.chat_area,
                ),
                # Input bar
                ft.Container(
                    padding=ft.padding.symmetric(horizontal=4, vertical=4),
                    border_radius=10,
                    border=ft.border.all(1, ft.Colors.with_opacity(0.1, ft.Colors.WHITE)),
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
                    content=ft.Row(
                        controls=[
                            ft.IconButton(
                                ft.Icons.ATTACH_FILE,
                                icon_size=20,
                                icon_color=ft.Colors.GREY_500,
                                tooltip="Attach context",
                            ),
                            self.message_input,
                            self.loading_indicator,
                            self.send_button,
                        ],
                    ),
                ),
            ],
            expand=True,
        )

    def _on_submit(self, e):
        if self.is_loading:
            return
        text = self.message_input.value.strip()
        if not text:
            return
        self.message_input.value = ""
        self._add_user_message(text)
        self.update()
        self._send(text)

    def _send(self, text: str):
        self.is_loading = True
        self.loading_indicator.visible = True
        self.send_button.disabled = True
        self.message_input.disabled = True
        self.update()

        try:
            result = self.send_message(text)
            response = result.get("response", result.get("answer", result.get("text", "No response")))
            sources = result.get("sources", [])
            self._add_bot_message(response, sources)
        except Exception as ex:
            self._add_error_message(str(ex))
        finally:
            self.is_loading = False
            self.loading_indicator.visible = False
            self.send_button.disabled = False
            self.message_input.disabled = False
            self.update()

    def _add_user_message(self, text: str):
        self.messages.append({"role": "user", "content": text})
        bubble = ft.Container(
            padding=12,
            border_radius=10,
            bgcolor=ft.Colors.BLUE_700,
            content=ft.Column(
                spacing=2,
                controls=[
                    ft.Row(
                        controls=[
                            ft.Container(expand=True),
                            ft.Column(
                                width=400,
                                controls=[
                                    ft.Text(text, color=ft.Colors.WHITE, size=14, selectable=True),
                                ],
                            ),
                        ],
                    ),
                    ft.Row(
                        controls=[
                            ft.Container(expand=True),
                            ft.Text("You", size=10, color=ft.Colors.BLUE_200, italic=True),
                        ],
                    ),
                ],
            ),
            margin=ft.margin.only(left=80),
            animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT),
        )
        self.chat_area.controls.append(bubble)
        self._scroll_to_bottom()

    def _add_bot_message(self, text: str, sources: Optional[List[dict]] = None):
        self.messages.append({"role": "assistant", "content": text, "sources": sources or []})

        controls = [
            ft.Row(
                controls=[
                    ft.Container(
                        width=28, height=28, border_radius=14,
                        bgcolor=ft.Colors.GREEN_700,
                        alignment=ft.alignment.center,
                        content=ft.Icon(ft.Icons.SMART_TOY, size=16, color=ft.Colors.WHITE),
                    ),
                    ft.Text("Assistant", size=11, color=ft.Colors.GREEN_300, italic=True),
                ],
            ),
            ft.Container(
                content=ft.Text(text, color=ft.Colors.WHITE, size=14, selectable=True),
                margin=ft.margin.only(left=36),
            ),
        ]

        if sources:
            source_items = []
            for s in sources[:4]:
                name = s.get("filename", s.get("name", s.get("title", "Source")))
                score = s.get("score", s.get("relevance", 0))
                source_items.append(
                    ft.Container(
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        border_radius=4,
                        bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE),
                        content=ft.Text(
                            f"📄 {name} ({score:.2f})" if score else f"📄 {name}",
                            size=11, color=ft.Colors.BLUE_300,
                        ),
                    )
                )
            controls.append(
                ft.Container(
                    padding=8,
                    border_radius=6,
                    bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.BLUE),
                    margin=ft.margin.only(left=36),
                    content=ft.Column(
                        spacing=4,
                        controls=[
                            ft.Text("Sources:", size=10, color=ft.Colors.BLUE_400, weight=ft.FontWeight.W_600),
                            *source_items,
                        ],
                    ),
                )
            )

        bubble = ft.Container(
            padding=12,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.GREEN),
            margin=ft.margin.only(right=80),
            animate=ft.animation.Animation(200, ft.AnimationCurve.EASE_OUT),
            content=ft.Column(spacing=6, controls=controls),
        )
        self.chat_area.controls.append(bubble)
        self._scroll_to_bottom()

    def _add_error_message(self, error_text: str):
        self.chat_area.controls.append(
            ft.Container(
                padding=12,
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.RED),
                margin=ft.margin.only(right=80),
                content=ft.Row(
                    controls=[
                        ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_400, size=16),
                        ft.Text(f"Error: {error_text}", color=ft.Colors.RED_400, size=13),
                    ],
                ),
            )
        )
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        try:
            self.chat_area.scroll_to(offset=-1, duration=200)
        except Exception:
            pass

    def _clear_chat(self, e):
        self.messages.clear()
        self.chat_area.controls.clear()
        self.chat_area.controls.append(
            ft.Container(
                expand=True,
                alignment=ft.alignment.center,
                content=ft.Column(
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                    controls=[
                        ft.Icon(ft.Icons.CHAT, size=48, color=ft.Colors.GREY_700),
                        ft.Text("Start a conversation", size=14, color=ft.Colors.GREY_500),
                        ft.Text("Ask questions about your documents.", size=12, color=ft.Colors.GREY_600),
                    ],
                ),
            )
        )
        self.update()

    def add_welcome_message(self, suggestions: Optional[List[str]] = None):
        """Add a welcome/greeting message with suggested questions."""
        controls = [
            ft.Row(
                controls=[
                    ft.Container(
                        width=28, height=28, border_radius=14,
                        bgcolor=ft.Colors.GREEN_700,
                        alignment=ft.alignment.center,
                        content=ft.Icon(ft.Icons.SMART_TOY, size=16, color=ft.Colors.WHITE),
                    ),
                    ft.Text("Assistant", size=11, color=ft.Colors.GREEN_300, italic=True),
                ],
            ),
            ft.Container(
                margin=ft.margin.only(left=36),
                content=ft.Text(
                    "Hello! I'm your AI assistant. I can answer questions based on your documents. What would you like to know?",
                    color=ft.Colors.WHITE, size=14,
                ),
            ),
        ]

        if suggestions:
            suggestion_btns = []
            for s in suggestions:
                suggestion_btns.append(
                    ft.ElevatedButton(
                        s,
                        style=ft.ButtonStyle(
                            color=ft.Colors.BLUE_300,
                            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.BLUE),
                            side=ft.BorderSide(1, ft.Colors.with_opacity(0.15, ft.Colors.BLUE)),
                            shape=ft.RoundedRectangleBorder(radius=8),
                        ),
                        on_click=lambda _, text=s: self._use_suggestion(text),
                    )
                )
            controls.append(
                ft.Container(
                    margin=ft.margin.only(left=36),
                    content=ft.Column(
                        spacing=6,
                        controls=[
                            ft.Text("Suggested questions:", size=11, color=ft.Colors.GREY_500),
                            ft.Row(wrap=True, spacing=8, controls=suggestion_btns),
                        ],
                    ),
                )
            )

        bubble = ft.Container(
            padding=12,
            border_radius=10,
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.GREEN),
            margin=ft.margin.only(right=80),
            content=ft.Column(spacing=6, controls=controls),
        )
        self.chat_area.controls.append(bubble)
        self.update()

    def _use_suggestion(self, text: str):
        self.message_input.value = text
        self.update()
        self._on_submit(None)
