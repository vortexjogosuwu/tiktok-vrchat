"""
gui/dialogs.py

Janelas (Toplevel) para:
- Criar/editar um alvo OSC isolado (TargetEditDialog), com botao de teste.
- Criar/editar um presente completo, incluindo conjunto de roupa,
  alvos extras, duracao e revert (GiftEditDialog).
- Gerenciar "conjuntos de roupa" reutilizaveis (OutfitManagerDialog /
  OutfitEditDialog).
- Editar a roupa padrao global (DefaultRevertDialog).
- Listar os parametros do avatar que o VRChat ja gravou em disco, para
  copiar/usar sem precisar adivinhar nomes (AvatarParametersDialog).
"""

from __future__ import annotations

import os
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from config.loader import ConfigError, VALID_TYPES, cast_value, parse_gift_rule
from tiktok.catalog import COMMON_GIFT_SUGGESTIONS, fetch_live_gift_catalog
from vrchat.discovery import default_osc_config_dir, find_avatars

NO_OUTFIT = "(nenhum)"


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
        ttk.Button(
            frm, text="Escolher da lista do avatar...", command=self._open_avatar_parameters
        ).grid(row=2, column=2, sticky="w", padx=(4, 10))

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

    def set_parameter(self, name: str, osc_type: str, value=None, address: str | None = None) -> None:
        """
        Preenche o formulario a partir de um parametro descoberto do
        avatar. Se `address` for dado (o endereço OSC exato, como veio
        do arquivo do VRChat ou do modo escuta), usa ele diretamente em
        modo "endereço completo" -- pra evitar reconstruir errado um
        endereço que não seja exatamente "/avatar/parameters/<nome>"
        (alguns parâmetros têm nome de exibição com espaço, mas
        endereço real com underline, por exemplo).
        """
        if address:
            self.mode_var.set("address")
            self.name_var.set(address)
        else:
            self.mode_var.set("parameter")
            self.name_var.set(name)
        self.type_var.set(osc_type)
        if value is not None:
            self.value_var.set(str(value))
        self._update_labels()

    def _open_avatar_parameters(self):
        AvatarParametersDialog(self, on_use_parameter=self.set_parameter)

    def _build_raw(self):
        name = self.name_var.get().strip()
        if not name:
            raise ConfigError("Informe o nome do parametro ou o endereco OSC.")

        value_type = self.type_var.get()
        # Converte o texto do campo pro tipo Python certo (int/float/bool/
        # string) ANTES de salvar -- assim o YAML grava "value: 0", não
        # "value: '0'", e o nome/tipo ficam exatamente como configurados.
        typed_value = cast_value(value_type, self.value_var.get(), label=name)

        # Ordem fixa de chaves (endereço/parâmetro, depois tipo, depois
        # valor) em todos alvos salvo, pra ficar sempre consistente no YAML.
        raw: dict = {}
        if self.mode_var.get() == "address":
            raw["address"] = name
        else:
            raw["parameter"] = name
        raw["type"] = value_type
        raw["value"] = typed_value
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


