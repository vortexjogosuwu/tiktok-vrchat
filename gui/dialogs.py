"""
gui/dialogs.py

Janelas (Toplevel) para criar/editar presentes e seus alvos OSC,
com botao de "Testar" em cada alvo -- dispara o comando OSC na hora,
sem precisar mandar presente nenhum no TikTok.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk
from typing import Any, Callable, Optional

from config.loader import ConfigError, VALID_TYPES, parse_gift_rule

TestTargetCallback = Callable[[dict], None]


class TargetEditDialog(tk.Toplevel):
    """Janela para criar/editar UM alvo OSC (parametro/endereco + tipo + valor)."""

    def __init__(self, parent, on_test, initial=None):
        super().__init__(parent)
        self.title("Alvo OSC")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.on_test = on_test
        self.result = None

        initial = initial or {}
        use_address = "address" in initial

        self.mode_var = tk.StringVar(value="address" if use_address else "parameter")
        self.name_var = tk.StringVar(
            value=str(initial.get("address") or initial.get("parameter") or "")
        )
        self.type_var = tk.StringVar(value=str(initial.get("type") or "int"))
        self.value_var = tk.StringVar(value=str(initial.get("value", "")))

        pad = {"padx": 10, "pady": 4}

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(
            frm,
            text="Escolha se este alvo e um parametro de avatar do VRChat\n"
                 "ou um endereco OSC completo e customizado:",
            justify="left",
        ).grid(row=0, column=0, columnspan=2, sticky="w", **pad)

        mode_frame = ttk.Frame(frm)
        mode_frame.grid(row=1, column=0, columnspan=2, sticky="w", padx=10)
        ttk.Radiobutton(
            mode_frame, text="Parametro do avatar (/avatar/parameters/...)",
            variable=self.mode_var, value="parameter", command=self._update_labels,
        ).pack(anchor="w")
        ttk.Radiobutton(
            mode_frame, text="Endereco OSC completo (customizado)",
            variable=self.mode_var, value="address", command=self._update_labels,
        ).pack(anchor="w")

        self.name_label = ttk.Label(frm, text="Nome do parametro:")
        self.name_label.grid(row=2, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.name_var, width=32).grid(
            row=2, column=1, sticky="we", **pad
        )

        ttk.Label(frm, text="Tipo:").grid(row=3, column=0, sticky="w", **pad)
        type_combo = ttk.Combobox(
            frm, textvariable=self.type_var, values=list(VALID_TYPES),
            state="readonly", width=29,
        )
        type_combo.grid(row=3, column=1, sticky="we", **pad)

        ttk.Label(frm, text="Valor:").grid(row=4, column=0, sticky="w", **pad)
        ttk.Entry(frm, textvariable=self.value_var, width=32).grid(
            row=4, column=1, sticky="we", **pad
        )

        hint = ttk.Label(
            frm,
            text="int: 0, 1, 2...   float: 0.0 a 1.0 (por ex.)   "
                 "bool: true/false   string: texto livre",
            foreground="#666666",
        )
        hint.grid(row=5, column=0, columnspan=2, sticky="w", padx=10)

        btn_frame = ttk.Frame(frm)
        btn_frame.grid(row=6, column=0, columnspan=2, pady=(12, 0))

        ttk.Button(btn_frame, text="Testar agora", command=self._on_test).pack(
            side="left", padx=4
        )
        ttk.Button(btn_frame, text="OK", command=self._on_ok).pack(side="left", padx=4)
        ttk.Button(btn_frame, text="Cancelar", command=self.destroy).pack(
            side="left", padx=4
        )

        self._update_labels()
        self.bind("<Return>", lambda _e: self._on_ok())
        self.bind("<Escape>", lambda _e: self.destroy())

    def _update_labels(self):
        if self.mode_var.get() == "address":
            self.name_label.configure(text="Endereco OSC (ex: /avatar/parameters/Nome):")
        else:
            self.name_label.configure(text="Nome do parametro (ex: Outfit):")

    def _build_raw(self):
        name = self.name_var.get().strip()
        if not name:
            raise ConfigError("Informe o nome do parametro ou o endereco OSC.")

        raw = {
            "type": self.type_var.get(),
            "value": self.value_var.get(),
        }
        if self.mode_var.get() == "address":
            raw["address"] = name
        else:
            raw["parameter"] = name
        return raw

    def _on_test(self):
        try:
            raw = self._build_raw()
            self.on_test(raw)
        except ConfigError as exc:
            messagebox.showerror("Configuracao invalida", str(exc), parent=self)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Falha ao testar", str(exc), parent=self)

    def _on_ok(self):
        try:
            raw = self._build_raw()
            parse_gift_rule("_validacao_", raw)
        except ConfigError as exc:
            messagebox.showerror("Configuracao invalida", str(exc), parent=self)
            return

        self.result = raw
        self.destroy()


class GiftEditDialog(tk.Toplevel):
    """Janela para criar/editar um presente completo (nome + lista de alvos OSC)."""

    def __init__(
        self,
        parent,
        on_test_target,
        gift_name="",
        targets=None,
        existing_names=None,
        editing_original_name=None,
    ):
        super().__init__(parent)
        self.title("Presente" if not gift_name else f"Editar presente: {gift_name}")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.on_test_target = on_test_target
        self.existing_names = existing_names or set()
        self.editing_original_name = editing_original_name
        self.targets = [dict(t) for t in (targets or [])]

        self.result = None

        pad = {"padx": 10, "pady": 6}

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(frm, text="Nome do presente (exatamente como o TikTok chama, ex: Rose):").grid(
            row=0, column=0, sticky="w", **pad
        )
        self.name_var = tk.StringVar(value=gift_name)
        ttk.Entry(frm, textvariable=self.name_var, width=40).grid(
            row=1, column=0, sticky="we", padx=10
        )

        ttk.Label(frm, text="Alvos OSC deste presente:").grid(
            row=2, column=0, sticky="w", **pad
        )

        columns = ("endereco", "tipo", "valor")
        self.tree = ttk.Treeview(
            frm, columns=columns, show="headings", height=6, selectmode="browse"
        )
        self.tree.heading("endereco", text="Endereco")
        self.tree.heading("tipo", text="Tipo")
        self.tree.heading("valor", text="Valor")
        self.tree.column("endereco", width=260)
        self.tree.column("tipo", width=70, anchor="center")
        self.tree.column("valor", width=100, anchor="center")
        self.tree.grid(row=3, column=0, sticky="we", padx=10)

        btns = ttk.Frame(frm)
        btns.grid(row=4, column=0, sticky="we", padx=10, pady=(6, 0))
        ttk.Button(btns, text="Adicionar alvo", command=self._add_target).pack(
            side="left", padx=2
        )
        ttk.Button(btns, text="Editar alvo", command=self._edit_target).pack(
            side="left", padx=2
        )
        ttk.Button(btns, text="Remover alvo", command=self._remove_target).pack(
            side="left", padx=2
        )
        ttk.Button(btns, text="Testar alvo", command=self._test_selected).pack(
            side="left", padx=2
        )

        final_btns = ttk.Frame(frm)
        final_btns.grid(row=5, column=0, pady=(14, 0))
        ttk.Button(final_btns, text="Salvar presente", command=self._on_ok).pack(
            side="left", padx=4
        )
        ttk.Button(final_btns, text="Cancelar", command=self.destroy).pack(
            side="left", padx=4
        )

        self._refresh_tree()

    def _refresh_tree(self):
        self.tree.delete(*self.tree.get_children())
        for idx, target in enumerate(self.targets):
            address = target.get("address") or f"/avatar/parameters/{target.get('parameter')}"
            self.tree.insert(
                "", "end", iid=str(idx),
                values=(address, target.get("type"), target.get("value")),
            )

    def _add_target(self):
        dlg = TargetEditDialog(self, on_test=self.on_test_target)
        self.wait_window(dlg)
        if dlg.result is not None:
            self.targets.append(dlg.result)
            self._refresh_tree()

    def _selected_index(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _edit_target(self):
        idx = self._selected_index()
        if idx is None:
            messagebox.showinfo("Nenhum alvo selecionado", "Selecione um alvo para editar.", parent=self)
            return
        dlg = TargetEditDialog(self, on_test=self.on_test_target, initial=self.targets[idx])
        self.wait_window(dlg)
        if dlg.result is not None:
            self.targets[idx] = dlg.result
            self._refresh_tree()

    def _remove_target(self):
        idx = self._selected_index()
        if idx is None:
            messagebox.showinfo("Nenhum alvo selecionado", "Selecione um alvo para remover.", parent=self)
            return
        del self.targets[idx]
        self._refresh_tree()

    def _test_selected(self):
        idx = self._selected_index()
        if idx is None:
            messagebox.showinfo("Nenhum alvo selecionado", "Selecione um alvo para testar.", parent=self)
            return
        try:
            self.on_test_target(self.targets[idx])
        except ConfigError as exc:
            messagebox.showerror("Configuracao invalida", str(exc), parent=self)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Falha ao testar", str(exc), parent=self)

    def _on_ok(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Nome obrigatorio", "Informe o nome do presente.", parent=self)
            return

        if not self.targets:
            messagebox.showerror(
                "Nenhum alvo", "Adicione ao menos um alvo OSC para este presente.", parent=self
            )
            return

        other_names = self.existing_names - (
            {self.editing_original_name} if self.editing_original_name else set()
        )
        if name in other_names:
            messagebox.showerror(
                "Nome duplicado",
                f"Ja existe um presente chamado '{name}'. Escolha outro nome.",
                parent=self,
            )
            return

        raw = {"parameters": self.targets} if len(self.targets) > 1 else self.targets[0]
        try:
            parse_gift_rule(name, raw)
        except ConfigError as exc:
            messagebox.showerror("Configuracao invalida", str(exc), parent=self)
            return

        self.result = (name, self.targets)
        self.destroy()
