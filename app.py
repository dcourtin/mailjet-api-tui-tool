from __future__ import annotations

import re
import csv
import json
import sqlite3
from pathlib import Path
from datetime import datetime

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Header, Footer, Input, Select, Button, DataTable, Label, Static

from textual_plotext import PlotextPlot

from mailjet_api import MailjetAPI, MESSAGE_STATES
from accounts_db import AccountsDB


class MetricsPlot(PlotextPlot):
    def update_data(self, data, date_label: str = ''):
        hours = [f"{i:02}h" for i in range(24)]
        counts = [0] * 24

        for d in data:
            time_str = d.get('time', '')
            if not time_str:
                continue
            try:
                dt_utc = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                dt_local = dt_utc.astimezone()
                hour = dt_local.hour
                if 0 <= hour <= 23:
                    counts[hour] += 1
            except Exception:
                pass

        self.plt.clear_figure()
        self.plt.bar(hours, counts, color="blue")
        title = f"Envois par Heure — {date_label}" if date_label else "Envois par Heure (Aujourd'hui)"
        self.plt.title(title)
        self.plt.ylabel("Nombre")
        self.refresh()


class AccountManagerScreen(ModalScreen):
    """Modal de gestion des comptes Mailjet."""

    BINDINGS = [("escape", "dismiss_modal", "Fermer")]

    DEFAULT_CSS = """
    AccountManagerScreen {
        align: center middle;
    }
    #modal-container {
        width: 90;
        height: 90%;
        background: $surface;
        border: thick $primary;
        padding: 0;
    }
    #modal-scroll {
        width: 1fr;
        height: 1fr;
        padding: 1 2;
    }
    #modal-title {
        text-style: bold;
        margin-bottom: 1;
    }
    #accounts-table {
        height: 8;
        margin-bottom: 1;
    }
    .modal-label {
        margin-top: 1;
    }
    #modal-error {
        color: $error;
        height: 1;
    }
    #modal-actions {
        margin-top: 1;
        height: auto;
    }
    """

    def __init__(self, db: AccountsDB) -> None:
        super().__init__()
        self.db = db
        self._selected_account_id: int | None = None
        # map row_key -> account_id
        self._row_to_account: dict[str, int] = {}

    def action_dismiss_modal(self) -> None:
        self.dismiss(True)

    def compose(self) -> ComposeResult:
        with Vertical(id="modal-container"):
            with VerticalScroll(id="modal-scroll"):
                yield Label("Gestion des Comptes Mailjet", id="modal-title")
                yield DataTable(id="accounts-table", cursor_type="row")
                yield Label("Nom du compte", classes="modal-label")
                yield Input(placeholder="Production", id="input-name")
                yield Label("API Key", classes="modal-label")
                yield Input(placeholder="...", id="input-key")
                yield Label("API Secret", classes="modal-label")
                yield Input(placeholder="...", password=True, id="input-secret")
                yield Static("", id="modal-error")
                with Horizontal(id="modal-actions"):
                    yield Button("Ajouter", variant="primary", id="btn-add")
                    yield Button("Modifier", variant="warning", id="btn-update")
                    yield Button("Supprimer", variant="error", id="btn-delete")
                    yield Button("Fermer", variant="default", id="btn-close")

    def on_mount(self) -> None:
        table = self.query_one("#accounts-table", DataTable)
        table.add_columns("Nom", "Clé API")
        self._refresh_table()

    def _refresh_table(self) -> None:
        table = self.query_one("#accounts-table", DataTable)
        table.clear()
        self._row_to_account = {}
        self._selected_account_id = None
        for acc in self.db.get_all_accounts():
            key = str(acc["id"])
            table.add_row(acc["name"], acc["api_key"][:8] + "...", key=key)
            self._row_to_account[key] = acc["id"]

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        account_id = self._row_to_account.get(str(event.row_key.value))
        self._selected_account_id = account_id
        if account_id is None:
            return
        acc = self.db.get_account_by_id(account_id)
        if acc:
            self.query_one("#input-name", Input).value = acc["name"]
            self.query_one("#input-key", Input).value = acc["api_key"]
            self.query_one("#input-secret", Input).value = acc["api_secret"]
            self._set_error("")

    def _set_error(self, msg: str) -> None:
        self.query_one("#modal-error", Static).update(msg)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-close":
            self.dismiss(True)
        elif event.button.id == "btn-add":
            self._handle_add()
        elif event.button.id == "btn-update":
            self._handle_update()
        elif event.button.id == "btn-delete":
            self._handle_delete()

    def _handle_add(self) -> None:
        name = self.query_one("#input-name", Input).value.strip()
        key = self.query_one("#input-key", Input).value.strip()
        secret = self.query_one("#input-secret", Input).value.strip()

        if not name or not key or not secret:
            self._set_error("Tous les champs sont obligatoires.")
            return

        if self.db.account_name_exists(name):
            self._set_error(f"Un compte nommé « {name} » existe déjà.")
            return

        try:
            self.db.add_account(name, key, secret)
        except sqlite3.IntegrityError:
            self._set_error("Ce nom est déjà utilisé.")
            return

        self.query_one("#input-name", Input).value = ""
        self.query_one("#input-key", Input).value = ""
        self.query_one("#input-secret", Input).value = ""
        self._selected_account_id = None
        self._set_error("")
        self._refresh_table()

    def _handle_update(self) -> None:
        if self._selected_account_id is None:
            self._set_error("Sélectionnez d'abord un compte dans la liste.")
            return

        name = self.query_one("#input-name", Input).value.strip()
        key = self.query_one("#input-key", Input).value.strip()
        secret = self.query_one("#input-secret", Input).value.strip()

        if not name or not key or not secret:
            self._set_error("Tous les champs sont obligatoires.")
            return

        try:
            self.db.update_account(self._selected_account_id, name, key, secret)
        except sqlite3.IntegrityError:
            self._set_error("Ce nom est déjà utilisé par un autre compte.")
            return

        self._set_error("")
        self._refresh_table()

    def _handle_delete(self) -> None:
        if self._selected_account_id is None:
            self._set_error("Sélectionnez d'abord un compte dans la liste.")
            return

        self.db.delete_account(self._selected_account_id)
        self._set_error("")
        self._refresh_table()