class TargetListEditor(ttk.LabelFrame):
    """
    Painel reutilizavel: uma lista de alvos OSC (Treeview) com botoes
    Adicionar/Editar/Remover/Testar.
    """

    def __init__(self, parent, title, on_test_target, initial=None, height=4):
        super().__init__(parent, text=title, padding=6)
        self.on_test_target = on_test_target
        self.targets = [dict(t) for t in (initial or [])]

        columns = ("endereco", "tipo", "valor")
        self.tree = ttk.Treeview(
            self, columns=columns, show="headings", height=height, selectmode="browse"
        )
        self.tree.heading("endereco", text="Endereco")
        self.tree.heading("tipo", text="Tipo")
        self.tree.heading("valor", text="Valor")
        self.tree.column("endereco", width=260)
        self.tree.column("tipo", width=70, anchor="center")
        self.tree.column("valor", width=100, anchor="center")
        self.tree.pack(fill="x")

        btns = ttk.Frame(self)
        btns.pack(fill="x", pady=(4, 0))
        ttk.Button(btns, text="Adicionar", command=self._add).pack(side="left", padx=2)
        ttk.Button(btns, text="Editar", command=self._edit).pack(side="left", padx=2)
        ttk.Button(btns, text="Remover", command=self._remove).pack(side="left", padx=2)
        ttk.Button(btns, text="Testar", command=self._test).pack(side="left", padx=2)

        self._refresh()

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        for idx, target in enumerate(self.targets):
            address = target.get("address") or f"/avatar/parameters/{target.get('parameter')}"
            self.tree.insert(
                "", "end", iid=str(idx),
                values=(address, target.get("type"), target.get("value")),
            )

    def _selected_index(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return int(sel[0])

    def _add(self):
        dlg = TargetEditDialog(self, on_test=self.on_test_target)
        self.wait_window(dlg)
        if dlg.result is not None:
            self.targets.append(dlg.result)
            self._refresh()

    def _edit(self):
        idx = self._selected_index()
        if idx is None:
            messagebox.showinfo("Nenhum alvo selecionado", "Selecione um alvo para editar.", parent=self)
            return
        dlg = TargetEditDialog(self, on_test=self.on_test_target, initial=self.targets[idx])
        self.wait_window(dlg)
        if dlg.result is not None:
            self.targets[idx] = dlg.result
            self._refresh()

    def _remove(self):
        idx = self._selected_index()
        if idx is None:
            messagebox.showinfo("Nenhum alvo selecionado", "Selecione um alvo para remover.", parent=self)
            return
        del self.targets[idx]
        self._refresh()

    def _test(self):
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

    def add_target_dict(self, target: dict) -> None:
        """Adiciona um alvo pronto (ex: vindo da lista de parametros do avatar)."""
        self.targets.append(dict(target))
        self._refresh()

    def get_targets(self):
        return [dict(t) for t in self.targets]


class OutfitEditDialog(tk.Toplevel):
    """Janela para criar/editar UM conjunto de roupa nomeado (lista de pecas)."""

    def __init__(self, parent, on_test_target, name="", targets=None, existing_names=None,
                 editing_original_name=None):
        super().__init__(parent)
        self.title("Conjunto de roupa" if not name else f"Editar conjunto: {name}")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.existing_names = existing_names or set()
        self.editing_original_name = editing_original_name
        self.result = None

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(frm, text="Nome do conjunto (ex: Padrão, Biquíni, Conjunto1):").pack(
            anchor="w"
        )
        self.name_var = tk.StringVar(value=name)
        ttk.Entry(frm, textvariable=self.name_var, width=40).pack(anchor="w", pady=(2, 8))

        self.editor = TargetListEditor(
            frm, "Peças / parâmetros deste conjunto",
            on_test_target=on_test_target, initial=targets, height=8,
        )
        self.editor.pack(fill="x")

        btns = ttk.Frame(frm)
        btns.pack(pady=(12, 0))
        ttk.Button(btns, text="Salvar conjunto", command=self._on_ok).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="left", padx=4)

    def _on_ok(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Nome obrigatório", "Informe o nome do conjunto.", parent=self)
            return

        targets = self.editor.get_targets()
        if not targets:
            messagebox.showerror(
                "Nenhuma peça", "Adicione ao menos uma peça/parâmetro a este conjunto.", parent=self
            )
            return

        other_names = self.existing_names - (
            {self.editing_original_name} if self.editing_original_name else set()
        )
        if name in other_names:
            messagebox.showerror(
                "Nome duplicado",
                f"Já existe um conjunto chamado '{name}'. Escolha outro nome.",
                parent=self,
            )
            return

        try:
            parse_gift_rule(name, {"parameters": targets})
        except ConfigError as exc:
            messagebox.showerror("Configuração inválida", str(exc), parent=self)
            return

        self.result = (name, targets)
        self.destroy()


class OutfitManagerDialog(tk.Toplevel):
    """Janela para gerenciar (criar/editar/remover) os conjuntos de roupa."""

    def __init__(self, parent, on_test_target, outfits_raw):
        super().__init__(parent)
        self.title("Conjuntos de roupa")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.on_test_target = on_test_target
        # outfits_raw: dict[str, list[dict]] -- copia local, so aplicada
        # de volta no config se o usuario clicar em "Fechar" (resultado != None)
        self.outfits = {name: list(items) for name, items in (outfits_raw or {}).items()}
        self.result = None
        self._changed = False

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(
            frm,
            text="Conjuntos de roupa reutilizáveis. Presentes podem escolher um\n"
                 "conjunto pronto em vez de marcar peça por peça toda vez.",
            justify="left",
        ).pack(anchor="w", pady=(0, 6))

        columns = ("nome", "pecas")
        self.tree = ttk.Treeview(frm, columns=columns, show="headings", height=8)
        self.tree.heading("nome", text="Conjunto")
        self.tree.heading("pecas", text="Peças")
        self.tree.column("nome", width=200)
        self.tree.column("pecas", width=300)
        self.tree.pack(fill="x")

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(6, 0))
        ttk.Button(btns, text="Novo conjunto", command=self._new).pack(side="left", padx=2)
        ttk.Button(btns, text="Editar conjunto", command=self._edit).pack(side="left", padx=2)
        ttk.Button(btns, text="Remover conjunto", command=self._remove).pack(side="left", padx=2)

        final_btns = ttk.Frame(frm)
        final_btns.pack(pady=(12, 0))
        ttk.Button(final_btns, text="Fechar", command=self._on_close).pack(side="left", padx=4)

        self._refresh()

    def _refresh(self):
        self.tree.delete(*self.tree.get_children())
        for name, targets in self.outfits.items():
            pieces = ", ".join(
                (t.get("parameter") or t.get("address") or "?") for t in targets
            )
            self.tree.insert("", "end", iid=name, values=(name, pieces))

    def _selected_name(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _new(self):
        dlg = OutfitEditDialog(
            self, on_test_target=self.on_test_target,
            existing_names=set(self.outfits.keys()),
        )
        self.wait_window(dlg)
        if dlg.result is not None:
            name, targets = dlg.result
            self.outfits[name] = targets
            self._changed = True
            self._refresh()

    def _edit(self):
        name = self._selected_name()
        if name is None:
            messagebox.showinfo("Nada selecionado", "Selecione um conjunto na lista.", parent=self)
            return
        dlg = OutfitEditDialog(
            self, on_test_target=self.on_test_target,
            name=name, targets=self.outfits[name],
            existing_names=set(self.outfits.keys()), editing_original_name=name,
        )
        self.wait_window(dlg)
        if dlg.result is not None:
            new_name, targets = dlg.result
            if new_name != name:
                del self.outfits[name]
            self.outfits[new_name] = targets
            self._changed = True
            self._refresh()

    def _remove(self):
        name = self._selected_name()
        if name is None:
            messagebox.showinfo("Nada selecionado", "Selecione um conjunto na lista.", parent=self)
            return
        if not messagebox.askyesno(
            "Remover conjunto",
            f"Remover o conjunto '{name}'? Presentes que usam esse conjunto vão "
            f"passar a dar erro até serem corrigidos.",
            parent=self,
        ):
            return
        del self.outfits[name]
        self._changed = True
        self._refresh()

    def _on_close(self):
        self.result = self.outfits if self._changed else None
        self.destroy()


class GiftNameCatalogDialog(tk.Toplevel):
    """
    Lista de nomes de presente do TikTok para escolher, em vez de digitar.

    - "Buscar da LIVE agora": fonte confiável, mas só funciona com o
      canal ao vivo no momento (é assim que o TikTok expõe a lista).
    - Sugestões comuns: lista offline não-oficial, para quando o canal
      não está ao vivo -- só um ponto de partida.
    """

    def __init__(self, parent, username, on_choose):
        super().__init__(parent)
        self.title("Escolher presente do TikTok")
        self.geometry("480x420")
        self.transient(parent)
        self.grab_set()

        self.username = username
        self.on_choose = on_choose
        self.all_items: list[tuple[str, str]] = []  # (nome, fonte)

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        top = ttk.Frame(frm)
        top.pack(fill="x")
        self.fetch_btn = ttk.Button(
            top, text="Buscar da LIVE agora (@" + (username or "?") + ")",
            command=self._fetch_live,
        )
        self.fetch_btn.pack(side="left")
        if not username:
            self.fetch_btn.configure(state="disabled")

        self.status_label = ttk.Label(frm, text="", foreground="#666666", justify="left")
        self.status_label.pack(anchor="w", pady=(6, 6))

        filter_frame = ttk.Frame(frm)
        filter_frame.pack(fill="x")
        ttk.Label(filter_frame, text="Filtrar:").pack(side="left")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_a: self._refresh())
        ttk.Entry(filter_frame, textvariable=self.filter_var).pack(
            side="left", fill="x", expand=True, padx=(4, 0)
        )

        columns = ("nome", "fonte")
        self.tree = ttk.Treeview(frm, columns=columns, show="headings")
        self.tree.heading("nome", text="Presente")
        self.tree.heading("fonte", text="Fonte")
        self.tree.column("nome", width=280)
        self.tree.column("fonte", width=140, anchor="center")
        self.tree.pack(fill="both", expand=True, pady=(6, 0))
        self.tree.bind("<Double-1>", lambda _e: self._use_selected())

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="Usar este nome", command=self._use_selected).pack(
            side="left", padx=2
        )
        ttk.Button(btns, text="Fechar", command=self.destroy).pack(side="right", padx=2)

        self._load_suggestions()

    def _load_suggestions(self) -> None:
        self.all_items = [(name, "sugestão") for name in COMMON_GIFT_SUGGESTIONS]
        self.status_label.configure(
            text="Mostrando sugestões comuns (não-oficiais, podem variar). "
            "Clique em 'Buscar da LIVE agora' para a lista real e certa "
            "do seu canal (precisa estar ao vivo)."
        )
        self._refresh()

    def _refresh(self) -> None:
        self.tree.delete(*self.tree.get_children())
        term = self.filter_var.get().strip().lower()
        for idx, (name, source) in enumerate(self.all_items):
            if term and term not in name.lower():
                continue
            self.tree.insert("", "end", iid=str(idx), values=(name, source))

    def _fetch_live(self) -> None:
        self.fetch_btn.configure(state="disabled")
        self.status_label.configure(text=f"Buscando presentes de @{self.username}...")

        def worker() -> None:
            import asyncio

            try:
                results = asyncio.run(fetch_live_gift_catalog(self.username))
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda: self._on_fetch_error(str(exc)))
                return
            self.after(0, lambda: self._on_fetch_success(results))

        threading.Thread(target=worker, daemon=True).start()

    def _on_fetch_success(self, results) -> None:
        self.fetch_btn.configure(state="normal")
        self.all_items = [
            (g.name + (f"  ({g.diamond_count} 💎)" if g.diamond_count else ""), "LIVE agora")
            for g in results
        ]
        self.status_label.configure(
            text=f"{len(results)} presente(s) confirmado(s) direto da LIVE de @{self.username}."
        )
        self._refresh()

    def _on_fetch_error(self, message: str) -> None:
        self.fetch_btn.configure(state="normal")
        self.status_label.configure(text=message, foreground="#c22")
        messagebox.showwarning("Não foi possível buscar da LIVE", message, parent=self)

    def _use_selected(self) -> None:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Nada selecionado", "Selecione um presente na lista.", parent=self)
            return
        name, _source = self.all_items[int(sel[0])]
        # remove o sufixo " (N 💎)" adicionado apenas para exibição
        clean_name = name.split("  (")[0]
        self.on_choose(clean_name)
        self.destroy()


