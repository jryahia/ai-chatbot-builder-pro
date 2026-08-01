"""Flet app shell with routing and navigation — classic premium dark design.
Chic, fast, refined. Glass sidebar, subtle header, smooth transitions.
"""

from typing import Callable, Optional

import flet as ft

from src.config import settings
from src.ui.components import ACCENT, ACCENT2, BG, CARD, SURFACE, TEXT, TEXT2, BORDER_COLOR, divider


ROUTES = {
    "/": "dashboard",
    "/project": "project",
    "/analytics": "analytics",
    "/settings": "settings",
}


async def main(page: ft.Page) -> None:
    page.title = "AI Chatbot Builder Pro"
    page.theme_mode = ft.ThemeMode.DARK
    page.bgcolor = BG
    page.padding = 0

    # Window — classic desktop proportions
    page.window.width = 1280
    page.window.height = 800
    page.window.min_width = 960
    page.window.min_height = 640

    page.theme = ft.Theme(
        color_scheme_seed=ACCENT,
        color_scheme=ft.ColorScheme(
            primary=ACCENT,
            secondary=ACCENT2,
            on_primary=ft.Colors.WHITE,
            on_secondary=ft.Colors.WHITE,
            surface_container_low=SURFACE,
        ),
        text_theme=ft.TextTheme(
            body_large=ft.TextStyle(color=TEXT),
            body_medium=ft.TextStyle(color=TEXT),
            label_large=ft.TextStyle(color=TEXT),
        ),
    )

    # ─── State ─────────────────────────────────────────────────────────────────
    current_route = "dashboard"
    selected_project_id: Optional[str] = None
    selected_nav_index = 0

    # ─── View Imports ──────────────────────────────────────────────────────────
    from src.ui.dashboard import DashboardView
    from src.ui.project_view import ProjectView
    from src.ui.analytics_view import AnalyticsView
    from src.ui.settings_view import SettingsView

    api_base = settings.api_base_url

    dashboard = DashboardView(page, api_base)
    project_view = ProjectView(page, api_base)
    analytics_view = AnalyticsView(page, api_base)
    settings_view = SettingsView(page, api_base)

    # ─── Content Area ──────────────────────────────────────────────────────────
    content_area = ft.Container(
        content=dashboard.render(),
        expand=True,
        bgcolor=BG,
        padding=0,
    )

    # ─── Navigate ──────────────────────────────────────────────────────────────
    def navigate(route: str, project_id: Optional[str] = None) -> None:
        nonlocal current_route, selected_project_id, selected_nav_index

        current_route = route
        selected_project_id = project_id

        if route == "project" and project_id:
            content_area.content = project_view.render(project_id)
            selected_nav_index = 0
        elif route == "analytics":
            content_area.content = analytics_view.render(project_id)
            selected_nav_index = 1
        elif route == "settings":
            content_area.content = settings_view.render()
            selected_nav_index = 3
        else:
            route = "dashboard"
            content_area.content = dashboard.render()
            selected_nav_index = 0

        nav_rail.selected_index = selected_nav_index
        page.update()

        # Trigger data load after mount
        if route == "dashboard":
            dashboard.load_projects()
        elif route == "project" and project_id:
            project_view._load_project()
        elif route == "analytics":
            analytics_view._load_data()

    dashboard.on_navigate = navigate
    project_view.on_navigate = navigate
    analytics_view.on_navigate = navigate
    settings_view.on_navigate = navigate

    def on_nav_change(e: ft.ControlEvent) -> None:
        idx = e.control.selected_index
        if idx == 0:
            navigate("dashboard")
        elif idx == 1:
            navigate("analytics", selected_project_id)
        elif idx == 2:
            navigate(current_route, selected_project_id)
        elif idx == 3:
            navigate("settings")

    # ─── Navigation Rail — refined, compact ────────────────────────────────────
    nav_destinations = [
        ft.NavigationRailDestination(
            icon=ft.Icons.DASHBOARD_ROUNDED,
            selected_icon=ft.Icons.DASHBOARD,
            label="Dashboard",
        ),
        ft.NavigationRailDestination(
            icon=ft.Icons.ANALYTICS_ROUNDED,
            selected_icon=ft.Icons.BAR_CHART,
            label="Analytics",
        ),
        ft.NavigationRailDestination(
            icon=ft.Icons.REFRESH_ROUNDED,
            selected_icon=ft.Icons.REFRESH,
            label="Refresh",
        ),
        ft.NavigationRailDestination(
            icon=ft.Icons.SETTINGS_ROUNDED,
            selected_icon=ft.Icons.SETTINGS,
            label="Settings",
        ),
    ]

    nav_rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=72,
        min_extended_width=160,
        bgcolor=SURFACE,
        indicator_color=ft.Colors.with_opacity(0.12, ACCENT),
        indicator_shape=ft.RoundedRectangleBorder(radius=8),
        destinations=nav_destinations,
        on_change=on_nav_change,
    )

    # ─── App Header — sleek, minimal ──────────────────────────────────────────
    header = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        # Logo badge — subtle glow
                        ft.Container(
                            content=ft.Text("CB", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            bgcolor=ACCENT,
                            border_radius=8,
                            width=30,
                            height=30,
                            alignment=ft.Alignment.CENTER,
                            shadow=ft.BoxShadow(
                                blur_radius=14,
                                color=ft.Colors.with_opacity(0.35, ACCENT),
                                offset=ft.Offset(0, 2),
                            ),
                        ),
                        ft.Text("AI Chatbot Builder", size=15, weight=ft.FontWeight.W_600, color=TEXT),
                        ft.Container(
                            content=ft.Text("PRO", size=9, weight=ft.FontWeight.BOLD, color=ACCENT),
                            bgcolor=ft.Colors.with_opacity(0.12, ACCENT),
                            border_radius=4,
                            padding=ft.Padding.symmetric(horizontal=5, vertical=2),
                        ),
                    ],
                    spacing=8,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        bgcolor=SURFACE,
        padding=ft.Padding.symmetric(horizontal=24, vertical=10),
        border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.06, ft.Colors.WHITE))),
    )

    # ─── Layout ────────────────────────────────────────────────────────────────
    layout = ft.Column(
        [
            header,
            ft.Row(
                [
                    nav_rail,
                    ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.06, ft.Colors.WHITE)),
                    content_area,
                ],
                expand=True,
                spacing=0,
            ),
        ],
        spacing=0,
        expand=True,
    )

    page.add(layout)
    page.update()

    # Initial data load
    dashboard.load_projects()
