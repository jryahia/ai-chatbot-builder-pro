"""Settings view for AI Chatbot Builder Pro."""

from __future__ import annotations

import json
import os
from typing import Any, Optional

import flet as ft
import structlog

from src.ui.components import (
    card_surface,
    info_row,
    primary_button,
    secondary_button,
    danger_button,
    toast,
)

logger = structlog.get_logger(__name__)

DARK_BG = "#0f1117"
DARK_SURFACE = "#1a1d27"
DARK_CARD = "#222733"
ACCENT_BLUE = "#4f8cff"
ACCENT_PURPLE = "#7c5cfc"
ACCENT_GREEN = "#34d399"
ACCENT_RED = "#ef4444"
TEXT_PRIMARY = "#f1f5f9"
TEXT_SECONDARY = "#94a3b8"


class SettingsView(ft.Column):
    """Settings page with tabs for API keys, models, appearance, data, and system."""

    def __init__(self, page: ft.Page, api_base: str = "") -> None:
        super().__init__()
        self._page = page
        self.api_base = api_base
        self.spacing = 20
        self.scroll = ft.ScrollMode.AUTO
        self.expand = True

        # API Keys state
        self._openai_key = ft.TextField(
            label="OpenAI API Key",
            password=True,
            can_reveal_password=True,
            width=500,
            bgcolor=DARK_SURFACE,
            color=TEXT_PRIMARY,
            border_color="rgba(255,255,255,0.12)",
            label_style=ft.TextStyle(color=TEXT_SECONDARY, size=13),
        )
        self._anthropic_key = ft.TextField(
            label="Anthropic API Key",
            password=True,
            can_reveal_password=True,
            width=500,
            bgcolor=DARK_SURFACE,
            color=TEXT_PRIMARY,
            border_color="rgba(255,255,255,0.12)",
            label_style=ft.TextStyle(color=TEXT_SECONDARY, size=13),
        )
        self._google_key = ft.TextField(
            label="Google Gemini API Key",
            password=True,
            can_reveal_password=True,
            width=500,
            bgcolor=DARK_SURFACE,
            color=TEXT_PRIMARY,
            border_color="rgba(255,255,255,0.12)",
            label_style=ft.TextStyle(color=TEXT_SECONDARY, size=13),
        )

        # Model settings
        self._default_model = ft.Dropdown(
            label="Default Model",
            options=[
                ft.dropdown.Option("gpt-4o"),
                ft.dropdown.Option("claude-sonnet-4-20250514"),
                ft.dropdown.Option("gemini-2.0-flash"),
                ft.dropdown.Option("ollama/llama3"),
            ],
            value="gpt-4o",
            width=300,
            bgcolor=DARK_SURFACE,
            color=TEXT_PRIMARY,
            border_color="rgba(255,255,255,0.12)",
            label_style=ft.TextStyle(color=TEXT_SECONDARY, size=13),
        )
        self._temperature = ft.Slider(
            min=0.0, max=2.0, value=0.7, divisions=20,
            label="{value}",
            active_color=ACCENT_BLUE,
            inactive_color="rgba(79,140,255,0.2)",
        )

        # Appearance
        self._theme_toggle = ft.Switch(
            label="Dark Mode",
            value=True,
            active_color=ACCENT_BLUE,
            on_change=self._toggle_theme,
        )
        self._font_size = ft.Slider(
            min=12, max=24, value=14, divisions=12,
            label="{value}px",
            active_color=ACCENT_BLUE,
            inactive_color="rgba(79,140,255,0.2)",
        )
        self._layout_density = ft.Dropdown(
            label="Layout Density",
            options=[
                ft.dropdown.Option("compact"),
                ft.dropdown.Option("comfortable"),
                ft.dropdown.Option("spacious"),
            ],
            value="comfortable",
            width=300,
            bgcolor=DARK_SURFACE,
            color=TEXT_PRIMARY,
            border_color="rgba(255,255,255,0.12)",
            label_style=ft.TextStyle(color=TEXT_SECONDARY, size=13),
        )

        # System
        self._auto_start = ft.Switch(
            label="Auto-start server on app launch",
            value=False,
            active_color=ACCENT_BLUE,
        )
        self._port = ft.TextField(
            label="Server Port",
            value="8000",
            width=150,
            keyboard_type=ft.KeyboardType.NUMBER,
            bgcolor=DARK_SURFACE,
            color=TEXT_PRIMARY,
            border_color="rgba(255,255,255,0.12)",
            label_style=ft.TextStyle(color=TEXT_SECONDARY, size=13),
        )
        self._log_level = ft.Dropdown(
            label="Log Level",
            options=[
                ft.dropdown.Option("DEBUG"),
                ft.dropdown.Option("INFO"),
                ft.dropdown.Option("WARNING"),
                ft.dropdown.Option("ERROR"),
            ],
            value="INFO",
            width=200,
            bgcolor=DARK_SURFACE,
            color=TEXT_PRIMARY,
            border_color="rgba(255,255,255,0.12)",
            label_style=ft.TextStyle(color=TEXT_SECONDARY, size=13),
        )

        # Build tabs — Flet 0.86 TabBar + TabBarView
        self._api_keys_tab = self._build_api_keys_tab()
        self._model_tab = self._build_model_tab()
        self._appearance_tab = self._build_appearance_tab()
        self._data_tab = self._build_data_tab()
        self._system_tab = self._build_system_tab()

        self.tabs = ft.Tabs(
            selected_index=0,
            animation_duration=300,
            length=5,
            expand=True,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(
                        label_color=ACCENT_BLUE,
                        unselected_label_color=TEXT_SECONDARY,
                        indicator_color=ACCENT_BLUE,
                        tabs=[
                            ft.Tab(label="API Keys"),
                            ft.Tab(label="Model Settings"),
                            ft.Tab(label="Appearance"),
                            ft.Tab(label="Data Management"),
                            ft.Tab(label="System"),
                        ],
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=[
                            self._api_keys_tab,
                            self._model_tab,
                            self._appearance_tab,
                            self._data_tab,
                            self._system_tab,
                        ],
                    ),
                ],
            ),
        )

        self.controls = [
            ft.Text("Settings", size=28, weight=ft.FontWeight.BOLD, color=TEXT_PRIMARY),
            ft.Text("Configure your AI Chatbot Builder", size=14, color=TEXT_SECONDARY),
            ft.Divider(height=1, color="rgba(255,255,255,0.08)"),
            self.tabs,
        ]

    def _section_card(self, title: str, controls: list[ft.Control]) -> ft.Container:
        """Wrap controls in a section card."""
        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(title, size=18, weight=ft.FontWeight.W_600, color=TEXT_PRIMARY),
                    ft.Divider(height=1, color="rgba(255,255,255,0.06)"),
                    *controls,
                ],
                spacing=16,
            ),
            bgcolor=DARK_CARD,
            border_radius=12,
            padding=24,
        )

    def _build_api_keys_tab(self) -> ft.Container:
        """Build API keys settings tab."""
        return ft.Container(
            content=ft.Column(
                [
                    self._section_card("API Keys", [
                        ft.Text("Store your provider API keys here. Keys are encrypted at rest.", size=13, color=TEXT_SECONDARY),
                        self._openai_key,
                        self._anthropic_key,
                        self._google_key,
                        ft.Row(
                            [primary_button("Save Keys", on_click=self._save_api_keys)],
                            alignment=ft.MainAxisAlignment.END,
                        ),
                    ]),
                ],
                spacing=20,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=10,
        )

    def _build_model_tab(self) -> ft.Container:
        """Build model settings tab."""
        return ft.Container(
            content=ft.Column(
                [
                    self._section_card("Default Model", [
                        ft.Text("Choose the default LLM model for new projects.", size=13, color=TEXT_SECONDARY),
                        self._default_model,
                    ]),
                    self._section_card("Generation Settings", [
                        ft.Text("Temperature controls response randomness. Lower = more deterministic.", size=13, color=TEXT_SECONDARY),
                        ft.Row(
                            [ft.Text("Temperature", size=14, color=TEXT_PRIMARY), self._temperature],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                        ft.Row(
                            [primary_button("Save Model Settings", on_click=self._save_model_settings)],
                            alignment=ft.MainAxisAlignment.END,
                        ),
                    ]),
                ],
                spacing=20,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=10,
        )

    def _build_appearance_tab(self) -> ft.Container:
        """Build appearance settings tab."""
        return ft.Container(
            content=ft.Column(
                [
                    self._section_card("Theme", [
                        self._theme_toggle,
                    ]),
                    self._section_card("Font Size", [
                        ft.Text("Adjust the UI font size.", size=13, color=TEXT_SECONDARY),
                        ft.Row(
                            [ft.Text("Font Size", size=14, color=TEXT_PRIMARY), self._font_size],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ]),
                    self._section_card("Layout", [
                        self._layout_density,
                    ]),
                    ft.Row(
                        [primary_button("Save Appearance", on_click=self._save_appearance)],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                spacing=20,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=10,
        )

    def _build_data_tab(self) -> ft.Container:
        """Build data management tab."""
        return ft.Container(
            content=ft.Column(
                [
                    self._section_card("Export", [
                        ft.Text("Export all projects and settings as a JSON archive.", size=13, color=TEXT_SECONDARY),
                        ft.Row(
                            [primary_button("Export All Projects", on_click=self._export_projects)],
                            alignment=ft.MainAxisAlignment.START,
                        ),
                    ]),
                    self._section_card("Import", [
                        ft.Text("Import projects from a previously exported JSON archive.", size=13, color=TEXT_SECONDARY),
                        ft.Row(
                            [secondary_button("Import Projects", on_click=self._import_projects)],
                            alignment=ft.MainAxisAlignment.START,
                        ),
                    ]),
                    self._section_card("Clear Data", [
                        ft.Text("Permanently delete all projects, documents, and settings. This cannot be undone.", size=13, color=ACCENT_RED),
                        ft.Row(
                            [danger_button("Clear All Data", on_click=self._confirm_clear_data)],
                            alignment=ft.MainAxisAlignment.START,
                        ),
                    ]),
                ],
                spacing=20,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=10,
        )

    def _build_system_tab(self) -> ft.Container:
        """Build system settings tab."""
        return ft.Container(
            content=ft.Column(
                [
                    self._section_card("Server", [
                        self._auto_start,
                        ft.Row(
                            [ft.Text("Port", size=14, color=TEXT_PRIMARY), self._port],
                            vertical_alignment=ft.CrossAxisAlignment.CENTER,
                        ),
                    ]),
                    self._section_card("Logging", [
                        self._log_level,
                    ]),
                    ft.Row(
                        [primary_button("Save System Settings", on_click=self._save_system_settings)],
                        alignment=ft.MainAxisAlignment.END,
                    ),
                ],
                spacing=20,
                scroll=ft.ScrollMode.AUTO,
            ),
            padding=10,
        )

    def _save_api_keys(self, e: ft.ControlEvent | None = None) -> None:
        """Save API keys to encrypted config."""
        try:
            from src.config import save_api_key
            save_api_key("openai", self._openai_key.value or "")
            save_api_key("anthropic", self._anthropic_key.value or "")
            save_api_key("google", self._google_key.value or "")
            self._page.snack_bar = toast("API keys saved securely!")
            self._page.snack_bar.open = True
            self.update()
        except Exception as ex:
            logger.error("Failed to save API keys", error=str(ex))
            self._page.snack_bar = toast(f"Failed to save keys: {ex}")
            self._page.snack_bar.open = True
            self.update()

    def _save_model_settings(self, e: ft.ControlEvent | None = None) -> None:
        """Save model settings."""
        try:
            from src.config import settings
            settings.default_model = self._default_model.value
            settings.temperature = self._temperature.value
            self._page.snack_bar = toast("Model settings saved!")
            self._page.snack_bar.open = True
            self.update()
        except Exception as ex:
            logger.error("Failed to save model settings", error=str(ex))
            self._page.snack_bar = toast(f"Failed: {ex}")
            self._page.snack_bar.open = True
            self.update()

    def _save_appearance(self, e: ft.ControlEvent | None = None) -> None:
        """Save appearance settings."""
        try:
            from src.config import settings
            settings.dark_mode = self._theme_toggle.value
            settings.font_size = int(self._font_size.value)
            settings.layout_density = self._layout_density.value
            self._page.snack_bar = toast("Appearance settings saved!")
            self._page.snack_bar.open = True
            self.update()
        except Exception as ex:
            logger.error("Failed to save appearance", error=str(ex))
            self._page.snack_bar = toast(f"Failed: {ex}")
            self._page.snack_bar.open = True
            self.update()

    def _save_system_settings(self, e: ft.ControlEvent | None = None) -> None:
        """Save system settings."""
        try:
            from src.config import settings
            settings.auto_start = self._auto_start.value
            settings.server_port = int(self._port.value)
            settings.log_level = self._log_level.value
            self._page.snack_bar = toast("System settings saved!")
            self._page.snack_bar.open = True
            self.update()
        except Exception as ex:
            logger.error("Failed to save system settings", error=str(ex))
            self._page.snack_bar = toast(f"Failed: {ex}")
            self._page.snack_bar.open = True
            self.update()

    def _toggle_theme(self, e: ft.ControlEvent | None = None) -> None:
        """Toggle between dark and light theme."""
        is_dark = self._theme_toggle.value
        self._page.theme_mode = ft.ThemeMode.DARK if is_dark else ft.ThemeMode.LIGHT
        self._page.update()

    def _export_projects(self, e: ft.ControlEvent | None = None) -> None:
        """Export all projects as JSON."""
        try:
            from src.export import export_all_projects
            data = export_all_projects()
            path = "/tmp/chatbot_projects_export.json"
            with open(path, "w") as f:
                json.dump(data, f, indent=2, default=str)
            self._page.snack_bar = toast(f"Exported to {path}")
            self._page.snack_bar.open = True
            self.update()
        except Exception as ex:
            logger.error("Export failed", error=str(ex))
            self._page.snack_bar = toast(f"Export failed: {ex}")
            self._page.snack_bar.open = True
            self.update()

    def _import_projects(self, e: ft.ControlEvent | None = None) -> None:
        """Import projects from JSON file."""
        def on_file_result(result: ft.FilePickerResultEvent | None) -> None:
            if result and result.files:
                try:
                    path = result.files[0].path
                    from src.export import import_projects
                    count = import_projects(path)
                    self._page.snack_bar = toast(f"Imported {count} projects!")
                    self._page.snack_bar.open = True
                    self.update()
                except Exception as ex:
                    logger.error("Import failed", error=str(ex))
                    self._page.snack_bar = toast(f"Import failed: {ex}")
                    self._page.snack_bar.open = True
                    self.update()

        file_picker = ft.FilePicker(on_result=on_file_result)
        self._page.overlay.append(file_picker)
        self._page.update()
        file_picker.pick_files(allow_multiple=False, file_type=ft.FilePickerFileType.CUSTOM, allowed_extensions=["json"])

    def _confirm_clear_data(self, e: ft.ControlEvent | None = None) -> None:
        """Show confirmation dialog before clearing all data."""
        def on_confirm(e: ft.ControlEvent | None = None) -> None:
            dlg.open = False
            self._page.update()
            try:
                from src.export import clear_all_data
                clear_all_data()
                self._page.snack_bar = toast("All data cleared successfully!")
                self._page.snack_bar.open = True
                self.update()
            except Exception as ex:
                logger.error("Clear data failed", error=str(ex))
                self._page.snack_bar = toast(f"Failed: {ex}")
                self._page.snack_bar.open = True
                self.update()

        dlg = ft.AlertDialog(
            modal=True,
            title=ft.Text("Clear All Data", color=TEXT_PRIMARY),
            content=ft.Text(
                "Are you sure you want to delete ALL projects, documents, conversations, and settings? This action cannot be undone.",
                color=TEXT_SECONDARY,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda e: (setattr(dlg, 'open', False), self._page.update())),
                ft.TextButton("Delete Everything", style=ft.ButtonStyle(color=ACCENT_RED), on_click=on_confirm),
            ],
            bgcolor=DARK_SURFACE,
        )
        self._page.dialog = dlg
        dlg.open = True
        self._page.update()