class GiftNameListEditor(ttk.LabelFrame):
    """
    Lista de nomes REAIS de presentes do TikTok que disparam uma
    recompensa. Permite mais de um (ex: "Rose" e "TikTok" caindo na
    mesma recompensa) -- digitando manualmente ou escolhendo da lista
    de presentes do canal (GiftNameCatalogDialog).
    """

    def __init__(self, parent, username, initial=None):
        super().__init__(
            parent, text="Presentes do TikTok que disparam esta recompensa", padding=6
        )
        self.username = username
        self.names: list[str] = list(initial or [])

        entry_row = ttk.Frame(self)
        entry_row.pack(fill="x")
        self.name_var = tk.StringVar()
        entry = ttk.Entry(entry_row, textvariable=self.name_var, width=22)
        entry.pack(side="left")
        entry.bind("<Return>", lambda _e: self._add_typed())
        ttk.Button(entry_row, text="Adicionar", command=self._add_typed).pack(
            side="left", padx=(4, 2)
        )
        ttk.Button(
            entry_row, text="Escolher da lista...", command=self._open_catalog
        ).pack(side="left", padx=2)

        self.listbox = tk.Listbox(self, height=4, exportselection=False)
        self.listbox.pack(fill="x", pady=(6, 0))

        ttk.Button(self, text="Remover selecionado", command=self._remove_selected).pack(
            anchor="w", pady=(4, 0)
        )

        self._refresh()

    def _refresh(self) -> None:
        self.listbox.delete(0, "end")
        for name in self.names:
            self.listbox.insert("end", name)

    def _add_typed(self) -> None:
        name = self.name_var.get().strip()
        if not name:
            return
        self._add_name(name)
        self.name_var.set("")

    def _add_name(self, name: str) -> None:
        name = name.strip()
        if not name or name in self.names:
            return
        self.names.append(name)
        self._refresh()

    def _open_catalog(self) -> None:
        GiftNameCatalogDialog(self, username=self.username, on_choose=self._add_name)

    def _remove_selected(self) -> None:
        sel = self.listbox.curselection()
        if not sel:
            messagebox.showinfo(
                "Nada selecionado", "Selecione um presente na lista pra remover.", parent=self
            )
            return
        del self.names[sel[0]]
        self._refresh()

    def get_names(self) -> list[str]:
        return list(self.names)


