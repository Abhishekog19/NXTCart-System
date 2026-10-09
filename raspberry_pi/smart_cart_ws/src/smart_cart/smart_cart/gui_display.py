#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
import tkinter as tk
from tkinter import font as tkfont
from collections import Counter
import qrcode
from PIL import Image, ImageTk
from std_msgs.msg import String
import json
import time
import uuid
from urllib.parse import urlencode
from .core_logic import retained_qos

from smart_cart_interfaces.msg import CartState

class CartGUINode(Node):
    def __init__(self, gui_app):
        super().__init__('premium_gui')
        self.gui_app = gui_app
        gui_app.node = self
        self.remove_pub = self.create_publisher(String, '/cart/remove_request', 10)
        self.checkout_pub = self.create_publisher(String, '/cart/checkout_request', 10)
        self.create_subscription(CartState, '/cart/ui_display', self.ui_callback, retained_qos())
        self.create_subscription(String, '/cart/alerts', self.alert_callback, 10)
        self.create_subscription(String, '/cart/checkout_quote', self.quote_callback, 10)

    def quote_callback(self, msg):
        try:
            self.gui_app.show_quote(json.loads(msg.data))
        except (ValueError, TypeError, KeyError):
            self.gui_app.show_alert('Invalid checkout response')

    def remove(self, txn_id):
        msg = String(); msg.data = txn_id
        self.remove_pub.publish(msg)

    def request_checkout(self, revision, request_id):
        msg = String(); msg.data = json.dumps({'revision': revision, 'request_id': request_id})
        self.checkout_pub.publish(msg)

    def ui_callback(self, msg):
        self.gui_app.root.after(0, self.gui_app.update_cart, msg)

    def alert_callback(self, msg):
        self.gui_app.root.after(0, self.gui_app.show_alert, msg.data)

