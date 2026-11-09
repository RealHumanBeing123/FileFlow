"""Media Converter GUI (Tkinter). Run: python app.py"""

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import converter as cv


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Media Converter")
        self.minsize(560, 460)
        self.source: Path | None = None
        self.out_dir: Path | None = None
        self.q: queue.Queue = queue.Queue()
        self.cancel = threading.Event()
        self.worker: threading.Thread | None = None
        self._build()
        self._on_category()
        self.after(100, self._poll)
        if not cv.find_ffmpeg():
            messagebox.showwarning(
                "FFmpeg not found",
                "FFmpeg must be installed and on your PATH.\n"
                "Download it from https://ffmpeg.org")

    # ------------------------------------------------------------- layout
    def _build(self):
        pad = {"padx": 10, "pady": 6}
        frm = ttk.Frame(self, padding=8)
        frm.pack(fill="both", expand=True)
        frm.columnconfigure(1, weight=1)

        # Source
        ttk.Label(frm, text="Source").grid(row=0, column=0, sticky="w", **pad)
        self.src_var = tk.StringVar(value="(nothing selected)")
        ttk.Label(frm, textvariable=self.src_var, relief="sunken",
                  anchor="w").grid(row=0, column=1, sticky="ew", **pad)
        bf = ttk.Frame(frm)
        bf.grid(row=0, column=2, **pad)
        ttk.Button(bf, text="File…", command=self._pick_file).pack(side="left")
        ttk.Button(bf, text="Folder…", command=self._pick_folder).pack(side="left", padx=(4, 0))

        self.recursive = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="Include subfolders (folder mode)",
                        variable=self.recursive).grid(row=1, column=1, sticky="w", padx=10)

        # Output folder (required)
        ttk.Label(frm, text="Output folder").grid(row=2, column=0, sticky="w", **pad)
        self.out_var = tk.StringVar(value="(required)")
        ttk.Label(frm, textvariable=self.out_var, relief="sunken",
                  anchor="w").grid(row=2, column=1, sticky="ew", **pad)
        ttk.Button(frm, text="Choose…", command=self._pick_out).grid(row=2, column=2, **pad)

        # Type, format, quality
        ttk.Label(frm, text="Media type").grid(row=3, column=0, sticky="w", **pad)
        self.cat = ttk.Combobox(frm, values=list(cv.CATEGORIES), state="readonly")
        self.cat.set("Audio")
        self.cat.grid(row=3, column=1, sticky="w", **pad)
        self.cat.bind("<<ComboboxSelected>>", lambda e: self._on_category())

        ttk.Label(frm, text="Convert to").grid(row=4, column=0, sticky="w", **pad)
        self.fmt = ttk.Combobox(frm, state="readonly")
        self.fmt.grid(row=4, column=1, sticky="w", **pad)
        self.fmt.bind("<<ComboboxSelected>>", lambda e: self._on_format())

        ttk.Label(frm, text="Quality").grid(row=5, column=0, sticky="w", **pad)
        self.quality = ttk.Combobox(frm, state="readonly", width=28)
        self.quality.grid(row=5, column=1, sticky="w", **pad)
        self.q_note = ttk.Label(frm, text="", foreground="gray")
        self.q_note.grid(row=6, column=1, sticky="w", padx=10)

        # Actions
        af = ttk.Frame(frm)
        af.grid(row=7, column=0, columnspan=3, pady=(14, 6))
        self.go = ttk.Button(af, text="Convert", command=self._start)
        self.go.pack(side="left")
        self.stop = ttk.Button(af, text="Cancel", command=self.cancel.set, state="disabled")
        self.stop.pack(side="left", padx=6)

        self.bar = ttk.Progressbar(frm, mode="determinate")
        self.bar.grid(row=8, column=0, columnspan=3, sticky="ew", **pad)

        self.log = tk.Text(frm, height=9, state="disabled", wrap="none")
        self.log.grid(row=9, column=0, columnspan=3, sticky="nsew", **pad)
        frm.rowconfigure(9, weight=1)

    # ------------------------------------------------------------ choices
    def _on_category(self):
        c = self.cat.get()
        self.fmt["values"] = cv.OUTPUT_FORMATS[c]
        self.fmt.current(0)
        self.quality["values"] = cv.QUALITY_LEVELS[c]
        self.quality.current(cv.DEFAULT_QUALITY[c])
        self._on_format()

    def _on_format(self):
        c, f = self.cat.get(), self.fmt.get()
        lossless = (c == "Audio" and f in cv.LOSSLESS_AUDIO) or \
                   (c == "Image" and f in ("png", "bmp", "tiff", "gif"))
        self.quality.configure(state="disabled" if lossless and
                               not (c == "Image" and f == "png") else "readonly")
        notes = {True: "This format is lossless; quality setting has little or no effect."}
        self.q_note.configure(text=notes.get(lossless, ""))

    def _pick_file(self):
        exts = " ".join(f"*{e}" for e in sorted(cv.CATEGORIES[self.cat.get()]))
        p = filedialog.askopenfilename(
            title="Choose a file",
            filetypes=[(f"{self.cat.get()} files", exts), ("All files", "*.*")])
        if p:
            self._set_source(Path(p))

    def _pick_folder(self):
        p = filedialog.askdirectory(title="Choose a folder of files")
        if p:
            self._set_source(Path(p))

    def _set_source(self, path: Path):
        self.source = path
        self.src_var.set(str(path))
        if path.is_file():
            c = cv.category_of(path)
            if c:
                self.cat.set(c)
                self._on_category()

    def _pick_out(self):
        p = filedialog.askdirectory(title="Choose output folder")
        if p:
            self.out_dir = Path(p)
            self.out_var.set(p)

    # ---------------------------------------------------------- running
    def _log(self, text: str):
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def _start(self):
        if not self.source:
            return messagebox.showinfo("Select a source", "Choose a file or a folder first.")
        if not self.out_dir:
            return messagebox.showinfo("Select output folder",
                                       "You must choose an output folder.")
        cat = self.cat.get()
        files = cv.collect_files(self.source, cat, self.recursive.get())
        if not files:
            return messagebox.showinfo("Nothing to convert",
                                       f"No {cat.lower()} files found in the selection.")
        self.cancel.clear()
        self.go.configure(state="disabled")
        self.stop.configure(state="normal")
        self.bar.configure(value=0, maximum=len(files))
        self._log(f"Converting {len(files)} file(s) to .{self.fmt.get()} …")
        args = (files, self.out_dir, cat, self.fmt.get(), self.quality.current())
        self.worker = threading.Thread(target=self._work, args=args, daemon=True)
        self.worker.start()

    def _work(self, files, out_dir, cat, fmt, qi):
        try:
            results = cv.convert_batch(
                files, out_dir, cat, fmt, qi,
                on_progress=lambda i, n, r: self.q.put(("progress", i, r)),
                should_cancel=self.cancel.is_set)
            self.q.put(("done", results))
        except Exception as e:  # e.g. FFmpeg missing
            self.q.put(("error", str(e)))

    def _poll(self):
        try:
            while True:
                msg = self.q.get_nowait()
                if msg[0] == "progress":
                    _, i, r = msg
                    self.bar.configure(value=i)
                    self._log(("OK    " if r.ok else "FAIL  ") + r.src.name +
                              ("" if r.ok else f"  — {r.message}"))
                elif msg[0] == "done":
                    res = msg[1]
                    ok = sum(r.ok for r in res)
                    self._log(f"Finished: {ok} succeeded, {len(res) - ok} failed"
                              + (" (cancelled)" if self.cancel.is_set() else "") + ".")
                    self._idle()
                elif msg[0] == "error":
                    messagebox.showerror("Error", msg[1])
                    self._idle()
        except queue.Empty:
            pass
        self.after(100, self._poll)

    def _idle(self):
        self.go.configure(state="normal")
        self.stop.configure(state="disabled")


if __name__ == "__main__":
    App().mainloop()