class GiftEditDialog(tk.Toplevel):
    """
    Janela para criar/editar um presente completo: nome, conjunto de
    roupa (opcional) + alvos extras, duração opcional (fila exclusiva)
    e revert opcional (conjunto e/ou alvos extras).
    """

    def __init__(
        self,
        parent,
        on_test_target,
        outfits_raw,
        gift_name="",
        trigger_gift_names=None,
        outfit_name=None,
        extra_targets=None,
        duration_value=None,
        duration_unit="minutos",
        revert_outfit_name=None,
        revert_extra_targets=None,
        enabled=True,
        ignore_queue=False,
        existing_names=None,
        editing_original_name=None,
        username="",
    ):
        super().__init__(parent)
        self.title("Nova recompensa" if not gift_name else f"Editar recompensa: {gift_name}")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.on_test_target = on_test_target
        self.outfits_raw = outfits_raw or {}
        self.outfit_options = [NO_OUTFIT] + list(self.outfits_raw.keys())
        self.existing_names = existing_names or set()
        self.editing_original_name = editing_original_name
        self.username = username

        self.result = None

        pad = {"padx": 10, "pady": 6}

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(frm, text="Nome da recompensa (livre, ex: \"Casual\", \"Combo Barato\"):").grid(
            row=0, column=0, sticky="w", **pad
        )
        self.name_var = tk.StringVar(value=gift_name)
        ttk.Entry(frm, textvariable=self.name_var, width=44).grid(
            row=1, column=0, sticky="we", padx=10
        )

        self.gift_names_editor = GiftNameListEditor(
            frm, username=self.username, initial=trigger_gift_names,
        )
        self.gift_names_editor.grid(row=2, column=0, sticky="we", padx=10, pady=(8, 0))

        self.enabled_var = tk.BooleanVar(value=enabled)
        ttk.Checkbutton(
            frm,
            text="Recompensa ativa (desmarque pra desligar temporariamente, sem apagar a configuração)",
            variable=self.enabled_var,
        ).grid(row=3, column=0, sticky="w", padx=10, pady=(8, 0))

        ttk.Label(frm, text="Conjunto de roupa a vestir (opcional):").grid(
            row=4, column=0, sticky="w", **pad
        )
        self.outfit_var = tk.StringVar(value=outfit_name or NO_OUTFIT)
        ttk.Combobox(
            frm, textvariable=self.outfit_var, values=self.outfit_options,
            state="readonly", width=30,
        ).grid(row=5, column=0, sticky="w", padx=10)

        self.targets_editor = TargetListEditor(
            frm, "Alvos extras (além do conjunto acima, opcional)",
            on_test_target=self.on_test_target, initial=extra_targets, height=4,
        )
        self.targets_editor.grid(row=6, column=0, sticky="we", padx=10, pady=(10, 0))

        # --- Duracao / fila exclusiva -----------------------------------
        duration_frame = ttk.LabelFrame(frm, text="Duração (opcional — fila exclusiva)", padding=6)
        duration_frame.grid(row=7, column=0, sticky="we", padx=10, pady=(10, 0))

        self.has_duration_var = tk.BooleanVar(value=duration_value is not None)
        ttk.Checkbutton(
            duration_frame,
            text="Esta recompensa fica ativa por um tempo e depois volta ao padrão "
                 "(se marcado, entra numa fila: não sobrepõe outra recompensa com "
                 "duração que já esteja ativa)",
            variable=self.has_duration_var,
            command=self._update_duration_state,
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(duration_frame, text="Duração:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.duration_var = tk.StringVar(
            value=str(duration_value) if duration_value is not None else "10"
        )
        self.duration_entry = ttk.Entry(duration_frame, textvariable=self.duration_var, width=10)
        self.duration_entry.grid(row=1, column=1, sticky="w", padx=(4, 0), pady=(6, 0))
        self.duration_unit_var = tk.StringVar(value=duration_unit)
        self.duration_unit_combo = ttk.Combobox(
            duration_frame, textvariable=self.duration_unit_var,
            values=["minutos", "segundos"], state="readonly", width=9,
        )
        self.duration_unit_combo.grid(row=1, column=2, sticky="w", padx=(6, 0), pady=(6, 0))
        ttk.Label(
            duration_frame, text="(ex: 1 minuto, 30 segundos ...)", foreground="#666666"
        ).grid(row=1, column=3, sticky="w", padx=(6, 0), pady=(6, 0))

        ttk.Label(duration_frame, text="Reverter para o conjunto (opcional):").grid(
            row=2, column=0, columnspan=3, sticky="w", pady=(8, 0)
        )
        self.revert_outfit_var = tk.StringVar(value=revert_outfit_name or NO_OUTFIT)
        self.revert_outfit_combo = ttk.Combobox(
            duration_frame, textvariable=self.revert_outfit_var, values=self.outfit_options,
            state="readonly", width=30,
        )
        self.revert_outfit_combo.grid(row=3, column=0, columnspan=3, sticky="w")

        self.revert_editor = TargetListEditor(
            duration_frame,
            "Alvos extras de revert (opcional — se tudo vazio, usa a roupa padrão global)",
            on_test_target=self.on_test_target, initial=revert_extra_targets, height=3,
        )
        self.revert_editor.grid(row=4, column=0, columnspan=3, sticky="we", pady=(8, 0))

        self.ignore_queue_var = tk.BooleanVar(value=ignore_queue)
        self.ignore_queue_check = ttk.Checkbutton(
            duration_frame,
            text="Ignorar a fila (roda em paralelo — não espera nem bloqueia "
                 "outros presentes com duração; bom pra ações rápidas tipo um "
                 "\"boop\" que não devem esperar uma troca de roupa)",
            variable=self.ignore_queue_var,
        )
        self.ignore_queue_check.grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))

        self._update_duration_state()

        final_btns = ttk.Frame(frm)
        final_btns.grid(row=8, column=0, pady=(14, 0))
        ttk.Button(final_btns, text="Salvar presente", command=self._on_ok).pack(
            side="left", padx=4
        )
        ttk.Button(final_btns, text="Cancelar", command=self.destroy).pack(
            side="left", padx=4
        )

    def _update_duration_state(self):
        state = "readonly" if self.has_duration_var.get() else "disabled"
        self.duration_entry.configure(state="normal" if self.has_duration_var.get() else "disabled")
        self.duration_unit_combo.configure(state=state)
        self.revert_outfit_combo.configure(state=state)
        self.ignore_queue_check.configure(
            state="normal" if self.has_duration_var.get() else "disabled"
        )

    def _on_ok(self):
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Nome obrigatório", "Informe o nome da recompensa.", parent=self)
            return

        gift_names = self.gift_names_editor.get_names()
        if not gift_names:
            messagebox.showerror(
                "Nenhum presente",
                "Adicione ao menos um presente do TikTok que deve disparar "
                "esta recompensa.",
                parent=self,
            )
            return

        outfit_name = self.outfit_var.get()
        outfit_name = None if outfit_name == NO_OUTFIT else outfit_name

        extra_targets = self.targets_editor.get_targets()

        if not outfit_name and not extra_targets:
            messagebox.showerror(
                "Nenhum alvo",
                "Escolha um conjunto de roupa e/ou adicione ao menos um alvo extra.",
                parent=self,
            )
            return

        other_names = self.existing_names - (
            {self.editing_original_name} if self.editing_original_name else set()
        )
        if name in other_names:
            messagebox.showerror(
                "Nome duplicado",
                f"Já existe uma recompensa chamada '{name}'. Escolha outro nome.",
                parent=self,
            )
            return

        duration_value = None
        duration_unit = self.duration_unit_var.get()
        revert_outfit_name = None
        revert_extra_targets = []
        if self.has_duration_var.get():
            try:
                duration_value = float(self.duration_var.get().strip().replace(",", "."))
            except ValueError:
                messagebox.showerror(
                    "Duração inválida", "Informe um número válido.", parent=self
                )
                return
            if duration_value <= 0:
                messagebox.showerror(
                    "Duração inválida", "A duração precisa ser maior que zero.", parent=self
                )
                return
            revert_outfit_value = self.revert_outfit_var.get()
            revert_outfit_name = None if revert_outfit_value == NO_OUTFIT else revert_outfit_value
            revert_extra_targets = self.revert_editor.get_targets()

        ignore_queue = self.ignore_queue_var.get() if self.has_duration_var.get() else False

        raw = {"gift_names": gift_names}
        if outfit_name:
            raw["outfit"] = outfit_name
        if len(extra_targets) > 1:
            raw["parameters"] = extra_targets
        elif len(extra_targets) == 1:
            raw.update(extra_targets[0])
        if not self.enabled_var.get():
            raw["enabled"] = False
        if duration_value is not None:
            if duration_unit == "segundos":
                raw["duration_seconds"] = duration_value
            else:
                raw["duration_minutes"] = duration_value
            if ignore_queue:
                raw["ignore_queue"] = True
        if revert_outfit_name:
            raw["revert_outfit"] = revert_outfit_name
        if revert_extra_targets:
            raw["revert"] = revert_extra_targets

        try:
            outfits_parsed = {}
            for outfit_name_key, items in self.outfits_raw.items():
                outfit_rule, _ = parse_gift_rule(outfit_name_key, {"parameters": items})
                outfits_parsed[outfit_name_key] = outfit_rule.targets
            parse_gift_rule(name, raw, outfits=outfits_parsed)
        except ConfigError as exc:
            messagebox.showerror("Configuração inválida", str(exc), parent=self)
            return

        self.result = {
            "name": name,
            "gift_names": gift_names,
            "outfit": outfit_name,
            "extra_targets": extra_targets,
            "duration_value": duration_value,
            "duration_unit": duration_unit,
            "revert_outfit": revert_outfit_name,
            "revert_extra_targets": revert_extra_targets,
            "enabled": self.enabled_var.get(),
            "ignore_queue": ignore_queue,
        }
        self.destroy()


