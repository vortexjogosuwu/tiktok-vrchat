"""
gui/app.py

Janela principal do TikTok LIVE -> VRChat OSC Bridge.

Organizada em duas abas:
- "Presentes": criar/editar/testar os presentes do TikTok.
- "Conjuntos de roupa": criar/editar/testar conjuntos reutilizáveis de
  peças, e escolher qual deles é a roupa padrão (revert global) -- tudo
  num só lugar, sem precisar abrir outra janela.

Os controles de conexão, as ações rápidas (voltar pra padrão / pânico)
e o log ficam sempre visíveis, fora das abas, porque são usados sempre
independente do que você está editando.
"""

from __future__ import annotations

import asyncio
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Optional

from config.loader import AppConfig, ConfigError, load_config, load_raw, parse_gift_rule, save_raw
from gui.dialogs import AvatarParametersDialog, GiftEditDialog, LiveParametersDialog, OutfitEditDialog, QueueStatusDialog, TargetEditDialog
from handlers.gifts import GiftHandler
from tiktok.listener import TikTokGiftListener
import utils_log
from vrchat.osc import VRChatOSC, send_target_sequence

DEFAULT_CONFIG_PATH = "config.yaml"

STATUS_LABELS = {
    "idle": ("Desconectado", "#888888"),
    "connecting": ("Conectando...", "#c98a00"),
    "connected": ("Conectado", "#1a8a1a"),
    "disconnected": ("Desconectado (tentando reconectar)", "#c98a00"),
    "stopped": ("Desconectado", "#888888"),
}


