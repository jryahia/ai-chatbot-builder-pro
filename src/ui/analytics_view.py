"""Analytics dashboard view for AI Chatbot Builder Pro."""

from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta
from typing import Any

import flet as ft
import structlog

from src.ui.components import (
    card_surface,
    info_row,
    loading_spinner,
    primary_button,
    secondary_button,
    status_badge,
    toast,
)

logger = structlog.get_logger(__name__)

DARK_BG = "#0f1117"
DARK_SURFACE = "#1a1d27"
DARK_CARD = "#222733"
ACCENT_BLUE = "#4f8cff"
ACCENT_PURPLE = "#7c5cfc"
TEXT_PRIMARY = "#f1f5f9"
TEXT_SECONDARY = "#94a3b8"

# Chart colors
CHART_COLORS = ["#4f8cff", "#7c5cfc", "#34d399", "#fbbf24", "#ef4444"]


class AnalyticsView(ft.Column):
    """Analytics dashboard with stats, charts, and export."""

    def __init__(self, page: ft.Page) -> None:
        super().__init__()
        self.page = page
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
            ft.Text("Analytics Dashboard", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ft.Text("Usage statistics and performance metrics for your chatbots", size=14, color=TEXT_SECONDARY),
            ft.Divider(height=1, color="rgba(255,255,255,0.08)"),
            self._loading_indicator,
            self._stats_cards,
            self._chart_container,
            ft.Text("Top Questions", size=20, weight=ft.FontWeight.SEMIBOLD, color=TEXT_PRIMARY),
            self._top_questions,
            ft.Divider(height=1, color="rgba(255,255,255,0.08)"),
            ft.Text("Response Time Distribution", size=20, weight=ft.FontWeight.SEMIBOLD, color=TEXT_PRIMARY),
            self._response_times,
            ft.Row(
                [self._export_btn],
                alignment=ft.MainAxisAlignment.END,
            ),
        ]

    def did_mount(self) -> None:
        self._load_data()

    def _load_data(self) -> None:
        """Fetch analytics data and update UI."""
        try:
            # Simulate async fetch from src/analytics.py
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
            self.page.snack_bar = toast(f"Error loading analytics: {e}")
            self.page.snack_bar.open = True
            self.update()

    def _fetch_stats(self) -> dict[str, Any]:
        """Fetch analytics data. In production, calls src/analytics."""
        try:
            from src.analytics import get_dashboard_stats
            return get_dashboard_stats()
        except ImportError:
            # Fallback mock data for development
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
        """Build stat card row."""
        stat_items = [
            ("Total Conversations", str(stats.get("total_conversations", 0)), ACCENT_BLUE, "💬"),
            ("Total Messages", str(stats.get("total_messages", 0)), ACCENT_PURPLE, "📝"),
            ("Total Tokens Used", str(stats.get("total_tokens", 0)), "#34d399", "🔤"),
            ("Daily Active Users", str(stats.get("daily_active_users", 0)), "#fbbf24", "👥"),
        ]

        cards = []
        for label, value, color, icon in stat_items:
            cards.append(
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Row(
                                [ft.Text(icon, size=24), ft.Text(value, size=28, weight=ft.FontWeight.BOLD, color=color)],
                                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                            ),
                            ft.Text(label, size=12, color=TEXT_SECONDARY),
                        ],
                        spacing=8,
                    ),
                    bgcolor=DARK_CARD,
                    border_radius=12,
                    padding=20,
                    width=220,
                    animate=ft.animation.Animation(300, ft.AnimationCurve.EASE_IN_OUT),
                )
            )
        self._stats_cards.controls = cards

    def _build_chart(self, daily_users: list[dict]) -> None:
        """Build daily active users chart."""
        if not daily_users:
            self._chart_container.content = ft.Container(
                content=ft.Text("No daily user data yet", color=TEXT_SECONDARY, italic=True),
                bgcolor=DARK_CARD,
                border_radius=12,
                padding=30,
                alignment=ft.alignment.center,
            )
            return

        chart_data = daily_users[-14:]  # Last 14 days
        max_val = max(d.get("count", 0) for d in chart_data) or 1

        bars = []
        for d in chart_data:
            day = d.get("date", "")[-5:] if d.get("date") else ""
            count = d.get("count", 0)
            bar_height = max(20, (count / max_val) * 150)
            bars.append(
                ft.Column(
                    [
                        ft.Text(str(count), size=10, color=TEXT_SECONDARY),
                        ft.Container(
                            width=30,
                            height=bar_height,
                            bgcolor=ACCENT_BLUE,
                            border_radius=ft.border_radius.only(top_left=4, top_right=4),
                        ),
                        ft.Text(day, size=9, color=TEXT_SECONDARY),
                    ],
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    spacing=4,
                )
            )

        self._chart_container.content = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Daily Active Users (Last 14 Days)", size=16, weight=ft.FontWeight.SEMIBOLD, color=TEXT_PRIMARY),
                    ft.Row(bars, alignment=ft.MainAxisAlignment.SPACE_AROUND, spacing=8),
                ],
                spacing=16,
            ),
            bgcolor=DARK_CARD,
            border_radius=12,
            padding=20,
        )

    def _build_top_questions(self, questions: list[dict]) -> None:
        """Build top questions list."""
        if not questions:
            self._top_questions.controls = [
                ft.Text("No questions recorded yet", color=TEXT_SECONDARY, italic=True)
            ]
            return

        items = []
        for i, q in enumerate(questions[:10], 1):
            items.append(
                ft.Container(
                    content=ft.Row(
                        [
                            ft.Container(
                                content=ft.Text(str(i), size=12, weight=ft.FontWeight.BOLD, color=ACCENT_BLUE),
                                width=28, height=28, bgcolor=f"{ACCENT_BLUE}20",
                                border_radius=14, alignment=ft.alignment.center,
                            ),
                            ft.Column(
                                [
                                    ft.Text(q.get("question", ""), size=14, color=TEXT_PRIMARY),
                                    ft.Text(f"{q.get('count', 0)} times", size=11, color=TEXT_SECONDARY),
                                ],
                                spacing=2,
                                expand=True,
                            ),
                            ft.Container(
                                content=ft.Text(f"{q.get('count', 0)}", size=14, weight=ft.FontWeight.BOLD, color=ACCENT_BLUE),
                                bgcolor=f"{ACCENT_BLUE}15",
                                border_radius=8, padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                            ),
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    bgcolor=DARK_SURFACE,
                    border_radius=8,
                    padding=12,
                )
            )
        self._top_questions.controls = items

    def _build_response_times(self, response_times: list[dict]) -> None:
        """Build response time distribution visualization."""
        if not response_times:
            self._response_times.controls = [
                ft.Text("No response time data yet", color=TEXT_SECONDARY, italic=True)
            ]
            return

        buckets = response_times[:8]
        max_val = max(b.get("count", 0) for b in buckets) or 1

        items = []
        for b in buckets:
            label = b.get("bucket", "")
            count = b.get("count", 0)
            bar_width = max(30, (count / max_val) * 400)
            items.append(
                ft.Row(
                    [
                        ft.Text(label, size=12, color=TEXT_PRIMARY, width=80),
                        ft.Container(
                            width=bar_width,
                            height=20,
                            bgcolor=ACCENT_PURPLE,
                            border_radius=4,
                            animate=ft.animation.Animation(500, ft.AnimationCurve.EASE_OUT),
                        ),
                        ft.Text(str(count), size=11, color=TEXT_SECONDARY),
                    ],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        self._response_times.controls = [
            ft.Column(items, spacing=8),
        ]

    def _export_csv(self, e: ft.ControlEvent | None = None) -> None:
        """Export analytics data as CSV and trigger download."""
        try:
            from src.analytics import export_analytics_csv

            csv_data = export_analytics_csv()
            output = io.StringIO()
            output.write(csv_data)
            output.seek(0)

            # Save to a temp file and trigger download via file_picker
            save_path = "/tmp/analytics_export.csv"
            with open(save_path, "w") as f:
                f.write(csv_data)

            if self.page and hasattr(self.page, "open_file"):
                self.page.open_file(save_path)

            self.page.snack_bar = toast("Analytics exported successfully!")
            self.page.snack_bar.open = True
            self.update()
        except Exception as e:
            logger.error("Export failed", error=str(e))
            if self.page:
                self.page.snack_bar = toast(f"Export failed: {e}")
                self.page.snack_bar.open = True
                self.update()