class DefaultRevertDialog(tk.Toplevel):
    """Janela para editar a roupa padrão global (vrchat.default_revert /
    vrchat.default_revert_outfit)."""

    def __init__(self, parent, on_test_target, outfit_names, outfit_name=None, targets=None):
        super().__init__(parent)
        self.title("Roupa padrão (revert global)")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self.outfit_options = [NO_OUTFIT] + list(outfit_names)
        self.result = None

        frm = ttk.Frame(self)
        frm.pack(fill="both", expand=True, padx=10, pady=10)

        ttk.Label(
            frm,
            text="Usada sempre que um presente com duração termina e não define\n"
                 "seu próprio 'reverter para'. Escolha um conjunto pronto OU\n"
                 "defina os alvos manualmente abaixo (se ambos, o conjunto tem prioridade).",
            justify="left",
        ).pack(anchor="w", pady=(0, 6))

        ttk.Label(frm, text="Usar o conjunto:").pack(anchor="w")
        self.outfit_var = tk.StringVar(value=outfit_name or NO_OUTFIT)
        ttk.Combobox(
            frm, textvariable=self.outfit_var, values=self.outfit_options,
            state="readonly", width=30,
        ).pack(anchor="w", pady=(2, 8))

        self.editor = TargetListEditor(
            frm, "Ou definir manualmente", on_test_target=on_test_target,
            initial=targets, height=5,
        )
        self.editor.pack(fill="x")

        btns = ttk.Frame(frm)
        btns.pack(pady=(12, 0))
        ttk.Button(btns, text="Salvar", command=self._on_ok).pack(side="left", padx=4)
        ttk.Button(btns, text="Cancelar", command=self.destroy).pack(side="left", padx=4)

    def _on_ok(self):
        outfit_value = self.outfit_var.get()
        outfit_name = None if outfit_value == NO_OUTFIT else outfit_value
        targets = self.editor.get_targets()

        if not outfit_name and not targets:
            messagebox.showerror(
                "Nada definido",
                "Escolha um conjunto ou defina ao menos um alvo manualmente.",
                parent=self,
            )
            return

        self.result = {"outfit": outfit_name, "targets": targets}
        self.destroy()


