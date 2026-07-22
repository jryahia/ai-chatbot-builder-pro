"""Flet app shell with routing and navigation."""

from typing import Callable, Optional

import flet as ft

from src.config import settings
from src.ui.components import ACCENT, ACCENT2, BG, CARD, SURFACE, TEXT, TEXT2


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
    page.window_width = 1280
    page.window_height = 800
    page.window_min_width = 900
    page.window_min_height = 600

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
    page.bgcolor = BG

    # State
    current_route = "dashboard"
    selected_project_id: Optional[str] = None
    selected_nav_index = 0

    # Import views
    from src.ui.dashboard import DashboardView
    from src.ui.project_view import ProjectView
    from src.ui.analytics_view import AnalyticsView
    from src.ui.settings_view import SettingsView

    api_base = settings.api_base_url

    dashboard = DashboardView(page, api_base)
    project_view = ProjectView(page, api_base)
    analytics_view = AnalyticsView(page, api_base)
    settings_view = SettingsView(page, api_base)

    content_area = ft.Container(
        content=await dashboard.build(),
        expand=True,
        bgcolor=BG,
    )

    async def navigate(route: str, project_id: Optional[str] = None) -> None:
        nonlocal current_route, selected_project_id, selected_nav_index

        current_route = route
        selected_project_id = project_id

        if route == "dashboard":
            content_area.content = await dashboard.build()
            selected_nav_index = 0
        elif route == "project" and project_id:
            content_area.content = await project_view.build(project_id)
            selected_nav_index = 0
        elif route == "analytics" and project_id:
            content_area.content = await analytics_view.build(project_id)
            selected_nav_index = 1
        elif route == "settings":
            content_area.content = await settings_view.build()
            selected_nav_index = 3
        else:
            content_area.content = await dashboard.build()
            selected_nav_index = 0

        nav_rail.selected_index = selected_nav_index
        page.update()

    dashboard.on_navigate = navigate
    project_view.on_navigate = navigate
    analytics_view.on_navigate = navigate
    settings_view.on_navigate = navigate

    async def on_nav_change(e: ft.ControlEvent) -> None:
        idx = e.control.selected_index
        if idx == 0:
            await navigate("dashboard")
        elif idx == 1:
            if selected_project_id:
                await navigate("analytics", selected_project_id)
            else:
                await navigate("dashboard")
        elif idx == 2:
            # Refresh current view
            await navigate(current_route, selected_project_id)
        elif idx == 3:
            await navigate("settings")

    nav_rail = ft.NavigationRail(
        selected_index=0,
        label_type=ft.NavigationRailLabelType.ALL,
        min_width=80,
        min_extended_width=160,
        bgcolor=SURFACE,
        indicator_color=ft.Colors.with_opacity(0.15, ACCENT),
        indicator_shape=ft.RoundedRectangleBorder(radius=8),
        destinations=[
            ft.NavigationRailDestination(
                icon=ft.Icons.DASHBOARD_OUTLINED,
                selected_icon=ft.Icons.DASHBOARD,
                label="Dashboard",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.BAR_CHART_OUTLINED,
                selected_icon=ft.Icons.BAR_CHART,
                label="Analytics",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.REFRESH_OUTLINED,
                selected_icon=ft.Icons.REFRESH,
                label="Refresh",
            ),
            ft.NavigationRailDestination(
                icon=ft.Icons.SETTINGS_OUTLINED,
                selected_icon=ft.Icons.SETTINGS,
                label="Settings",
            ),
        ],
        on_change=on_nav_change,
    )

    # App header
    header = ft.Container(
        content=ft.Row(
            [
                ft.Row(
                    [
                        ft.Container(
                            content=ft.Text("CB", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            bgcolor=ACCENT,
                            border_radius=8,
                            width=32,
                            height=32,
                            alignment=ft.Alignment.CENTER,
                        ),
                        ft.Text("AI Chatbot Builder", size=16, weight=ft.FontWeight.BOLD, color=TEXT),
                        ft.Container(
                            content=ft.Text("PRO", size=10, weight=ft.FontWeight.BOLD, color=ACCENT),
                            bgcolor=ft.Colors.with_opacity(0.15, ACCENT),
                            border_radius=4,
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2),
                        ),
                    ],
                    spacing=10,
                ),
                ft.Row(
                    [
                        ft.Text("●", size=10, color="#34d399"),
                        ft.Text(f"API :{settings.api_port}", size=12, color=TEXT2),
                    ],
                    spacing=4,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        ),
        bgcolor=SURFACE,
        padding=ft.Padding.symmetric(horizontal=20, vertical=12),
        border=ft.Border.only(bottom=ft.BorderSide(1, ft.Colors.with_opacity(0.08, ft.Colors.WHITE))),
    )

    layout = ft.Column(
        [
            header,
            ft.Row(
                [
                    nav_rail,
                    ft.VerticalDivider(width=1, color=ft.Colors.with_opacity(0.08, ft.Colors.WHITE)),
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
