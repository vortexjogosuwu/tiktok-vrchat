"""
gui/app.py

Janela principal do TikTok LIVE -> VRChat OSC Bridge.

Tudo que o programa CLI (main.py) faz, esta janela tambem faz, mas com
mouse: conectar/desconectar da LIVE, ver o log em tempo real, e o mais
importante -- criar, editar e TESTAR presentes sem precisar mandar
nada de verdade no TikTok (inclusive presentes com duração/fila: dá
para testar o ciclo completo -- aplica, espera, reverte -- sem estar
conectado a nenhuma LIVE).
"""

from __future__ import annotations

import asyncio
import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Optional

from config.loader import AppConfig, ConfigError, load_config, load_raw, parse_gift_rule, save_raw
from gui.dialogs import AvatarParametersDialog, DefaultRevertDialog, GiftEditDialog, OutfitManagerDialog
from handlers.gifts import GiftHandler
from tiktok.listener import TikTokGiftListener
import utils_log
from vrchat.osc import VRChatOSC

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
        self.geometry("780x560")
        self.minsize(680, 480)

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

        # --- Lista de presentes -------------------------------------------------
        list_frame = ttk.LabelFrame(self, text="Presentes configurados", padding=8)
        list_frame.pack(fill="both", expand=True, padx=10, pady=(8, 4))

        columns = ("presente", "conjunto", "endereco", "tipo", "valor", "duracao")
        self.tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="extended")
        self.tree.heading("presente", text="Presente")
        self.tree.heading("conjunto", text="Conjunto")
        self.tree.heading("endereco", text="Endereco OSC")
        self.tree.heading("tipo", text="Tipo")
        self.tree.heading("valor", text="Valor")
        self.tree.heading("duracao", text="Duração")
        self.tree.column("presente", width=110)
        self.tree.column("conjunto", width=90, anchor="center")
        self.tree.column("endereco", width=230)
        self.tree.column("tipo", width=55, anchor="center")
        self.tree.column("valor", width=70, anchor="center")
        self.tree.column("duracao", width=80, anchor="center")
        self.tree.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="left", fill="y")

        btns_frame = ttk.Frame(self, padding=(10, 0))
        btns_frame.pack(fill="x")
        ttk.Button(btns_frame, text="Novo presente", command=self._on_new_gift).pack(
            side="left", padx=2
        )
        ttk.Button(btns_frame, text="Editar presente", command=self._on_edit_gift).pack(
            side="left", padx=2
        )
        ttk.Button(btns_frame, text="Remover presente", command=self._on_remove_gift).pack(
            side="left", padx=2
        )
        ttk.Button(
            btns_frame, text="Testar selecionado(s)", command=self._on_test_selected
        ).pack(side="left", padx=(12, 2))
        ttk.Button(
            btns_frame, text="Testar presente (completo)", command=self._on_test_gift_full
        ).pack(side="left", padx=2)
        ttk.Button(
            btns_frame, text="Conjuntos de roupa", command=self._on_manage_outfits
        ).pack(side="left", padx=(12, 2))
        ttk.Button(
            btns_frame, text="Roupa padrão (revert global)", command=self._on_edit_default_revert
        ).pack(side="left", padx=2)
        ttk.Button(
            btns_frame, text="Parâmetros do avatar...", command=self._on_show_avatar_parameters
        ).pack(side="left", padx=(12, 2))
        ttk.Button(
            btns_frame, text="Salvar configuracao", command=self._on_save_config
        ).pack(side="right", padx=2)

        # --- Log -------------------------------------------------------------
        log_frame = ttk.LabelFrame(self, text="Log", padding=6)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        self.log_text = tk.Text(log_frame, height=10, state="disabled", wrap="word")
        self.log_text.pack(side="left", fill="both", expand=True)
        log_scroll = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scroll.set)
        log_scroll.pack(side="left", fill="y")

        self.log_text.tag_configure("TIKTOK", foreground="#1a5aa8")
        self.log_text.tag_configure("OSC", foreground="#1a8a1a")
        self.log_text.tag_configure("ERROR", foreground="#c22")

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

        self._refresh_tree()
        self._ensure_osc_client()

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        if not self.app_config:
            return
        for gift_name, rule in self.app_config.gifts.items():
            duration_label = "-"
            if rule.duration_seconds is not None:
                minutes = rule.duration_seconds / 60
                duration_label = (
                    f"{int(minutes)} min" if minutes == int(minutes) else f"{minutes:.1f} min"
                )
            for idx, target in enumerate(rule.targets):
                iid = f"{gift_name}#{idx}"
                self.tree.insert(
                    "", "end", iid=iid,
                    values=(
                        gift_name, rule.outfit_name or "-", target.address,
                        target.value_type, target.value, duration_label,
                    ),
                )

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
        quanto pelo botão "Testar presente (completo)". Isso garante que
        testar funciona exatamente como a LIVE de verdade funcionaria
        (mesma fila, mesmo revert), com ou sem estar conectado.
        """
        self._ensure_osc_client()
        assert self.app_config is not None
        if self.gift_handler is None:
            self.gift_handler = GiftHandler(config=self.app_config, osc_client=self.osc_client)  # type: ignore[arg-type]
        return self.gift_handler

    def _on_test_gift_full(self) -> None:
        """
        Testa o presente inteiro como se tivesse chegado de verdade pela
        LIVE: aplica os alvos, espera a duração (se houver) e reverte --
        tudo isso funciona COM ou SEM estar conectado ao TikTok, porque
        roda no mesmo loop assíncrono permanente do programa.
        """
        gift_name = self._selected_gift_name()
        if gift_name is None:
            messagebox.showinfo("Nada selecionado", "Selecione um presente na lista.")
            return
        if self.async_loop is None:
            messagebox.showerror("Erro interno", "O loop assíncrono não está pronto ainda.")
            return

        gift_handler = self._ensure_gift_handler()

        async def _run() -> None:
            await gift_handler.handle_gift(gift_name, "Teste manual", 1)

        asyncio.run_coroutine_threadsafe(_run(), self.async_loop)

    def _test_raw_target(self, raw_target: dict[str, Any]) -> None:
        """Valida e envia um alvo isolado (usado pelos dialogos de edicao)."""
        self._ensure_osc_client()
        rule, warnings = parse_gift_rule("_teste_", raw_target)
        for warning in warnings:
            utils_log.log_error(f"[CONFIG] {warning}")
        for target in rule.targets:
            assert self.osc_client is not None
            self.osc_client.send(target.address, target.value)

    def _on_test_selected(self) -> None:
        self._ensure_osc_client()
        selection = self.tree.selection()
        if not selection:
            messagebox.showinfo("Nada selecionado", "Selecione um ou mais presentes na lista.")
            return

        for iid in selection:
            gift_name, idx_str = iid.split("#")
            idx = int(idx_str)
            rule = self.app_config.gifts[gift_name]  # type: ignore[union-attr]
            target = rule.targets[idx]
            assert self.osc_client is not None
            self.osc_client.send(target.address, target.value)

    # ------------------------------------------------------------------ #
    # CRUD de presentes (editando self.raw_config["gifts"])
    # ------------------------------------------------------------------ #
    def _current_gift_names(self) -> set[str]:
        return set((self.raw_config.get("gifts") or {}).keys())

    def _current_outfits_raw(self) -> dict[str, Any]:
        return self.raw_config.get("outfits") or {}

    @staticmethod
    def _build_raw_gift(result: dict[str, Any]) -> dict[str, Any]:
        raw_gift: dict[str, Any] = {}
        if result["outfit"]:
            raw_gift["outfit"] = result["outfit"]
        extra_targets = result["extra_targets"]
        if len(extra_targets) > 1:
            raw_gift["parameters"] = extra_targets
        elif len(extra_targets) == 1:
            raw_gift.update(extra_targets[0])
        if result["duration_minutes"] is not None:
            raw_gift["duration_minutes"] = result["duration_minutes"]
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
            messagebox.showinfo("Nada selecionado", "Selecione um presente na lista.")
            return

        raw_gift = (self.raw_config.get("gifts") or {}).get(gift_name, {})
        outfit_name = raw_gift.get("outfit")
        if raw_gift.get("parameters"):
            extra_targets = raw_gift["parameters"]
        elif "parameter" in raw_gift or "address" in raw_gift:
            extra_targets = [
                {k: v for k, v in raw_gift.items()
                 if k not in ("duration_minutes", "duration_seconds", "revert", "revert_outfit", "outfit")}
            ]
        else:
            extra_targets = []

        duration_minutes = raw_gift.get("duration_minutes")
        if duration_minutes is None and raw_gift.get("duration_seconds") is not None:
            duration_minutes = float(raw_gift["duration_seconds"]) / 60.0

        dlg = GiftEditDialog(
            self, on_test_target=self._test_raw_target,
            outfits_raw=self._current_outfits_raw(),
            gift_name=gift_name, outfit_name=outfit_name, extra_targets=extra_targets,
            duration_minutes=duration_minutes,
            revert_outfit_name=raw_gift.get("revert_outfit"),
            revert_extra_targets=raw_gift.get("revert") or [],
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

    def _on_manage_outfits(self) -> None:
        dlg = OutfitManagerDialog(
            self, on_test_target=self._test_raw_target,
            outfits_raw=self._current_outfits_raw(),
        )
        self.wait_window(dlg)
        if dlg.result is None:
            return
        self.raw_config["outfits"] = dlg.result
        self._reload_app_config_from_raw()

    def _on_edit_default_revert(self) -> None:
        vrchat_raw = self.raw_config.setdefault("vrchat", {})
        dlg = DefaultRevertDialog(
            self, on_test_target=self._test_raw_target,
            outfit_names=list(self._current_outfits_raw().keys()),
            outfit_name=vrchat_raw.get("default_revert_outfit"),
            targets=vrchat_raw.get("default_revert") or [],
        )
        self.wait_window(dlg)
        if dlg.result is None:
            return
        if dlg.result["outfit"]:
            vrchat_raw["default_revert_outfit"] = dlg.result["outfit"]
            vrchat_raw.pop("default_revert", None)
        else:
            vrchat_raw["default_revert"] = dlg.result["targets"]
            vrchat_raw.pop("default_revert_outfit", None)
        self._reload_app_config_from_raw()

    def _on_show_avatar_parameters(self) -> None:
        AvatarParametersDialog(self, on_use_parameter=self._on_use_avatar_parameter)

    def _on_use_avatar_parameter(self, name: str, loader_type: str) -> None:
        """Chamado quando o usuário escolhe 'Usar este parâmetro...' na lista
        de parâmetros do avatar — abre um alvo já pré-preenchido para ele
        só completar o valor e testar/adicionar num presente ou conjunto."""
        from gui.dialogs import TargetEditDialog

        dlg = TargetEditDialog(self, on_test=self._test_raw_target)
        dlg.set_parameter(name, loader_type)
        messagebox.showinfo(
            "Parâmetro pronto",
            f"Preenchi o parâmetro '{name}' (tipo detectado: {loader_type}).\n"
            f"Defina o valor e clique em 'Testar agora' para conferir no avatar, "
            f"depois 'OK'. Você pode então copiar esse alvo manualmente para um "
            f"presente ou conjunto (ou usar como referência).",
            parent=self,
        )

    def _on_remove_gift(self) -> None:
        gift_name = self._selected_gift_name()
        if gift_name is None:
            messagebox.showinfo("Nada selecionado", "Selecione um presente na lista.")
            return
        if not messagebox.askyesno(
            "Remover presente", f"Remover o presente '{gift_name}' da configuracao?"
        ):
            return
        gifts = self.raw_config.get("gifts") or {}
        gifts.pop(gift_name, None)
        self._reload_app_config_from_raw()

    def _selected_gift_name(self) -> Optional[str]:
        selection = self.tree.selection()
        if not selection:
            return None
        return selection[0].split("#")[0]

    def _reload_app_config_from_raw(self) -> None:
        """Revalida self.raw_config em memoria (sem tocar no arquivo ainda)
        e atualiza a lista na tela."""
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
                        f"Presente '{gift_name}' tem duração configurada, mas não há "
                        f"revert definido para ele nem uma roupa padrão global "
                        f"configurada. Use o botão 'Roupa padrão (revert global)' ou "
                        f"defina um 'reverter para' neste presente."
                    )
        except ConfigError as exc:
            messagebox.showerror("Configuracao invalida", str(exc))
            return

        if self.app_config is not None:
            self.app_config.gifts = gifts
            self.app_config.outfits = outfits_parsed
            self.app_config.default_revert = default_revert
            self.app_config.default_revert_outfit_name = default_revert_outfit_name
            self.app_config.warnings = warnings
        self._refresh_tree()

    def _on_save_config(self) -> None:
        if not messagebox.askyesno(
            "Salvar configuracao",
            "Isso vai sobrescrever o config.yaml com os presentes atuais.\n"
            "Comentarios do arquivo original serao perdidos.\n\n"
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
                "Conectar de novo. (O botão 'Testar presente' já usa a "
                "configuração nova automaticamente, sem precisar reconectar.)"
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