class AvatarParametersDialog(tk.Toplevel):
    """
    Le e mostra os parametros do avatar atual, a partir dos arquivos que
    o proprio VRChat grava em disco (%USERPROFILE%\\AppData\\LocalLow\\
    VRChat\\VRChat\\OSC\\...). Permite copiar nome/endereco, usar um
    parametro direto para criar um novo alvo, ou -- se a busca automática
    não achar nada -- abrir um arquivo manualmente e ver o diagnóstico
    exato do que deu errado.
    """

    def __init__(self, parent, on_use_parameter=None):
        super().__init__(parent)
        self.title("Parâmetros do avatar (lidos do VRChat)")
        self.geometry("680x480")
        self.transient(parent)
        self.grab_set()

        self.on_use_parameter = on_use_parameter
        self.avatars = []
        self.current_params = []
        self._visible_params = []

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        top = ttk.Frame(frm)
        top.pack(fill="x")
        ttk.Label(top, text="Avatar:").pack(side="left")
        self.avatar_var = tk.StringVar()
        self.avatar_combo = ttk.Combobox(
            top, textvariable=self.avatar_var, state="readonly", width=42
        )
        self.avatar_combo.pack(side="left", padx=(4, 8))
        self.avatar_combo.bind("<<ComboboxSelected>>", lambda _e: self._load_selected_avatar())
        ttk.Button(top, text="Atualizar lista", command=self._scan).pack(side="left")
        ttk.Button(
            top, text="Abrir arquivo manualmente...", command=self._open_manual_file
        ).pack(side="left", padx=(8, 0))

        self.info_label = ttk.Label(frm, text="", foreground="#666666", justify="left")
        self.info_label.pack(anchor="w", pady=(6, 6))

        filter_frame = ttk.Frame(frm)
        filter_frame.pack(fill="x", pady=(0, 6))
        ttk.Label(filter_frame, text="Filtrar (nome ou endereço):").pack(side="left")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_a: self._refresh_tree())
        filter_entry = ttk.Entry(filter_frame, textvariable=self.filter_var)
        filter_entry.pack(side="left", fill="x", expand=True, padx=(6, 6))
        ttk.Button(filter_frame, text="Limpar", command=lambda: self.filter_var.set("")).pack(
            side="left"
        )
        self.count_label = ttk.Label(filter_frame, text="", foreground="#666666")
        self.count_label.pack(side="left", padx=(8, 0))
        filter_entry.focus_set()

        columns = ("nome", "endereco", "tipo", "gravavel")
        self.tree = ttk.Treeview(frm, columns=columns, show="headings")
        self.tree.heading("nome", text="Nome do parâmetro")
        self.tree.heading("endereco", text="Endereço OSC")
        self.tree.heading("tipo", text="Tipo")
        self.tree.heading("gravavel", text="Pode setar?")
        self.tree.column("nome", width=160)
        self.tree.column("endereco", width=250)
        self.tree.column("tipo", width=60, anchor="center")
        self.tree.column("gravavel", width=90, anchor="center")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-1>", lambda _e: self._use_selected())

        scroll = ttk.Scrollbar(frm, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="Copiar nome", command=self._copy_name).pack(side="left", padx=2)
        ttk.Button(btns, text="Copiar endereço", command=self._copy_address).pack(side="left", padx=2)
        if self.on_use_parameter is not None:
            ttk.Button(
                btns, text="Usar este parâmetro...", command=self._use_selected
            ).pack(side="left", padx=(12, 2))
        ttk.Button(btns, text="Fechar", command=self.destroy).pack(side="right", padx=2)

        self._scan()

    def _scan(self):
        from vrchat.discovery import find_avatars

        self.avatars, diagnostics = find_avatars()

        if not self.avatars:
            osc_dir = diagnostics.osc_dir
            if osc_dir is None:
                self.info_label.configure(
                    text="Não encontrei a pasta de configs do VRChat neste computador "
                    "(isso só funciona no Windows, com o VRChat já aberto).\n"
                    "Você pode usar 'Abrir arquivo manualmente...' para apontar direto "
                    "para um .json, ou digitar os parâmetros manualmente."
                )
            elif diagnostics.json_files_found == 0:
                self.info_label.configure(
                    text=f"Nenhum arquivo de avatar encontrado em:\n{osc_dir}\n"
                    "Carregue o avatar no VRChat com OSC habilitado (Action Menu → "
                    "OSC → Enabled) pelo menos uma vez, e clique em 'Atualizar lista'."
                )
            else:
                error_lines = "\n".join(
                    f"  • {os.path.basename(path)}: {reason}"
                    for path, reason in diagnostics.errors[:6]
                )
                more = ""
                if len(diagnostics.errors) > 6:
                    more = f"\n  ... e mais {len(diagnostics.errors) - 6} arquivo(s)."
                self.info_label.configure(
                    text=f"Encontrei {diagnostics.json_files_found} arquivo(s) em "
                    f"{osc_dir}, mas não consegui ler nenhum:\n{error_lines}{more}\n"
                    f"Use 'Abrir arquivo manualmente...' para escolher um .json "
                    f"específico e ver o motivo com mais detalhe."
                )
            self.avatar_combo.configure(values=[])
            self.tree.delete(*self.tree.get_children())
            return

        labels = [a.label for a in self.avatars]
        self.avatar_combo.configure(values=labels)
        self.avatar_var.set(labels[0])
        extra = ""
        if diagnostics.errors:
            extra = f" ({len(diagnostics.errors)} arquivo(s) não puderam ser lidos.)"
        self.info_label.configure(
            text=f"{len(self.avatars)} avatar(es) encontrado(s){extra} "
            f"Selecionado: mais recente."
        )
        self._load_selected_avatar()

    def _open_manual_file(self):
        from tkinter import filedialog

        from vrchat.discovery import parse_avatar_config_file

        path = filedialog.askopenfilename(
            parent=self,
            title="Escolher arquivo de config do avatar (.json)",
            filetypes=[("Arquivos JSON", "*.json"), ("Todos os arquivos", "*.*")],
        )
        if not path:
            return

        avatar, error = parse_avatar_config_file(path)
        if avatar is None:
            preview = ""
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    preview = f.read(400)
            except OSError:
                pass
            messagebox.showerror(
                "Não consegui ler este arquivo",
                f"Motivo: {error}\n\n"
                + (f"Início do arquivo:\n{preview}" if preview else ""),
                parent=self,
            )
            return

        if avatar not in self.avatars:
            self.avatars.append(avatar)
        labels = [a.label for a in self.avatars]
        self.avatar_combo.configure(values=labels)
        self.avatar_var.set(avatar.label)
        self.info_label.configure(
            text=f"Carregado manualmente: {os.path.basename(path)} "
            f"({len(avatar.parameters)} parâmetro(s))."
        )
        self._load_selected_avatar()



    def _load_selected_avatar(self):
        label = self.avatar_var.get()
        avatar = next((a for a in self.avatars if a.label == label), None)
        self.current_params = avatar.parameters if avatar is not None else []
        self._refresh_tree()

    def _refresh_tree(self):
        term = self.filter_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        self._visible_params = []
        for p in self.current_params:
            if term and term not in p.name.lower() and term not in p.address.lower():
                continue
            iid = str(len(self._visible_params))
            self._visible_params.append(p)
            self.tree.insert(
                "", "end", iid=iid,
                values=(p.name, p.address, p.osc_type, "sim" if p.writable else "não"),
            )
        total = len(self.current_params)
        shown = len(self._visible_params)
        self.count_label.configure(
            text=f"{shown} de {total}" if term else f"{total} parâmetro(s)"
        )

    def _selected_param(self):
        sel = self.tree.selection()
        if not sel:
            return None
        return self._visible_params[int(sel[0])]

    def _copy_name(self):
        p = self._selected_param()
        if p is None:
            messagebox.showinfo("Nada selecionado", "Selecione um parâmetro na lista.", parent=self)
            return
        self.clipboard_clear()
        self.clipboard_append(p.name)

    def _copy_address(self):
        p = self._selected_param()
        if p is None:
            messagebox.showinfo("Nada selecionado", "Selecione um parâmetro na lista.", parent=self)
            return
        self.clipboard_clear()
        self.clipboard_append(p.address)

    def _use_selected(self):
        p = self._selected_param()
        if p is None:
            messagebox.showinfo("Nada selecionado", "Selecione um parâmetro na lista.", parent=self)
            return
        if not p.writable:
            if not messagebox.askyesno(
                "Parâmetro somente leitura",
                f"'{p.name}' parece ser somente leitura (o avatar só ENVIA esse "
                f"valor, não recebe). Provavelmente não serve para trocar roupa. "
                f"Usar mesmo assim?",
                parent=self,
            ):
                return
        if self.on_use_parameter is not None:
            self.on_use_parameter(p.name, p.loader_type, address=p.address)