class CartGUI:
    BG        = "#ffffff"
    SIDEBAR   = "#f5f5f5"
    PRIMARY   = "#1a1a1a"
    SECONDARY = "#555555"
    MUTED     = "#999999"
    DIVIDER   = "#d9d9d9"
    BLACK     = "#000000"
    WHITE     = "#ffffff"

    COL_PRICE = 90
    COL_TOTAL = 90

    def __init__(self, root):
        self.root = root
        self.root.title("My Shopping Bag")
        self.root.geometry("1000x540")
        self.root.configure(bg=self.BG)

        self.current_total = 0.0
        self.checkout_allowed = False
        self.checkout_reason = 'Waiting for cart verification'
        self.revision = 0
        self.received_at = 0.0
        self.rendered = None
        self.status_labels = []
        self.spinner = 0
        self.popup = None
        self.quote_request = None

        self.f_title   = tkfont.Font(family="Helvetica", size=15, weight="bold")
        self.f_heading = tkfont.Font(family="Helvetica", size=9,  weight="bold")
        self.f_name    = tkfont.Font(family="Helvetica", size=11, weight="bold")
        self.f_detail  = tkfont.Font(family="Helvetica", size=9)
        self.f_price   = tkfont.Font(family="Helvetica", size=11)
        self.f_side    = tkfont.Font(family="Helvetica", size=10)
        self.f_side_b  = tkfont.Font(family="Helvetica", size=11, weight="bold")
        self.f_total_l = tkfont.Font(family="Helvetica", size=10, weight="bold")
        self.f_total_v = tkfont.Font(family="Helvetica", size=13, weight="bold")
        self.f_btn     = tkfont.Font(family="Helvetica", size=11, weight="bold")
        self.f_small   = tkfont.Font(family="Helvetica", size=8)

        self.alert_frame = tk.Frame(root, bg=self.BLACK, height=40)
        self.alert_label = tk.Label(self.alert_frame, text="", bg=self.BLACK, fg=self.WHITE, font=("Helvetica", 11, "bold"))
        self.alert_label.pack(pady=8)
        self.alert_frame.pack_forget()

        self.main = tk.Frame(root, bg=self.BG)
        self.main.pack(fill=tk.BOTH, expand=True)

        self._build_sidebar()
        self._build_product_pane()
        self.root.after(250, self._animate_status)

    def _build_product_pane(self):
        left = tk.Frame(self.main, bg=self.BG)
        left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pad = 28
        tk.Label(left, text="MY SHOPPING BAG", font=self.f_title, bg=self.BG, fg=self.PRIMARY).pack(anchor="w", padx=pad, pady=(22, 14))
        tk.Frame(left, bg=self.DIVIDER, height=1).pack(fill=tk.X, padx=pad)

        hdr = tk.Frame(left, bg=self.BG)
        hdr.pack(fill=tk.X, padx=pad, pady=(8, 0))
        hdr.columnconfigure(0, weight=1)
        hdr.columnconfigure(1, minsize=self.COL_PRICE)
        hdr.columnconfigure(2, minsize=self.COL_TOTAL)

        tk.Label(hdr, text="PRODUCT", font=self.f_heading, bg=self.BG, fg=self.MUTED, anchor="w").grid(row=0, column=0, sticky="w")
        tk.Label(hdr, text="PRICE", font=self.f_heading, bg=self.BG, fg=self.MUTED, anchor="e").grid(row=0, column=1, sticky="e", padx=(0, 8))
        tk.Label(hdr, text="TOTAL", font=self.f_heading, bg=self.BG, fg=self.MUTED, anchor="e").grid(row=0, column=2, sticky="e")

        tk.Frame(left, bg=self.DIVIDER, height=1).pack(fill=tk.X, padx=pad, pady=(6, 0))

        scroll_wrap = tk.Frame(left, bg=self.BG)
        scroll_wrap.pack(fill=tk.BOTH, expand=True, padx=(pad, 0))

        self.canvas = tk.Canvas(scroll_wrap, bg=self.BG, highlightthickness=0, bd=0)
        self.vsb = tk.Scrollbar(scroll_wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vsb.set)

        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.vsb.pack_forget()

        self.product_frame = tk.Frame(self.canvas, bg=self.BG)
        self._cwin = self.canvas.create_window((0, 0), window=self.product_frame, anchor="nw")

        self.canvas.bind("<Configure>", self._on_canvas_cfg)
        self.product_frame.bind("<Configure>", self._on_pf_cfg)
        self.canvas.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

        self._show_empty()

    def _on_canvas_cfg(self, event):
        self.canvas.itemconfigure(self._cwin, width=event.width)

    def _on_pf_cfg(self, _):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        bbox = self.canvas.bbox("all")
        if bbox and bbox[3] > self.canvas.winfo_height():
            self.vsb.pack(side=tk.RIGHT, fill=tk.Y)
        else:
            self.vsb.pack_forget()

    def _build_sidebar(self):
        right = tk.Frame(self.main, bg=self.SIDEBAR, width=310)
        right.pack(side=tk.RIGHT, fill=tk.Y)
        right.pack_propagate(False)

        tk.Frame(right, bg=self.DIVIDER, width=1).pack(side=tk.LEFT, fill=tk.Y)

        sb = tk.Frame(right, bg=self.SIDEBAR)
        sb.pack(fill=tk.BOTH, expand=True, padx=22, pady=22)

        tk.Label(sb, text="SUMMARY", font=self.f_side_b, bg=self.SIDEBAR, fg=self.PRIMARY).pack(anchor="w")
        tk.Frame(sb, bg="#bbb", height=1).pack(fill=tk.X, pady=(10, 18))

        def _row(label, initial, bold=False):
            f = tk.Frame(sb, bg=self.SIDEBAR)
            f.pack(fill=tk.X, pady=4)
            fn = self.f_side_b if bold else self.f_side
            tk.Label(f, text=label, font=fn, bg=self.SIDEBAR, fg=self.SECONDARY).pack(side=tk.LEFT)
            v = tk.Label(f, text=initial, font=fn, bg=self.SIDEBAR, fg=self.PRIMARY)
            v.pack(side=tk.RIGHT)
            return v

        self.lbl_items    = _row("Total Items",  "0")
        self.lbl_subtotal = _row("SUBTOTAL",     "₹0.00")
        self.lbl_weight   = _row("Live Weight",  "0.0 g")
        _row("Shipping",   "—")
        _row("Sales Tax",  "TBD")

        tk.Frame(sb, bg="#ccc", height=1).pack(fill=tk.X, pady=(12, 10))

        tk.Label(sb, text="ESTIMATED TOTAL", font=self.f_total_l, bg=self.SIDEBAR, fg=self.PRIMARY, anchor="w").pack(fill=tk.X)
        self.lbl_total = tk.Label(sb, text="₹0.00", font=self.f_total_v, bg=self.SIDEBAR, fg=self.PRIMARY, anchor="e")
        self.lbl_total.pack(fill=tk.X, pady=(2, 14))

        btn = tk.Label(sb, text="CHECKOUT", bg=self.BLACK, fg=self.WHITE, font=self.f_btn, pady=14, cursor="hand2")
        btn.pack(fill=tk.X, pady=(0, 12))
        btn.bind("<Button-1>", self._checkout)
        btn.bind("<Enter>", lambda e: btn.config(bg="#333333"))
        btn.bind("<Leave>", lambda e: btn.config(bg=self.BLACK))
        self.checkout_button = btn

        tk.Label(sb, text="Need help? Smart Cart v2.0", font=self.f_small, bg=self.SIDEBAR, fg=self.MUTED).pack(anchor="w")

    def _make_row(self, name, weight, qty, unit_price, line_total, item=None):
        row = tk.Frame(self.product_frame, bg=self.BG)
        row.pack(fill=tk.X)
        row.columnconfigure(0, weight=1)
        row.columnconfigure(1, minsize=self.COL_PRICE)
        row.columnconfigure(2, minsize=self.COL_TOTAL)

        info = tk.Frame(row, bg=self.BG)
        info.grid(row=0, column=0, sticky="nsw", pady=(14, 14), padx=(0, 10))

        tk.Label(info, text=name.upper(), font=self.f_name, bg=self.BG, fg=self.PRIMARY, anchor="w").pack(anchor="w")
        tk.Label(info, text=f"WEIGHT: {weight:.0f}g", font=self.f_detail, bg=self.BG, fg=self.MUTED, anchor="w").pack(anchor="w", pady=(2, 0))
        tk.Label(info, text=f"QTY: {qty}", font=self.f_detail, bg=self.BG, fg=self.MUTED, anchor="w").pack(anchor="w")
        if item is not None:
            colors = {'VERIFIED': '#16803c', 'FLAGGED': '#bf3030', 'VERIFYING': '#b67a16', 'REMOVING': '#b67a16'}
            label = tk.Label(info, text='', font=self.f_small, bg=self.BG,
                             fg=colors.get(item.status, self.MUTED), anchor='w')
            label.pack(anchor='w', pady=(3, 0))
            self.status_labels.append((label, item))
            remove = tk.Label(info, text='Remove', font=self.f_small, bg=self.BG,
                              fg=self.SECONDARY, cursor='hand2')
            remove.pack(anchor='w', pady=(2, 0))
            remove.bind('<Button-1>', lambda event, txn=item.txn_id: self.node.remove(txn))
            if item.reason and item.status == 'FLAGGED':
                tk.Label(info, text=item.reason, font=self.f_small, bg=self.BG, fg='#bf3030',
                         wraplength=310, justify='left').pack(anchor='w')

        tk.Label(row, text=f"₹{unit_price:.2f}", font=self.f_price, bg=self.BG, fg=self.PRIMARY, anchor="e").grid(row=0, column=1, sticky="ne", pady=14, padx=(0, 8))
        tk.Label(row, text=f"₹{line_total:.2f}", font=self.f_price, bg=self.BG, fg=self.PRIMARY, anchor="e").grid(row=0, column=2, sticky="ne", pady=14, padx=(0, 4))
        tk.Frame(self.product_frame, bg=self.DIVIDER, height=1).pack(fill=tk.X)

    def _show_empty(self):
        for w in self.product_frame.winfo_children():
            w.destroy()
        tk.Label(self.product_frame, text="Your cart is empty.\nScan items to get started.", font=("Helvetica", 12), bg=self.BG, fg=self.MUTED, justify="center").pack(pady=80, expand=True)

    def update_cart(self, msg):
        self.current_total = msg.total_price
        self.received_at = time.monotonic()
        self.checkout_allowed, self.checkout_reason, self.revision = msg.checkout_allowed, msg.checkout_reason, msg.revision
        key = tuple((i.txn_id, i.name, i.weight, i.price, i.weight_status, i.camera_status,
                     i.status, i.reason) for i in msg.items)
        if key != self.rendered:
            self.rendered = key
            self.status_labels = []
            for w in self.product_frame.winfo_children():
                w.destroy()
            if not msg.items:
                self._show_empty()
            else:
                for item in msg.items:
                    self._make_row(item.name, item.weight, 1, item.price, item.price, item)
            self._refresh_status()
        if self.popup and self.popup.winfo_exists() and (not msg.checkout_allowed or self.popup.revision != msg.revision):
            self.popup.destroy(); self.popup = None
            self.show_alert('Cart changed. Complete verification before payment.')

        self.lbl_items.config(text=str(msg.total_items))
        self.lbl_subtotal.config(text=f"₹{msg.total_price:.2f}")
        self.lbl_weight.config(text=f"{msg.total_weight:.1f} g")
        self.lbl_total.config(text=f"₹{msg.total_price:.2f}")

    def _refresh_status(self):
        def gate(value):
            return '✓' if value == 'PASS' else '✕' if value == 'FAIL' else '◌◔◑◕'[self.spinner % 4]
        for label, item in self.status_labels:
            suffix = '  ✓ Verified' if item.status == 'VERIFIED' else '  ✕ Check item' if item.status == 'FLAGGED' else ''
            label.config(text=f'Weight {gate(item.weight_status)}   Camera {gate(item.camera_status)}{suffix}')

    def _animate_status(self):
        self.spinner += 1; self._refresh_status()
        if time.monotonic()-self.received_at > 1.5:
            self.checkout_allowed = False
            self.checkout_reason = 'Cart service disconnected'
            if self.popup and self.popup.winfo_exists():
                self.popup.destroy(); self.popup = None
        if self.quote_request and time.monotonic()-self.quote_request[1] > 2.0:
            self.quote_request = None
            self.show_alert('Checkout service did not respond. Try again.')
        self.root.after(250, self._animate_status)

    def show_alert(self, text):
        if not text:
            self.hide_alert()
            return

        self.alert_label.config(text=text)
        # Only pack it if it isn't already visible to prevent layout flickering
        if not self.alert_frame.winfo_ismapped():
            self.alert_frame.pack(side=tk.TOP, fill=tk.X, before=self.main)

        if hasattr(self, '_alert_timer') and self._alert_timer:
            self.root.after_cancel(self._alert_timer)
        self._alert_timer = self.root.after(4000, self.hide_alert)

    def hide_alert(self):
        self.alert_frame.pack_forget()
        if hasattr(self, '_alert_timer') and self._alert_timer:
            self.root.after_cancel(self._alert_timer)
            self._alert_timer = None

    def _checkout(self, event):
        if self.current_total <= 0:
            self.show_alert("Cart is empty! Scan items before checkout.")
            return

        if not self.checkout_allowed or time.monotonic()-self.received_at > 1.5:
            self.show_alert(self.checkout_reason or 'Waiting for verification')
            return
        request_id = uuid.uuid4().hex
        self.quote_request = (request_id, time.monotonic())
        self.node.request_checkout(self.revision, request_id)

    def show_quote(self, quote):
        if not self.quote_request or quote.get('request_id') != self.quote_request[0]:
            return
        if time.monotonic()-self.quote_request[1] > 2.0:
            self.quote_request = None
            self.show_alert('Checkout request expired; try again')
            return
        self.quote_request = None
        if not quote.get('allowed') or not self.checkout_allowed or quote['revision'] != self.revision or time.monotonic()-self.received_at > 1.5:
            self.show_alert(quote.get('reason') or 'Verification required'); return
        if self.popup and self.popup.winfo_exists():
            self.popup.destroy()

        popup = tk.Toplevel(self.root)
        self.popup = popup
        popup.revision = quote['revision']
        popup.title("Checkout")
        popup.geometry("360x480")
        popup.configure(bg=self.BG)
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.grab_set()

        tk.Label(popup, text="PAYMENT", font=self.f_title, bg=self.BG, fg=self.PRIMARY).pack(pady=(24, 8))
        tk.Label(popup, text=f"Total Due: ₹{self.current_total:.2f}", font=("Helvetica", 14), bg=self.BG, fg=self.SECONDARY).pack(pady=(0, 20))

        upi = 'upi://pay?' + urlencode({'pa': quote['payee'], 'pn': quote['merchant'],
                                      'am': f"{quote['amount']:.2f}", 'cu': 'INR'})
        qr = qrcode.QRCode(version=1, box_size=8, border=2)
        qr.add_data(upi)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        popup.qr_photo = ImageTk.PhotoImage(img)

        tk.Label(popup, image=popup.qr_photo, bg=self.BG).pack(pady=10)
        tk.Label(popup, text="Scan with any UPI app", font=self.f_small, bg=self.BG, fg=self.MUTED).pack(pady=4)

        close = tk.Label(popup, text="CLOSE", bg=self.SIDEBAR, fg=self.PRIMARY, font=self.f_btn, pady=10, cursor="hand2")
        close.pack(fill=tk.X, padx=50, pady=20)
        close.bind("<Button-1>", lambda e: popup.destroy())

def main(args=None):
    rclpy.init(args=args)
    root = tk.Tk()
    app = CartGUI(root)
    node = CartGUINode(app)

    # Process ROS callbacks inside the tkinter main loop
    def rclpy_spin_once():
        rclpy.spin_once(node, timeout_sec=0)
        root.after(10, rclpy_spin_once)

    root.after(10, rclpy_spin_once)

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