class MailjetApp(App):
    TITLE = "Mailjet TUI Dashboard"
    CSS = """
    Screen {
        layout: horizontal;
    }

    #sidebar {
        width: 35;
        height: 100%;
        dock: left;
        padding: 1;
        background: $boost;
        border-right: vkey $primary;
    }

    #main_area {
        width: 1fr;
        height: 100%;
        layout: vertical;
        padding: 0 1;
    }

    .filter-label {
        margin-top: 1;
        margin-bottom: 1;
        text-style: bold;
    }

    Input, Select, Button {
        margin-bottom: 1;
    }

    #sidebar Button {
        width: 100%;
        margin-top: 1;
    }

    DataTable {
        height: 2fr;
        border: solid $accent;
        margin-bottom: 1;
    }

    #stats-bar {
        height: auto;
        padding: 0 1;
        margin-bottom: 1;
        background: $boost;
        border: solid $primary;
        color: $text;
    }

    MetricsPlot {
        height: 1fr;
        min-height: 15;
        border: solid $accent;
    }

    #credentials-warning {
        display: none;
        padding: 1;
        background: $error;
        color: white;
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quitter"),
        ("r", "refresh_data", "Rafraîchir"),
    ]

    def __init__(self):
        super().__init__()
        self.db = AccountsDB()
        accounts = self.db.get_all_accounts()
        first = accounts[0] if accounts else None
        self._active_account_id: int | None = first["id"] if first else None
        self.api = self._make_api(first)
        self._current_data: list = []

    def _make_api(self, account: dict | None) -> MailjetAPI:
        if account:
            return MailjetAPI(api_key=account["api_key"], api_secret=account["api_secret"])
        return MailjetAPI()

    def _build_account_options(self) -> list[tuple[str, int]]:
        return [(acc["name"], acc["id"]) for acc in self.db.get_all_accounts()]

    def compose(self) -> ComposeResult:
        yield Header()

        with VerticalScroll(id="sidebar"):
            yield Label("MODE MOCK — Aucun compte configuré", id="credentials-warning")

            yield Label("Compte actif", classes="filter-label")
            yield Select(
                self._build_account_options(),
                value=self._active_account_id if self._active_account_id is not None else Select.NULL,
                allow_blank=True,
                prompt="— Aucun compte —",
                id="account-select",
            )
            yield Button("Gérer comptes", variant="default", id="btn-manage-accounts")

            yield Label("Statut", classes="filter-label")
            status_options = [("Tous", "All")] + [(v, v) for v in MESSAGE_STATES.values()]
            yield Select(status_options, value="All", id="filter-status")

            yield Label("Date début (AAAA-MM-JJ)", classes="filter-label")
            today = datetime.now().strftime("%Y-%m-%d")
            yield Input(placeholder=today, value=today, id="filter-date")
            yield Label("Date fin (optionnel)", classes="filter-label")
            yield Input(placeholder=today, id="filter-date-end")

            yield Label("Émetteur (Sender)", classes="filter-label")
            yield Input(placeholder="contact@example.com", id="filter-sender")

            yield Label("Destinataire (Recipient)", classes="filter-label")
            yield Input(placeholder="client@...", id="filter-recipient")

            yield Button("Appliquer les filtres", variant="primary", id="btn-apply")

            yield Label("Format export", classes="filter-label")
            yield Select([("CSV", "csv"), ("JSON", "json")], value="csv", id="export-format")
            yield Button("Exporter", variant="success", id="btn-export")

        with Vertical(id="main_area"):
            yield DataTable(id="emails-table")
            yield Static("", id="stats-bar")
            yield MetricsPlot(id="chart-plot")

        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Date/Heure", "Émetteur", "Destinataire", "Statut", "Sujet")
        self._update_mock_warning()
        self.action_refresh_data()

    def _update_mock_warning(self) -> None:
        warning = self.query_one("#credentials-warning", Label)
        warning.display = not self.api.has_credentials

    def on_select_changed(self, event: Select.Changed) -> None:
        if event.select.id != "account-select":
            return
        if event.value is Select.NULL or event.value == self._active_account_id:
            return
        self._switch_account(event.value)

    def _switch_account(self, account_id: int) -> None:
        self._active_account_id = account_id
        account = self.db.get_account_by_id(account_id)
        self.api = self._make_api(account)
        self._update_mock_warning()
        self.action_refresh_data()
        name = account["name"] if account else "inconnu"
        self.notify(f"Compte actif : {name}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-apply":
            self.action_refresh_data()
        elif event.button.id == "btn-export":
            self.action_export()
        elif event.button.id == "btn-manage-accounts":
            self.push_screen(AccountManagerScreen(self.db), self._on_accounts_changed)

    def _on_accounts_changed(self, _changed: bool) -> None:
        accounts = self.db.get_all_accounts()
        options = [(acc["name"], acc["id"]) for acc in accounts]
        selector = self.query_one("#account-select", Select)
        selector.set_options(options)

        if not accounts:
            self._active_account_id = None
            self.api = self._make_api(None)
            self._update_mock_warning()
            self.action_refresh_data()
            self.notify("Aucun compte — mode mock activé", severity="warning")
            return

        valid_ids = {acc["id"] for acc in accounts}
        if self._active_account_id not in valid_ids:
            first = accounts[0]
            self._active_account_id = first["id"]
            self.api = self._make_api(first)
            self._update_mock_warning()
            self.action_refresh_data()
            self.notify(f"Compte précédent supprimé. Basculé sur : {first['name']}", severity="warning")
        else:
            # Recharger l'API — les credentials ont pu être modifiés
            account = self.db.get_account_by_id(self._active_account_id)
            self.api = self._make_api(account)
            selector.value = self._active_account_id
            self._update_mock_warning()
            self.action_refresh_data()

    def action_refresh_data(self) -> None:
        status = self.query_one("#filter-status", Select).value
        date_val = self.query_one("#filter-date", Input).value.strip()
        date_end_val = self.query_one("#filter-date-end", Input).value.strip()
        sender = self.query_one("#filter-sender", Input).value
        recipient = self.query_one("#filter-recipient", Input).value

        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_val):
            date_val = datetime.now().strftime("%Y-%m-%d")

        if not re.match(r'^\d{4}-\d{2}-\d{2}$', date_end_val):
            date_end_val = None

        data = self.api.get_messages(limit=300, status=status, sender=sender, recipient=recipient, date_filter=date_val, date_end=date_end_val)
        self._current_data = data

        table = self.query_one(DataTable)
        table.clear()

        for d in data:
            time_display = d.get('time', '')
            if time_display:
                try:
                    dt_utc = datetime.fromisoformat(time_display.replace('Z', '+00:00'))
                    dt_local = dt_utc.astimezone()
                    time_display = dt_local.strftime("%d/%m %H:%M:%S")
                except Exception:
                    if 'T' in time_display:
                        time_display = time_display.split('T')[1].split('Z')[0].split('+')[0]
                        if '.' in time_display:
                            time_display = time_display.split('.')[0]

            table.add_row(
                time_display,
                d.get('sender', ''),
                d.get('recipient', ''),
                d.get('status', ''),
                d.get('subject', '') or '—'
            )

        self._update_stats(data)
        plot = self.query_one(MetricsPlot)
        plot.update_data(data, date_label=date_val)

    def _update_stats(self, data: list) -> None:
        stats_bar = self.query_one("#stats-bar", Static)
        total = len(data)
        if total == 0:
            stats_bar.update("Aucun message dans la sélection.")
            return

        counts: dict[str, int] = {}
        for d in data:
            s = d.get("status", "Unknown")
            counts[s] = counts.get(s, 0) + 1

        parts = [f"[bold]{total} message{'s' if total > 1 else ''}[/bold]"]
        for status, count in sorted(counts.items(), key=lambda x: -x[1]):
            pct = count / total * 100
            parts.append(f"{status}: {count} ({pct:.0f}%)")

        stats_bar.update("  ·  ".join(parts))

    def action_export(self) -> None:
        if not self._current_data:
            self.notify("Aucune donnée à exporter", severity="warning")
            return

        fmt = self.query_one("#export-format", Select).value
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        export_dir = Path(__file__).parent / "exports"
        export_dir.mkdir(exist_ok=True)
        filename = export_dir / f"mailjet_export_{timestamp}.{fmt}"
        fields = ["time", "sender", "recipient", "status", "subject"]

        try:
            if fmt == "csv":
                with open(filename, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
                    writer.writeheader()
                    writer.writerows(self._current_data)
            else:
                with open(filename, "w", encoding="utf-8") as f:
                    json.dump(
                        [{k: d.get(k, "") for k in fields} for d in self._current_data],
                        f, indent=2, ensure_ascii=False
                    )
            self.notify(f"Exporté : {filename}")
        except Exception as e:
            self.notify(f"Erreur export : {e}", severity="error")


if __name__ == "__main__":
    app = MailjetApp()
    app.run()