class LiveParametersDialog(tk.Toplevel):
    """
    "Modo escuta": mostra em tempo real os parâmetros que o PRÓPRIO
    VRChat manda pra fora quando algo muda no avatar (troca de roupa
    pelo menu de expressões, gestos, etc). Serve pra descobrir qual
    número corresponde a qual opção visual, sem precisar adivinhar --
    isso não existe em nenhum arquivo, só é possível ver "ao vivo".

    Mostra uma linha por endereço (o valor mais recente + quantas vezes
    mudou), não um log crescendo infinito -- assim parâmetros ruidosos
    (Viseme, GestureLeft, velocidade...) não enchem a tela.
    """

    def __init__(self, parent, async_loop, on_use_parameter=None):
        super().__init__(parent)
        self.title("Descobrir valores ao vivo (modo escuta)")
        self.geometry("620x460")
        self.transient(parent)

        self.async_loop = async_loop
        self.on_use_parameter = on_use_parameter
        self.listener = None
        self.rows: dict[str, tuple[object, int]] = {}  # address -> (last_value, count)
        self._visible_addresses: list[str] = []

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        ttk.Label(
            frm,
            text="Inicie a escuta, depois troque de roupa/acessório pelo menu de\n"
                 "expressões do VRChat (ou faça gestos) -- o valor exato que o jogo\n"
                 "manda pra fora aparece aqui na hora.",
            justify="left",
        ).pack(anchor="w", pady=(0, 6))

        top = ttk.Frame(frm)
        top.pack(fill="x")
        ttk.Label(top, text="Porta de escuta:").pack(side="left")
        self.port_var = tk.StringVar(value="9001")
        ttk.Entry(top, textvariable=self.port_var, width=8).pack(side="left", padx=(4, 10))
        self.start_btn = ttk.Button(top, text="Iniciar escuta", command=self._on_start)
        self.start_btn.pack(side="left", padx=2)
        self.stop_btn = ttk.Button(
            top, text="Parar escuta", command=self._on_stop, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=2)
        ttk.Button(top, text="Limpar lista", command=self._on_clear).pack(side="left", padx=(10, 2))

        self.status_label = ttk.Label(frm, text="Parado.", foreground="#888888")
        self.status_label.pack(anchor="w", pady=(4, 6))

        filter_frame = ttk.Frame(frm)
        filter_frame.pack(fill="x", pady=(0, 6))
        ttk.Label(filter_frame, text="Filtrar:").pack(side="left")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_a: self._refresh_tree())
        ttk.Entry(filter_frame, textvariable=self.filter_var).pack(
            side="left", fill="x", expand=True, padx=(6, 0)
        )

        columns = ("endereco", "valor", "vezes")
        self.tree = ttk.Treeview(frm, columns=columns, show="headings")
        self.tree.heading("endereco", text="Endereço")
        self.tree.heading("valor", text="Último valor")
        self.tree.heading("vezes", text="Vezes visto")
        self.tree.column("endereco", width=300)
        self.tree.column("valor", width=140, anchor="center")
        self.tree.column("vezes", width=90, anchor="center")
        self.tree.pack(fill="both", expand=True)

        scroll = ttk.Scrollbar(frm, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(8, 0))
        ttk.Button(btns, text="Copiar endereço", command=self._copy_address).pack(
            side="left", padx=2
        )
        if self.on_use_parameter is not None:
            ttk.Button(
                btns, text="Usar como alvo...", command=self._use_selected
            ).pack(side="left", padx=(12, 2))
        ttk.Button(btns, text="Fechar", command=self._on_close).pack(side="right", padx=2)

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _on_start(self) -> None:
        if self.async_loop is None:
            messagebox.showerror("Erro interno", "O loop assíncrono não está pronto ainda.", parent=self)
            return
        try:
            port = int(self.port_var.get().strip())
        except ValueError:
            messagebox.showerror("Porta inválida", "A porta precisa ser um número.", parent=self)
            return

        from vrchat.osc_listener import VRChatOscListener

        listener = VRChatOscListener(on_message=self._on_message_any_thread, port=port)

        async def _run():
            await listener.start()

        import asyncio

        future = asyncio.run_coroutine_threadsafe(_run(), self.async_loop)
        try:
            future.result(timeout=3)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(
                "Não foi possível escutar nessa porta",
                f"{exc}\n\nSe já tiver outro programa escutando na mesma porta "
                f"(ex: o próprio config.yaml usando a mesma porta pra outra coisa), "
                f"tente uma porta diferente.",
                parent=self,
            )
            return

        self.listener = listener
        self.status_label.configure(
            text=f"Escutando na porta {port}. Troque algo no VRChat agora.",
            foreground="#1a8a1a",
        )
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")

    def _on_message_any_thread(self, address: str, args: tuple) -> None:
        value = args[0] if args else None
        self.after(0, lambda: self._record(address, value))

    def _record(self, address: str, value) -> None:
        _, count = self.rows.get(address, (None, 0))
        self.rows[address] = (value, count + 1)
        self._refresh_tree()

    def _refresh_tree(self) -> None:
        term = self.filter_var.get().strip().lower()
        self.tree.delete(*self.tree.get_children())
        self._visible_addresses = []
        for address, (value, count) in sorted(self.rows.items()):
            if term and term not in address.lower():
                continue
            self._visible_addresses.append(address)
            self.tree.insert("", "end", iid=address, values=(address, repr(value), count))

    def _on_clear(self) -> None:
        self.rows.clear()
        self._refresh_tree()

    def _on_stop(self) -> None:
        if self.listener is not None and self.async_loop is not None:
            listener = self.listener

            async def _run():
                await listener.stop()

            import asyncio

            asyncio.run_coroutine_threadsafe(_run(), self.async_loop)
            self.listener = None
        self.status_label.configure(text="Parado.", foreground="#888888")
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")

    def _on_close(self) -> None:
        self._on_stop()
        self.destroy()

    def _selected_address(self):
        sel = self.tree.selection()
        return sel[0] if sel else None

    def _copy_address(self) -> None:
        address = self._selected_address()
        if address is None:
            messagebox.showinfo("Nada selecionado", "Selecione uma linha na lista.", parent=self)
            return
        self.clipboard_clear()
        self.clipboard_append(address)

    def _use_selected(self) -> None:
        address = self._selected_address()
        if address is None:
            messagebox.showinfo("Nada selecionado", "Selecione uma linha na lista.", parent=self)
            return
        value, _count = self.rows[address]
        name = address.rsplit("/", 1)[-1]
        if isinstance(value, bool):
            osc_type = "bool"
        elif isinstance(value, int):
            osc_type = "int"
        elif isinstance(value, float):
            osc_type = "float"
        else:
            osc_type = "string"
        if self.on_use_parameter is not None:
            self.on_use_parameter(name, osc_type, value, address)


