"""Analytics dashboard view for AI Chatbot Builder Pro.
Refined classic design — clean stat cards, subtle chart bars, professional layout.
"""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Any

import flet as ft
import structlog

from src.ui.components import (
    ACCENT, ACCENT2, BG, CARD, SURFACE, TEXT, TEXT2, TEXT3,
    BORDER_COLOR, SUCCESS, WARNING, ERROR,
    glass_card, card_surface, info_row, loading_spinner,
    primary_button, secondary_button, ghost_button,
    status_badge, toast, divider,
    T,
)

logger = structlog.get_logger(__name__)

CHART_COLORS = [ACCENT, ACCENT2, SUCCESS, WARNING, ERROR]


class AnalyticsView(ft.Column):
    """Analytics dashboard — clean stats, subtle charts, premium feel."""

    def __init__(self, page: ft.Page, api_base: str = "") -> None:
        super().__init__()
        self._page = page
        self.spacing = 20
        self.scroll = ft.ScrollMode.AUTO
        self.expand = True

        self._stats_cards: ft.Row = ft.Row(spacing=16, wrap=True)
        self._chart_container: ft.Container = ft.Container()
        self._top_questions: ft.Column = ft.Column(spacing=8)
        self._response_times: ft.Column = ft.Column(spacing=8)
        self._export_btn = primary_button("Export CSV", on_click=self._export_csv)
        self._loading_indicator = loading_spinner("Loading analytics...")

        self.controls = [
            ft.Container(
                content=ft.Column(
                    controls=[
                        ft.Text("Analytics Dashboard", size=26, weight=ft.FontWeight.BOLD, color=TEXT),
                        ft.Text("Usage statistics and performance metrics for your chatbots", size=14, color=TEXT2),
                    ],
                    spacing=2,
                ),
                margin=ft.Margin.only(bottom=4),
            ),
            divider(),
            self._loading_indicator,
            self._stats_cards,
            self._chart_container,
            ft.Text("Top Questions", size=20, weight=ft.FontWeight.W_600, color=TEXT),
            self._top_questions,
            divider(),
            ft.Text("Response Time Distribution", size=20, weight=ft.FontWeight.W_600, color=TEXT),
            self._response_times,
            ft.Row(
                [self._export_btn],
                alignment=ft.MainAxisAlignment.END,
            ),
        ]

    def render(self, project_id: str | None = None) -> "AnalyticsView":
        self.project_id = project_id
        return self

    def did_mount(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        try:
            stats = self._fetch_stats()
            self._build_stats_cards(stats)
            self._build_chart(stats.get("daily_users", []))
            self._build_top_questions(stats.get("top_questions", []))
            self._build_response_times(stats.get("response_times", []))
            self._loading_indicator.visible = False
            self.update()
        except Exception as e:
            logger.error("Failed to load analytics", error=str(e))
            self._loading_indicator.visible = False
            self._page.snack_bar = toast(f"Error loading analytics: {e}")
            self._page.snack_bar.open = True
            self.update()

    def _fetch_stats(self) -> dict[str, Any]:
        try:
            from src.analytics import get_dashboard_stats
            return get_dashboard_stats()
        except ImportError:
            return {
                "total_conversations": 0,
                "total_messages": 0,
                "total_tokens": 0,
                "daily_active_users": 0,
                "daily_users": [],
                "top_questions": [],
                "response_times": [],
            }

    def _build_stats_cards(self, stats: dict[str, Any]) -> None:
        stat_items = [
            ("Total Conversations", str(stats.get("total_conversations", 0)), ACCENT, ft.Icons.CHAT_OUTLINED),
            ("Total Messages", str(stats.get("total_messages", 0)), ACCENT2, ft.Icons.FORUM_OUTLINED),
            ("Total Tokens Used", str(stats.get("total_tokens", 0)), SUCCESS, ft.Icons.TOKEN_OUTLINED),
            ("Daily Active Users", str(stats.get("daily_active_users", 0)), WARNING, ft.Icons.PEOPLE_OUTLINED),
        ]

        cards = []
        for label, value, color, icon in stat_items:
            cards.append(
                glass_card(
                    ft.Column(
                        [
                            ft.Row(
                                [
                                    ft.Container(
                                        content=ft.Icon(icon, color=color, size=18),
                                        bgcolor=ft.Colors.with_opacity(0.12, color),
                                        border_radius=8,
                                        padding=8,
                                    ),
                                    ft.Container(expand=True),
                                    ft.Text(value, size=26, weight=ft.FontWeight.BOLD, color=color),
                                ],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Container(height=2),
                            ft.Text(label, size=12, color=TEXT3),
                        ],
                        spacing=6,
                    ),
                    padding=16,
                    width=220,
                )
            )
        self._stats_cards.controls = cards

    def _build_chart(self, daily_users: list[dict]) -> None:
        if not daily_users:
            self._chart_container.content = ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.Icons.BAR_CHART_OUTLINED, size=32, color=TEXT3),
                        ft.Text("No daily user data yet", color=TEXT3),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=8,
                ),
                bgcolor=CARD,
                border_radius=12,
                padding=40,
                alignment=ft.Alignment.CENTER,
            )
            return

        chart_data = daily_users[-14:]
        max_val = max(d.get("count", 0) for d in chart_data) or 1

        bars = []
        for d in chart_data:
            day = d.get("date", "")[-5:] if d.get("date") else ""
            count = d.get("count", 0)
            bar_height = max(16, (count / max_val) * 140)
            bars.append(
                ft.Column(
                    [
                        ft.Text(str(count), size=10, color=TEXT3),
                        ft.Container(
                            width=28,
                            height=bar_height,
                            bgcolor=ACCENT,
                            border_radius=ft.BorderRadius.only(top_left=4, top_right=4),
                        ),
                        ft.Text(day, size=9, color=TEXT3),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                )
            )

        self._chart_container.content = glass_card(
            ft.Column(
                [
                    ft.Text("Daily Active Users (Last 14 Days)", size=16, weight=ft.FontWeight.W_600, color=TEXT),
                    ft.Row(bars, alignment=ft.MainAxisAlignment.SPACE_AROUND, spacing=8),
                ],
                spacing=16,
            ),
            padding=20,
        )

    def _build_top_questions(self, questions: list[dict]) -> None:
        if not questions:
            self._top_questions.controls = [
                ft.Text("No questions recorded yet", color=TEXT3, italic=True)
            ]
            return

        items = []
        for i, q in enumerate(questions[:10], 1):
            items.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(str(i), size=12, weight=ft.FontWeight.BOLD, color=ACCENT),
                                width=26, height=26,
                                bgcolor=ft.Colors.with_opacity(0.1, ACCENT),
                                border_radius=13, alignment=ft.Alignment.CENTER,
                            ),
                            ft.Column(
                                [
                                    ft.Text(q.get("question", ""), size=14, color=TEXT),
                                    ft.Text(f"{q.get('count', 0)} times", size=11, color=TEXT3),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Text(f"{q.get('count', 0)}", size=14, weight=ft.FontWeight.BOLD, color=ACCENT),
                                bgcolor=ft.Colors.with_opacity(0.1, ACCENT),
                                border_radius=8,
                                padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    bgcolor=SURFACE,
                    border_radius=10,
                    padding=ft.Padding.symmetric(horizontal=14, vertical=10),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.04, ft.Colors.WHITE)),
                )
            )
        self._top_questions.controls = items

    def _build_response_times(self, response_times: list[dict]) -> None:
        if not response_times:
            self._response_times.controls = [
                ft.Text("No response time data yet", color=TEXT3, italic=True)
            ]
            return

        buckets = response_times[:8]
        max_val = max(b.get("count", 0) for b in buckets) or 1

        items = []
        for b in buckets:
            label = b.get("bucket", "")
            count = b.get("count", 0)
            bar_width = max(24, (count / max_val) * 350)
            items.append(
                ft.Row(
                    [
                        ft.Text(label, size=12, color=TEXT, width=80),
                        ft.Container(
                            width=bar_width,
                            height=18,
                            bgcolor=ACCENT2,
                            border_radius=4,
                            animate=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
                        ),
                        ft.Text(str(count), size=11, color=TEXT3),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        self._response_times.controls = [
            ft.Column(items, spacing=8),
        ]

    def _export_csv(self, e: ft.ControlEvent | None = None) -> None:
        try:
            from src.analytics import export_analytics_csv
            csv_data = export_analytics_csv()
            output = io.StringIO()
            output.write(csv_data)
            output.seek(0)

            save_path = "/tmp/analytics_export.csv"
            with open(save_path, "w") as f:
                f.write(csv_data)

            if self.page and hasattr(self.page, "open_file"):
                self._page.open_file(save_path)

            self._page.snack_bar = toast("Analytics exported successfully!")
            self._page.snack_bar.open = True
            self.update()
        except Exception as e:
            logger.error("Export failed", error=str(e))
            if self.page:
                self._page.snack_bar = toast(f"Export failed: {e}")
                self._page.snack_bar.open = True
                self.update()