class App(tk.Tk):
    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH) -> None:
        super().__init__()
        self.title("TikTok LIVE -> VRChat OSC Bridge")
        self.geometry("820x600")
        self.minsize(700, 500)

        self.config_path = config_path
        self.gui_queue: "queue.Queue[tuple[str, Any]]" = queue.Queue()

        self.app_config: Optional[AppConfig] = None
        self.raw_config: dict[str, Any] = {}
        self.osc_client: Optional[VRChatOSC] = None
        self.gift_handler: Optional[GiftHandler] = None
        self.listener: Optional[TikTokGiftListener] = None
        self.connected = False

        # Loop assíncrono ÚNICO e permanente, rodando numa thread separada
        # durante toda a vida do programa -- não só enquanto conectado à
        # LIVE. É nele que a fila de presentes com duração roda, então
        # testar um presente funciona igual, esteja você conectado ou não.
        self.async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_loop_ready = threading.Event()
        self.async_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.async_thread.start()
        self._async_loop_ready.wait(timeout=5)

        utils_log.add_sink(self._on_log_from_any_thread)

        self._build_widgets()
        self._load_config_into_ui(initial=True)

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(100, self._poll_queue)

    def _run_async_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self.async_loop = loop
        self._async_loop_ready.set()
        loop.run_forever()

    # ------------------------------------------------------------------ #
    # Construcao da interface
    # ------------------------------------------------------------------ #
    def _build_widgets(self) -> None:
        # --- Conexão (sempre visível) -----------------------------------
        top = ttk.Frame(self, padding=10)
        top.pack(fill="x")

        ttk.Label(top, text="Canal TikTok (@):").grid(row=0, column=0, sticky="w")
        self.username_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.username_var, width=20).grid(
            row=0, column=1, padx=(4, 16)
        )

        ttk.Label(top, text="OSC Host:").grid(row=0, column=2, sticky="w")
        self.host_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.host_var, width=14).grid(
            row=0, column=3, padx=(4, 16)
        )

        ttk.Label(top, text="OSC Port:").grid(row=0, column=4, sticky="w")
        self.port_var = tk.StringVar()
        ttk.Entry(top, textvariable=self.port_var, width=8).grid(
            row=0, column=5, padx=(4, 16)
        )

        self.connect_btn = ttk.Button(top, text="Conectar na LIVE", command=self._on_connect)
        self.connect_btn.grid(row=0, column=6, padx=4)
        self.disconnect_btn = ttk.Button(
            top, text="Desconectar", command=self._on_disconnect, state="disabled"
        )
        self.disconnect_btn.grid(row=0, column=7, padx=4)

        status_frame = ttk.Frame(self, padding=(10, 0))
        status_frame.pack(fill="x")
        ttk.Label(status_frame, text="Status:").pack(side="left")
        self.status_label = ttk.Label(status_frame, text="Desconectado", foreground="#888888")
        self.status_label.pack(side="left", padx=(4, 0))

        # --- Ações rápidas / globais (sempre visíveis) -------------------
        actions_frame = ttk.Frame(self, padding=(10, 6))
        actions_frame.pack(fill="x")
        ttk.Button(
            actions_frame, text="Voltar para roupa padrão", command=self._on_revert_to_default,
        ).pack(side="left", padx=2)
        ttk.Button(
            actions_frame, text="Ver fila...", command=self._on_show_queue
        ).pack(side="left", padx=(8, 2))
        ttk.Button(
            actions_frame, text="Limpar fila", command=self._on_clear_queue
        ).pack(side="left", padx=2)
        panic_btn = tk.Button(
            actions_frame, text="🚨 PÂNICO", command=self._on_panic,
            background="#c22", foreground="white", activebackground="#a11",
            activeforeground="white",
        )
        panic_btn.pack(side="left", padx=(8, 2))
        ttk.Button(
            actions_frame, text="Parâmetros do avatar...", command=self._on_show_avatar_parameters
        ).pack(side="left", padx=(16, 2))
        ttk.Button(
            actions_frame, text="Descobrir valores ao vivo...", command=self._on_show_live_parameters
        ).pack(side="left", padx=2)
        ttk.Button(
            actions_frame, text="Salvar configuração", command=self._on_save_config
        ).pack(side="right", padx=2)

        # --- Abas: Presentes / Conjuntos de roupa -------------------------
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=10, pady=(0, 4))

        gifts_tab = ttk.Frame(notebook)
        outfits_tab = ttk.Frame(notebook)
        notebook.add(gifts_tab, text="Recompensas")
        notebook.add(outfits_tab, text="Conjuntos de roupa")

        self._build_gifts_tab(gifts_tab)
        self._build_outfits_tab(outfits_tab)

        # --- Log (sempre visível, embaixo das abas) -----------------------
        log_frame = ttk.LabelFrame(self, text="Log", padding=6)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        self.log_text = tk.Text(log_frame, height=9, state="disabled", wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="left", fill="y")

        self.log_text.tag_configure("TIKTOK", foreground="#1a5aa8")
        self.log_text.tag_configure("OSC", foreground="#1a8a1a")
        self.log_text.tag_configure("ERROR", foreground="#c22")

    def _build_gifts_tab(self, parent: ttk.Frame) -> None:
        list_frame = ttk.LabelFrame(parent, text="Recompensas configuradas", padding=8)
        list_frame.pack(fill="both", expand=True, padx=6, pady=(6, 4))

        columns = ("recompensa", "presentes", "ativo", "conjunto", "fila", "duracao", "alvos")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("recompensa", text="Recompensa")
        self.tree.heading("presentes", text="Presentes")
        self.tree.heading("ativo", text="Ativo?")
        self.tree.heading("conjunto", text="Conjunto")
        self.tree.heading("fila", text="Fila")
        self.tree.heading("duracao", text="Duração")
        self.tree.heading("alvos", text="Itens")
        self.tree.column("recompensa", width=110)
        self.tree.column("presentes", width=130)
        self.tree.column("ativo", width=55, anchor="center")
        self.tree.column("conjunto", width=85, anchor="center")
        self.tree.column("fila", width=65, anchor="center")
        self.tree.column("duracao", width=70, anchor="center")
        self.tree.column("alvos", width=220)
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self._on_edit_gift())

        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="left", fill="y")

        btns_frame = ttk.Frame(parent, padding=(6, 0))
        btns_frame.pack(fill="x")
        ttk.Button(btns_frame, text="Nova recompensa", command=self._on_new_gift).pack(
            side="left", padx=2
        )
        ttk.Button(btns_frame, text="Editar recompensa", command=self._on_edit_gift).pack(
            side="left", padx=2
        )
        ttk.Button(btns_frame, text="Remover recompensa", command=self._on_remove_gift).pack(
            side="left", padx=2
        )
        ttk.Button(
            btns_frame, text="Ativar/Desativar", command=self._on_toggle_gift_enabled
        ).pack(side="left", padx=(12, 2))
        ttk.Button(
            btns_frame, text="Testar (Completo)", command=self._on_test_gift_full
        ).pack(side="left", padx=(12, 2))
        ttk.Button(
            btns_frame, text="Testar (Aplicar)", command=self._on_test_gift_apply_only
        ).pack(side="left", padx=2)

    def _build_outfits_tab(self, parent: ttk.Frame) -> None:
        list_frame = ttk.LabelFrame(parent, text="Conjuntos de roupa", padding=8)
        list_frame.pack(fill="both", expand=True, padx=6, pady=(6, 4))

        columns = ("padrao", "nome", "pecas")
        self.outfits_tree = ttk.Treeview(
            list_frame, columns=columns, show="headings", selectmode="browse"
        )
        self.outfits_tree.heading("padrao", text="Padrão?")
        self.outfits_tree.heading("nome", text="Conjunto")
        self.outfits_tree.heading("pecas", text="Peças")
        self.outfits_tree.column("padrao", width=60, anchor="center")
        self.outfits_tree.column("nome", width=140)
        self.outfits_tree.column("pecas", width=420)
        self.outfits_tree.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.outfits_tree.yview)
        self.outfits_tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="left", fill="y")

        btns_frame = ttk.Frame(parent, padding=(6, 0))
        btns_frame.pack(fill="x")
        ttk.Button(btns_frame, text="Novo conjunto", command=self._on_new_outfit).pack(
            side="left", padx=2
        )
        ttk.Button(btns_frame, text="Editar conjunto", command=self._on_edit_outfit).pack(
            side="left", padx=2
        )
        ttk.Button(btns_frame, text="Remover conjunto", command=self._on_remove_outfit).pack(
            side="left", padx=2
        )
        ttk.Button(
            btns_frame, text="Testar conjunto (completo)", command=self._on_test_outfit
        ).pack(side="left", padx=(12, 2))
        ttk.Button(
            btns_frame, text="★ Definir como roupa padrão", command=self._on_set_default_outfit
        ).pack(side="left", padx=(12, 2))

    # ------------------------------------------------------------------ #
    # Carregar/preencher a partir do config.yaml
    # ------------------------------------------------------------------ #
    def _load_config_into_ui(self, initial: bool = False) -> None:
        try:
            self.app_config = load_config(self.config_path)
            self.raw_config = load_raw(self.config_path)
        except ConfigError as exc:
            if initial:
                messagebox.showerror(
                    "Erro ao carregar config.yaml",
                    f"{exc}\n\nVerifique o arquivo config.yaml antes de continuar.",
                )
            else:
                messagebox.showerror("Erro ao carregar config.yaml", str(exc))
            return

        # O objeto AppConfig é recriado do zero a cada load. Se já existia
        # um GiftHandler (do teste ou da conexão), ele estava apontando
        # para o AppConfig antigo -- descarta pra recriar com o novo na
        # próxima vez que for preciso (teste ou nova conexão).
        self.gift_handler = None

        self.username_var.set(self.app_config.tiktok_username)
        self.host_var.set(self.app_config.osc_host)
        self.port_var.set(str(self.app_config.osc_port))

        for warning in self.app_config.warnings:
            utils_log.log_error(f"[CONFIG] {warning}")

        self._refresh_all_trees()
        self._ensure_osc_client()

    def _refresh_all_trees(self) -> None:
        self._refresh_gifts_tree()
        self._refresh_outfits_tree()

    def _refresh_gifts_tree(self) -> None:
        previously_selected = self.tree.selection()
        self.tree.delete(*self.tree.get_children())
        if not self.app_config:
            return
        for gift_name, rule in self.app_config.gifts.items():
            duration_label = "-"
            if rule.duration_seconds is not None:
                if rule.duration_seconds < 60:
                    seconds = rule.duration_seconds
                    duration_label = (
                        f"{int(seconds)}s" if seconds == int(seconds) else f"{seconds:.1f}s"
                    )
                else:
                    minutes = rule.duration_seconds / 60
                    duration_label = (
                        f"{int(minutes)} min" if minutes == int(minutes) else f"{minutes:.1f} min"
                    )
            targets_summary = ", ".join(
                f"{t.address.rsplit('/', 1)[-1]}={t.value!r}" for t in rule.targets
            )
            alvos_label = f"({len(rule.targets)}) {targets_summary}" if rule.targets else "(0)"
            fila_label = "ignora" if (rule.duration_seconds is not None and rule.ignore_queue) else "-"
            presentes_label = ", ".join(rule.trigger_gift_names)
            self.tree.insert(
                "", "end", iid=gift_name,
                values=(
                    gift_name, presentes_label, "Sim" if rule.enabled else "Não",
                    rule.outfit_name or "-", fila_label, duration_label, alvos_label,
                ),
                tags=() if rule.enabled else ("disabled",),
            )
        self.tree.tag_configure("disabled", foreground="#999999")
        # Restaura a seleção anterior, se o presente ainda existir (ex:
        # depois de ativar/desativar), pra não perder o que estava marcado.
        still_present = [iid for iid in previously_selected if self.tree.exists(iid)]
        if still_present:
            self.tree.selection_set(still_present)

    def _refresh_outfits_tree(self) -> None:
        previously_selected = self.outfits_tree.selection()
        self.outfits_tree.delete(*self.outfits_tree.get_children())
        default_name = self.app_config.default_revert_outfit_name if self.app_config else None
        for name, items in self._current_outfits_raw().items():
            pieces = ", ".join(
                f"{t.get('parameter') or t.get('address')}={t.get('value')!r}" for t in items
            )
            self.outfits_tree.insert(
                "", "end", iid=name,
                values=("★" if name == default_name else "", name, pieces),
            )
        still_present = [iid for iid in previously_selected if self.outfits_tree.exists(iid)]
        if still_present:
            self.outfits_tree.selection_set(still_present)

    # ------------------------------------------------------------------ #
    # OSC (teste manual, independente do TikTok estar conectado)
    # ------------------------------------------------------------------ #
    def _ensure_osc_client(self) -> None:
        host = self.host_var.get().strip() or "127.0.0.1"
        try:
            port = int(self.port_var.get().strip() or "9000")
        except ValueError:
            port = 9000

        if self.osc_client is None or self.osc_client.host != host or self.osc_client.port != port:
            self.osc_client = VRChatOSC(host=host, port=port)
            # Se o host/porta mudou, o handler antigo estava apontando pro
            # cliente OSC velho -- descarta pra recriar com o novo.
            self.gift_handler = None

    def _ensure_gift_handler(self) -> GiftHandler:
        """
        Cria (uma única vez, reaproveitando depois) o GiftHandler que
        processa presentes -- usado tanto pela conexão real com o TikTok
        quanto pelos botões de teste. Isso garante que testar funciona
        exatamente como a LIVE de verdade funcionaria (mesma fila, mesmo
        revert), com ou sem estar conectado.
        """
        self._ensure_osc_client()
        assert self.app_config is not None
        if self.gift_handler is None:
            self.gift_handler = GiftHandler(config=self.app_config, osc_client=self.osc_client)  # type: ignore[arg-type]
        return self.gift_handler

    def _on_test_gift_full(self) -> None:
        """
        Testa a recompensa inteira como se um presente tivesse chegado
        de verdade pela LIVE: aplica os alvos, espera a duração (se
        houver) e reverte -- tudo isso funciona COM ou SEM estar
        conectado ao TikTok, porque roda no mesmo loop assíncrono
        permanente do programa. Testa pelo NOME DA RECOMPENSA
        diretamente (não pelo nome de um presente-gatilho), já que os
        dois podem ser diferentes.
        """
        reward_name = self._selected_gift_name()
        if reward_name is None:
            messagebox.showinfo("Nada selecionado", "Selecione uma recompensa na lista.")
            return
        if self.async_loop is None:
            messagebox.showerror("Erro interno", "O loop assíncrono não está pronto ainda.")
            return

        gift_handler = self._ensure_gift_handler()

        async def _run() -> None:
            await gift_handler.test_reward(reward_name, "Teste manual", 1)

        asyncio.run_coroutine_threadsafe(_run(), self.async_loop)

    def _on_revert_to_default(self) -> None:
        """Troca para a roupa padrão AGORA, sem mexer na fila -- funciona
        com ou sem estar conectado à LIVE."""
        if self.async_loop is None:
            messagebox.showerror("Erro interno", "O loop assíncrono não está pronto ainda.")
            return
        gift_handler = self._ensure_gift_handler()

        async def _run() -> None:
            await gift_handler.revert_to_default()

        asyncio.run_coroutine_threadsafe(_run(), self.async_loop)

    def _on_panic(self) -> None:
        """PÂNICO: pede confirmação, limpa a fila inteira (e os presentes
        paralelos ativos) e volta pra roupa padrão imediatamente."""
        if not messagebox.askyesno(
            "Limpar fila de presentes?",
            "Isso vai cancelar TODOS os presentes com duração que estejam "
            "ativos ou esperando na fila (inclusive os que rodam em paralelo), "
            "e trocar para a roupa padrão imediatamente.\n\nContinuar?",
        ):
            return
        if self.async_loop is None:
            messagebox.showerror("Erro interno", "O loop assíncrono não está pronto ainda.")
            return
        gift_handler = self._ensure_gift_handler()

        async def _run():
            return await gift_handler.panic()

        future = asyncio.run_coroutine_threadsafe(_run(), self.async_loop)

        def _report():
            try:
                queue_cleared, independent_cleared = future.result(timeout=5)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Erro no pânico", str(exc))
                return
            total = queue_cleared + independent_cleared
            messagebox.showinfo(
                "Pânico concluído",
                f"{total} recompensa(s) cancelada(s) "
                f"({queue_cleared} da fila, {independent_cleared} em paralelo).\n"
                f"Roupa padrão aplicada.",
            )

        self.after(100, _report)

    def _on_show_queue(self) -> None:
        gift_handler = self._ensure_gift_handler()

        def get_status():
            return gift_handler.timed_queue.current_snapshot(), gift_handler.timed_queue.pending_snapshot()

        def on_clear():
            self._clear_queue_and_report(show_dialog_after=True)

        QueueStatusDialog(self, get_status=get_status, on_clear=on_clear)

    def _on_clear_queue(self) -> None:
        if not messagebox.askyesno(
            "Limpar fila?",
            "Isso cancela a recompensa ativa e todas as que estão esperando na "
            "fila (sem reverter pra roupa padrão automaticamente — se quiser "
            "isso também, use o botão PÂNICO).\n\nContinuar?",
        ):
            return
        self._clear_queue_and_report(show_dialog_after=False)

    def _clear_queue_and_report(self, show_dialog_after: bool) -> None:
        if self.async_loop is None:
            messagebox.showerror("Erro interno", "O loop assíncrono não está pronto ainda.")
            return
        gift_handler = self._ensure_gift_handler()

        async def _run():
            return await gift_handler.timed_queue.panic_clear()

        future = asyncio.run_coroutine_threadsafe(_run(), self.async_loop)

        def _report():
            try:
                cleared = future.result(timeout=5)
            except Exception as exc:  # noqa: BLE001
                messagebox.showerror("Erro ao limpar a fila", str(exc))
                return
            messagebox.showinfo("Fila limpa", f"{cleared} recompensa(s) removida(s) da fila.")

        self.after(100, _report)

    def _test_raw_target(self, raw_target: dict[str, Any]) -> None:
        """Valida e envia um alvo isolado (usado pelos dialogos de edicao)."""
        self._ensure_osc_client()
        rule, warnings = parse_gift_rule("_teste_", raw_target)
        for warning in warnings:
            utils_log.log_error(f"[CONFIG] {warning}")
        for target in rule.targets:
            assert self.osc_client is not None
            self.osc_client.send(target.address, target.value)

    def _on_test_gift_apply_only(self) -> None:
        """
        Testar (Aplicar): aplica TODOS os itens do presente selecionado
        agora, só para teste -- NÃO entra na fila, NÃO conta duração e
        NÃO reverte para a roupa padrão depois. Serve só pra conferir
        se todos os itens do presente aplicam corretamente, sem afetar
        a fila nem o estado normal do sistema.
        """
        gift_name = self._selected_gift_name()
        if gift_name is None:
            messagebox.showinfo("Nada selecionado", "Selecione uma recompensa na lista.")
            return
        if self.async_loop is None:
            messagebox.showerror("Erro interno", "O loop assíncrono não está pronto ainda.")
            return

        self._ensure_osc_client()
        assert self.app_config is not None
        rule = self.app_config.gifts.get(gift_name)
        if rule is None:
            return
        osc_client = self.osc_client

        async def _run() -> None:
            utils_log.log_tiktok(
                f"Testando '{gift_name}' (aplicar apenas -- sem fila, sem revert)..."
            )
            await send_target_sequence(osc_client, rule.targets)

        asyncio.run_coroutine_threadsafe(_run(), self.async_loop)

    # ------------------------------------------------------------------ #
    # CRUD de presentes (editando self.raw_config["gifts"])
    # ------------------------------------------------------------------ #
    def _current_gift_names(self) -> set[str]:
        return set((self.raw_config.get("gifts") or {}).keys())

    def _current_outfits_raw(self) -> dict[str, Any]:
        return self.raw_config.get("outfits") or {}

    @staticmethod
    def _build_raw_gift(result: dict[str, Any]) -> dict[str, Any]:
        raw_gift: dict[str, Any] = {"gift_names": result["gift_names"]}
        if result["outfit"]:
            raw_gift["outfit"] = result["outfit"]
        extra_targets = result["extra_targets"]
        if len(extra_targets) > 1:
            raw_gift["parameters"] = extra_targets
        elif len(extra_targets) == 1:
            raw_gift.update(extra_targets[0])
        if not result.get("enabled", True):
            raw_gift["enabled"] = False
        if result["duration_value"] is not None:
            if result["duration_unit"] == "segundos":
                raw_gift["duration_seconds"] = result["duration_value"]
            else:
                raw_gift["duration_minutes"] = result["duration_value"]
            if result.get("ignore_queue"):
                raw_gift["ignore_queue"] = True
        if result["revert_outfit"]:
            raw_gift["revert_outfit"] = result["revert_outfit"]
        if result["revert_extra_targets"]:
            raw_gift["revert"] = result["revert_extra_targets"]
        return raw_gift

    def _on_new_gift(self) -> None:
        dlg = GiftEditDialog(
            self, on_test_target=self._test_raw_target,
            outfits_raw=self._current_outfits_raw(),
            existing_names=self._current_gift_names(),
            username=self.username_var.get().strip(),
        )
        self.wait_window(dlg)
        if dlg.result is None:
            return
        raw_gift = self._build_raw_gift(dlg.result)
        self.raw_config.setdefault("gifts", {})[dlg.result["name"]] = raw_gift
        self._reload_app_config_from_raw()

    def _on_edit_gift(self) -> None:
        gift_name = self._selected_gift_name()
        if gift_name is None:
            messagebox.showinfo("Nada selecionado", "Selecione uma recompensa na lista.")
            return

        raw_gift = (self.raw_config.get("gifts") or {}).get(gift_name, {})
        outfit_name = raw_gift.get("outfit")
        excluded_keys = (
            "duration_minutes", "duration_seconds", "revert", "revert_outfit",
            "outfit", "enabled", "ignore_queue", "gift_names",
        )
        if raw_gift.get("parameters"):
            extra_targets = raw_gift["parameters"]
        elif "parameter" in raw_gift or "address" in raw_gift:
            extra_targets = [
                {k: v for k, v in raw_gift.items() if k not in excluded_keys}
            ]
        else:
            extra_targets = []

        # Retrocompatível: se não houver 'gift_names' explícito, o
        # próprio nome da recompensa é o único presente-gatilho.
        trigger_gift_names = raw_gift.get("gift_names") or [gift_name]

        # Preserva a unidade original (minutos/segundos) que foi usada
        # ao salvar, em vez de sempre converter para minutos -- assim
        # editar um presente com "duration_seconds: 6" continua
        # mostrando "6 segundos", não "0.1 minutos".
        if raw_gift.get("duration_seconds") is not None:
            duration_value = float(raw_gift["duration_seconds"])
            duration_unit = "segundos"
        elif raw_gift.get("duration_minutes") is not None:
            duration_value = float(raw_gift["duration_minutes"])
            duration_unit = "minutos"
        else:
            duration_value = None
            duration_unit = "minutos"

        dlg = GiftEditDialog(
            self, on_test_target=self._test_raw_target,
            outfits_raw=self._current_outfits_raw(),
            gift_name=gift_name, trigger_gift_names=trigger_gift_names,
            outfit_name=outfit_name, extra_targets=extra_targets,
            duration_value=duration_value, duration_unit=duration_unit,
            revert_outfit_name=raw_gift.get("revert_outfit"),
            revert_extra_targets=raw_gift.get("revert") or [],
            enabled=raw_gift.get("enabled", True),
            ignore_queue=raw_gift.get("ignore_queue", False),
            existing_names=self._current_gift_names(),
            editing_original_name=gift_name,
            username=self.username_var.get().strip(),
        )
        self.wait_window(dlg)
        if dlg.result is None:
            return

        new_raw_gift = self._build_raw_gift(dlg.result)
        gifts = self.raw_config.setdefault("gifts", {})
        new_name = dlg.result["name"]
        if new_name != gift_name:
            del gifts[gift_name]
        gifts[new_name] = new_raw_gift
        self._reload_app_config_from_raw()

    def _on_remove_gift(self) -> None:
        gift_name = self._selected_gift_name()
        if gift_name is None:
            messagebox.showinfo("Nada selecionado", "Selecione uma recompensa na lista.")
            return
        if not messagebox.askyesno(
            "Remover recompensa", f"Remover a recompensa '{gift_name}' da configuracao?"
        ):
            return
        gifts = self.raw_config.get("gifts") or {}
        gifts.pop(gift_name, None)
        self._reload_app_config_from_raw()

    def _on_toggle_gift_enabled(self) -> None:
        gift_name = self._selected_gift_name()
        if gift_name is None:
            messagebox.showinfo("Nada selecionado", "Selecione uma recompensa na lista.")
            return
        gifts = self.raw_config.get("gifts") or {}
        raw_gift = gifts.get(gift_name)
        if raw_gift is None:
            return
        currently_enabled = raw_gift.get("enabled", True)
        if currently_enabled:
            raw_gift["enabled"] = False
        else:
            raw_gift.pop("enabled", None)
        self._reload_app_config_from_raw()
        utils_log.log_tiktok(
            f"'{gift_name}' {'desativado' if currently_enabled else 'ativado'} "
            f"(ainda não salvo em disco)."
        )

    def _selected_gift_name(self) -> Optional[str]:
        selection = self.tree.selection()
        if not selection:
            return None
        return selection[0]

    # ------------------------------------------------------------------ #
    # CRUD de conjuntos de roupa (editando self.raw_config["outfits"])
    # ------------------------------------------------------------------ #
    def _selected_outfit_name(self) -> Optional[str]:
        selection = self.outfits_tree.selection()
        if not selection:
            return None
        return selection[0]

    def _rename_outfit_references(self, old_name: str, new_name: str) -> None:
        """Ao renomear um conjunto, atualiza quem apontava pro nome antigo
        (padrão global + presentes que usam esse conjunto)."""
        vrchat_raw = self.raw_config.get("vrchat") or {}
        if vrchat_raw.get("default_revert_outfit") == old_name:
            vrchat_raw["default_revert_outfit"] = new_name
        for gift_body in (self.raw_config.get("gifts") or {}).values():
            if gift_body.get("outfit") == old_name:
                gift_body["outfit"] = new_name
            if gift_body.get("revert_outfit") == old_name:
                gift_body["revert_outfit"] = new_name

    def _on_new_outfit(self) -> None:
        dlg = OutfitEditDialog(
            self, on_test_target=self._test_raw_target,
            existing_names=set(self._current_outfits_raw().keys()),
        )
        self.wait_window(dlg)
        if dlg.result is None:
            return
        name, targets = dlg.result
        self.raw_config.setdefault("outfits", {})[name] = targets
        self._reload_app_config_from_raw()

    def _on_edit_outfit(self) -> None:
        name = self._selected_outfit_name()
        if name is None:
            messagebox.showinfo("Nada selecionado", "Selecione um conjunto na lista.")
            return

        targets = self._current_outfits_raw().get(name, [])
        dlg = OutfitEditDialog(
            self, on_test_target=self._test_raw_target,
            name=name, targets=targets,
            existing_names=set(self._current_outfits_raw().keys()),
            editing_original_name=name,
        )
        self.wait_window(dlg)
        if dlg.result is None:
            return

        new_name, new_targets = dlg.result
        outfits = self.raw_config.setdefault("outfits", {})
        if new_name != name:
            del outfits[name]
            self._rename_outfit_references(name, new_name)
        outfits[new_name] = new_targets
        self._reload_app_config_from_raw()

    def _on_remove_outfit(self) -> None:
        name = self._selected_outfit_name()
        if name is None:
            messagebox.showinfo("Nada selecionado", "Selecione um conjunto na lista.")
            return

        vrchat_raw = self.raw_config.get("vrchat") or {}
        used_by = [
            gift_name for gift_name, body in (self.raw_config.get("gifts") or {}).items()
            if body.get("outfit") == name or body.get("revert_outfit") == name
        ]
        is_default = vrchat_raw.get("default_revert_outfit") == name

        warning_lines = []
        if is_default:
            warning_lines.append("• É a roupa padrão global atual.")
        if used_by:
            warning_lines.append(f"• Usado pelos presentes: {', '.join(used_by)}")
        warning = ("\n\n" + "\n".join(warning_lines)) if warning_lines else ""

        if not messagebox.askyesno(
            "Remover conjunto",
            f"Remover o conjunto '{name}'?{warning}\n\n"
            f"(Se algo ainda referenciar esse nome depois de remover, a "
            f"configuração vai dar erro até você corrigir.)",
        ):
            return

        outfits = self.raw_config.get("outfits") or {}
        outfits.pop(name, None)
        if is_default:
            vrchat_raw.pop("default_revert_outfit", None)
        self._reload_app_config_from_raw()

    def _on_test_outfit(self) -> None:
        """Aplica todas as peças do conjunto selecionado agora, em
        sequência (com a pausa automática) -- funciona com ou sem estar
        conectado à LIVE."""
        name = self._selected_outfit_name()
        if name is None:
            messagebox.showinfo("Nada selecionado", "Selecione um conjunto na lista.")
            return
        if self.async_loop is None:
            messagebox.showerror("Erro interno", "O loop assíncrono não está pronto ainda.")
            return

        self._ensure_osc_client()
        items = self._current_outfits_raw().get(name, [])
        try:
            rule, warnings = parse_gift_rule(name, {"parameters": items})
        except ConfigError as exc:
            messagebox.showerror("Configuração inválida", str(exc))
            return
        for warning in warnings:
            utils_log.log_error(f"[CONFIG] {warning}")

        osc_client = self.osc_client

        async def _run() -> None:
            utils_log.log_tiktok(f"Testando conjunto '{name}' (todas as peças)...")
            await send_target_sequence(osc_client, rule.targets)

        asyncio.run_coroutine_threadsafe(_run(), self.async_loop)

    def _on_set_default_outfit(self) -> None:
        name = self._selected_outfit_name()
        if name is None:
            messagebox.showinfo("Nada selecionado", "Selecione um conjunto na lista.")
            return
        vrchat_raw = self.raw_config.setdefault("vrchat", {})
        vrchat_raw["default_revert_outfit"] = name
        vrchat_raw.pop("default_revert", None)
        self._reload_app_config_from_raw()
        utils_log.log_tiktok(f"'{name}' definido como roupa padrão (ainda não salvo em disco).")

    def _on_show_avatar_parameters(self) -> None:
        AvatarParametersDialog(self, on_use_parameter=self._on_use_avatar_parameter)

    def _on_use_avatar_parameter(
        self, name: str, loader_type: str, value=None, address: str | None = None
    ) -> None:
        """Chamado quando o usuário escolhe 'Usar este parâmetro...' na lista
        de parâmetros do avatar — abre um alvo já pré-preenchido para ele
        só completar o valor e testar/adicionar num presente ou conjunto.
        Usa sempre o endereço OSC exato (quando disponível), em vez de
        reconstruir a partir do nome -- alguns parâmetros têm nome de
        exibição diferente do endereço real (ex: espaço vs underline)."""
        dlg = TargetEditDialog(self, on_test=self._test_raw_target)
        dlg.set_parameter(name, loader_type, value=value, address=address)
        messagebox.showinfo(
            "Parâmetro pronto",
            f"Preenchi o parâmetro '{name}' (tipo detectado: {loader_type}).\n"
            f"Defina o valor e clique em 'Testar agora' para conferir no avatar, "
            f"depois 'OK'. Você pode então copiar esse alvo manualmente para um "
            f"presente ou conjunto (ou usar como referência).",
            parent=self,
        )

    def _on_show_live_parameters(self) -> None:
        LiveParametersDialog(
            self, async_loop=self.async_loop, on_use_parameter=self._on_use_avatar_parameter
        )

    def _reload_app_config_from_raw(self) -> None:
        """Revalida self.raw_config em memoria (sem tocar no arquivo ainda)
        e atualiza as listas na tela."""
        warnings: list[str] = []
        gifts = {}
        try:
            outfits_raw = self.raw_config.get("outfits") or {}
            outfits_parsed: dict[str, Any] = {}
            for outfit_name, items in outfits_raw.items():
                outfit_rule, outfit_warnings = parse_gift_rule(
                    outfit_name, {"parameters": items}
                )
                outfits_parsed[outfit_name] = outfit_rule.targets
                warnings.extend(outfit_warnings)

            vrchat_raw = self.raw_config.get("vrchat") or {}
            default_revert = []
            default_revert_outfit_name = vrchat_raw.get("default_revert_outfit")
            if default_revert_outfit_name:
                if default_revert_outfit_name not in outfits_parsed:
                    raise ConfigError(
                        f"'vrchat.default_revert_outfit' referencia o conjunto "
                        f"'{default_revert_outfit_name}', que não existe."
                    )
                default_revert = outfits_parsed[default_revert_outfit_name]
            elif vrchat_raw.get("default_revert"):
                default_rule, default_warnings = parse_gift_rule(
                    "_default_revert_", {"parameters": vrchat_raw["default_revert"]}
                )
                default_revert = default_rule.targets
                warnings.extend(default_warnings)

            for gift_name, gift_body in (self.raw_config.get("gifts") or {}).items():
                rule, gift_warnings = parse_gift_rule(gift_name, gift_body, outfits=outfits_parsed)
                gifts[gift_name] = rule
                warnings.extend(gift_warnings)

            for gift_name, rule in gifts.items():
                if rule.duration_seconds is not None and not rule.revert_targets and not default_revert:
                    raise ConfigError(
                        f"Recompensa '{gift_name}' tem duração configurada, mas não há "
                        f"revert definido para ela nem uma roupa padrão global "
                        f"configurada. Defina uma na aba 'Conjuntos de roupa' ou "
                        f"escolha um 'reverter para' nesta recompensa."
                    )

            # Cada presente REAL do TikTok só pode disparar UMA recompensa.
            gift_name_lookup: dict[str, str] = {}
            for reward_name, rule in gifts.items():
                for trigger in rule.trigger_gift_names:
                    existing = gift_name_lookup.get(trigger)
                    if existing is not None and existing != reward_name:
                        raise ConfigError(
                            f"O presente '{trigger}' está associado a mais de uma "
                            f"recompensa ('{existing}' e '{reward_name}'). Cada "
                            f"presente do TikTok só pode disparar uma recompensa "
                            f"— remova-o de uma delas."
                        )
                    gift_name_lookup[trigger] = reward_name
        except ConfigError as exc:
            messagebox.showerror("Configuracao invalida", str(exc))
            return

        if self.app_config is not None:
            self.app_config.gifts = gifts
            self.app_config.gift_name_lookup = gift_name_lookup
            self.app_config.outfits = outfits_parsed
            self.app_config.default_revert = default_revert
            self.app_config.default_revert_outfit_name = default_revert_outfit_name
            self.app_config.warnings = warnings
        self._refresh_all_trees()

    def _on_save_config(self) -> None:
        if not messagebox.askyesno(
            "Salvar configuracao",
            "Isso vai sobrescrever o config.yaml com os presentes e conjuntos "
            "atuais.\nComentarios do arquivo original serao perdidos.\n\n"
            "Deseja continuar?",
        ):
            return

        self.raw_config.setdefault("tiktok", {})["username"] = self.username_var.get().strip()
        vrchat_raw = self.raw_config.setdefault("vrchat", {})
        vrchat_raw["osc_host"] = self.host_var.get().strip()
        try:
            vrchat_raw["osc_port"] = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Porta invalida", "A porta OSC precisa ser um numero inteiro.")
            return

        try:
            save_raw(self.config_path, self.raw_config)
        except ConfigError as exc:
            messagebox.showerror("Erro ao salvar", str(exc))
            return

        messagebox.showinfo(
            "Salvo",
            "config.yaml atualizado com sucesso." + (
                "\n\nVocê está conectado à LIVE agora: para a conexão atual "
                "usar essa configuração nova, clique em Desconectar e depois "
                "Conectar de novo. (Os botões de teste já usam a configuração "
                "nova automaticamente, sem precisar reconectar.)"
                if self.connected else ""
            ),
        )
        self._load_config_into_ui()

    # ------------------------------------------------------------------ #
    # Conexao com o TikTok LIVE (no loop assincrono permanente do app)
    # ------------------------------------------------------------------ #
    def _on_connect(self) -> None:
        if self.connected:
            return

        username = self.username_var.get().strip()
        if not username:
            messagebox.showerror("Canal do TikTok vazio", "Informe o @ do canal do TikTok.")
            return
        if self.async_loop is None:
            messagebox.showerror("Erro interno", "O loop assíncrono não está pronto ainda.")
            return

        gift_handler = self._ensure_gift_handler()
        assert self.app_config is not None

        self.listener = TikTokGiftListener(
            username=username,
            on_gift=gift_handler.handle_gift,
            reconnect_initial_delay=self.app_config.reconnect_initial_delay,
            reconnect_max_delay=self.app_config.reconnect_max_delay,
            reconnect_backoff_multiplier=self.app_config.reconnect_backoff_multiplier,
            on_status=self._on_status_from_any_thread,
        )

        self.connected = True
        self.connect_btn.configure(state="disabled")
        self.disconnect_btn.configure(state="normal")

        asyncio.run_coroutine_threadsafe(self.listener.run_forever(), self.async_loop)

    def _on_disconnect(self) -> None:
        if self.listener is not None:
            self.listener.request_stop()
        self.connected = False
        self.connect_btn.configure(state="normal")
        self.disconnect_btn.configure(state="disabled")

    def _on_close(self) -> None:
        if self.listener is not None:
            self.listener.request_stop()
        if self.async_loop is not None:
            self.async_loop.call_soon_threadsafe(self.async_loop.stop)
        self.destroy()

    # ------------------------------------------------------------------ #
    # Comunicacao entre threads (log/status) -> fila -> loop da GUI
    # ------------------------------------------------------------------ #
    def _on_log_from_any_thread(self, tag: str, message: str) -> None:
        self.gui_queue.put(("log", (tag, message)))

    def _on_status_from_any_thread(self, status: str) -> None:
        self.gui_queue.put(("status", status))

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.gui_queue.get_nowait()
                if kind == "log":
                    tag, message = payload
                    self._append_log(tag, message)
                elif kind == "status":
                    self._apply_status(payload)
        except queue.Empty:
            pass
        finally:
            self.after(100, self._poll_queue)

    def _append_log(self, tag: str, message: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"[{tag}] {message}\n", (tag,))
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _apply_status(self, status: str) -> None:
        text, color = STATUS_LABELS.get(status, (status, "#888888"))
        self.status_label.configure(text=text, foreground=color)
        if status == "stopped":
            self.connected = False
            self.connect_btn.configure(state="normal")
            self.disconnect_btn.configure(state="disabled")


def run(config_path: str = DEFAULT_CONFIG_PATH) -> None:
    app = App(config_path=config_path)
    app.mainloop()