class QueueStatusDialog(tk.Toplevel):
    """
    Mostra o que está acontecendo na fila de presentes com duração
    agora: o item ativo (com tempo restante aproximado) e os que estão
    esperando. Tem um botão pra atualizar (a fila muda com o tempo) e
    um pra limpar tudo.
    """

    def __init__(self, parent, get_status, on_clear):
        super().__init__(parent)
        self.title("Fila de presentes")
        self.geometry("480x380")
        self.transient(parent)

        self.get_status = get_status
        self.on_clear = on_clear

        frm = ttk.Frame(self, padding=10)
        frm.pack(fill="both", expand=True)

        self.active_label = ttk.Label(frm, text="", justify="left")
        self.active_label.pack(anchor="w", pady=(0, 8))

        ttk.Label(frm, text="Esperando na fila:").pack(anchor="w")
        columns = ("posicao", "presente", "usuario", "duracao")
        self.tree = ttk.Treeview(frm, columns=columns, show="headings", height=8)
        self.tree.heading("posicao", text="#")
        self.tree.heading("presente", text="Recompensa")
        self.tree.heading("usuario", text="De")
        self.tree.heading("duracao", text="Duração")
        self.tree.column("posicao", width=30, anchor="center")
        self.tree.column("presente", width=150)
        self.tree.column("usuario", width=140)
        self.tree.column("duracao", width=80, anchor="center")
        self.tree.pack(fill="both", expand=True, pady=(4, 0))

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(10, 0))
        ttk.Button(btns, text="Atualizar", command=self._refresh).pack(side="left", padx=2)
        ttk.Button(btns, text="Limpar fila", command=self._on_clear_clicked).pack(
            side="left", padx=(12, 2)
        )
        ttk.Button(btns, text="Fechar", command=self.destroy).pack(side="right", padx=2)

        self._refresh()

    def _refresh(self):
        current, pending = self.get_status()

        if current is None:
            self.active_label.configure(
                text="Nenhuma recompensa ativa agora.", foreground="#888888"
            )
        else:
            remaining = (
                f"{current.remaining_seconds:.0f}s restante(s)"
                if current.remaining_seconds is not None else "?"
            )
            self.active_label.configure(
                text=f"Ativo agora: '{current.gift_name}' (de {current.user_name}) "
                f"— {remaining}",
                foreground="#1a8a1a",
            )

        self.tree.delete(*self.tree.get_children())
        for idx, item in enumerate(pending, start=1):
            minutes = item.duration_seconds / 60
            duration_label = (
                f"{int(minutes)} min" if minutes == int(minutes) and minutes >= 1
                else f"{item.duration_seconds:.0f}s"
            )
            self.tree.insert(
                "", "end", values=(idx, item.gift_name, item.user_name, duration_label)
            )

    def _on_clear_clicked(self):
        if not messagebox.askyesno(
            "Limpar fila?",
            "Isso cancela a recompensa ativa e todas as que estão esperando na "
            "fila (sem reverter pra roupa padrão automaticamente).\n\nContinuar?",
            parent=self,
        ):
            return
        self.on_clear()
        self._refresh()
