import sys
import os
import traceback
import threading
import requests
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from kivy.app import App
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, Rectangle
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp, sp

# Debug log
LOG_PATH = '/data/data/com.nse.bankniftyheatmap/files/debug.log'
def dlog(msg):
    try:
        with open(LOG_PATH, 'a') as f:
            f.write(str(msg) + '\n')
    except Exception:
        pass

try:
    open(LOG_PATH, 'w').close()
except Exception:
    pass

dlog("BANKNIFTY APP STARTING - Python: " + sys.version)

# Bank Nifty 12 constituents
BANKNIFTY = [
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "KOTAKBANK.NS",
    "AXISBANK.NS",
    "SBIN.NS",
    "INDUSINDBK.NS",
    "BANDHANBNK.NS",
    "FEDERALBNK.NS",
    "IDFCFIRSTB.NS",
    "PNB.NS",
    "BANKBARODA.NS",
    "AUBANK.NS",
]

SHORT_NAMES = {
    "HDFCBANK.NS":   "HDFCBANK",
    "ICICIBANK.NS":  "ICICIBANK",
    "KOTAKBANK.NS":  "KOTAKBANK",
    "AXISBANK.NS":   "AXISBANK",
    "SBIN.NS":       "SBIN",
    "INDUSINDBK.NS": "INDUSINDB",
    "BANDHANBNK.NS": "BANDHANBNK",
    "FEDERALBNK.NS": "FEDERALBNK",
    "IDFCFIRSTB.NS": "IDFCFIRST",
    "PNB.NS":        "PNB",
    "BANKBARODA.NS": "BANKBARODA",
    "AUBANK.NS":     "AUBANK",
}

def get_short_name(ticker):
    return SHORT_NAMES.get(ticker, ticker.replace(".NS", "")[:10])

def pct_to_color(pct):
    if pct is None:
        return (0.25, 0.25, 0.25, 1)
    if pct >= 3:
        return (0.0, 0.50, 0.05, 1)
    elif pct >= 2:
        return (0.0, 0.60, 0.10, 1)
    elif pct >= 1:
        return (0.05, 0.70, 0.15, 1)
    elif pct > 0:
        return (0.10, 0.55, 0.30, 1)
    elif pct == 0:
        return (0.3, 0.3, 0.3, 1)
    elif pct > -1:
        return (0.60, 0.10, 0.10, 1)
    elif pct > -2:
        return (0.72, 0.05, 0.05, 1)
    else:
        return (0.55, 0.0, 0.0, 1)

def fetch_banknifty_data():
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json',
    }

    def fetch_one(ticker):
        try:
            yf_ticker = '^NSEBANK' if ticker == '^NSEBANK' else ticker
            url = f'https://query1.finance.yahoo.com/v8/finance/chart/{yf_ticker}?interval=1d&range=2d'
            resp = requests.get(url, headers=headers, timeout=10)
            data = resp.json()
            closes = data['chart']['result'][0]['indicators']['quote'][0]['close']
            closes = [c for c in closes if c is not None]
            if len(closes) >= 2:
                prev, curr = closes[-2], closes[-1]
                pct = ((curr - prev) / prev) * 100
                return ticker, (curr, pct)
            elif len(closes) == 1:
                return ticker, (closes[-1], None)
            else:
                return ticker, (None, None)
        except Exception as e:
            dlog(f"Error fetching {ticker}: {e}")
            return ticker, (None, None)

    all_tickers = ['^NSEBANK'] + BANKNIFTY
    results = {}
    index_data = {}

    with ThreadPoolExecutor(max_workers=13) as executor:
        futures = {executor.submit(fetch_one, t): t for t in all_tickers}
        for future in as_completed(futures):
            ticker, value = future.result()
            if ticker == '^NSEBANK':
                if value[0] is not None and value[1] is not None:
                    curr = value[0]
                    pct = value[1]
                    prev = curr / (1 + pct / 100)
                    pts = curr - prev
                    index_data = {'price': curr, 'pct': pct, 'pts': pts}
            else:
                results[ticker] = value

    dlog(f"Fetched {len(results)} stocks, index={index_data}")
    return results, index_data


class StockTile(BoxLayout):
    def __init__(self, ticker, tile_height=dp(110), **kwargs):
        super().__init__(orientation='vertical', padding=dp(4), spacing=dp(2), **kwargs)
        self.ticker = ticker
        self.size_hint_y = None
        self.height = tile_height

        with self.canvas.before:
            self.rect_color = Color(0.25, 0.25, 0.25, 1)
            self.rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._update_rect, size=self._update_rect)

        self.name_label = Label(
            text=get_short_name(ticker), font_size=sp(13),
            bold=True, color=(1, 1, 1, 1),
            size_hint_y=0.35, halign='center', valign='middle')
        self.name_label.bind(size=self.name_label.setter('text_size'))

        self.price_label = Label(
            text='', font_size=sp(12), color=(1, 1, 1, 0.95),
            size_hint_y=0.35, halign='center', valign='middle')
        self.price_label.bind(size=self.price_label.setter('text_size'))

        self.pct_label = Label(
            text='', font_size=sp(13), bold=True, color=(1, 1, 1, 1),
            size_hint_y=0.30, halign='center', valign='middle')
        self.pct_label.bind(size=self.pct_label.setter('text_size'))

        self.add_widget(self.name_label)
        self.add_widget(self.price_label)
        self.add_widget(self.pct_label)

    def _update_rect(self, *args):
        self.rect.pos = self.pos
        self.rect.size = self.size

    def update(self, price, pct):
        self.rect_color.rgba = pct_to_color(pct)
        if price is not None:
            self.price_label.text = f'Rs.{price:,.1f}'
        else:
            self.price_label.text = 'N/A'
        if pct is not None:
            sign = '+' if pct >= 0 else ''
            self.pct_label.text = f'{sign}{pct:.2f}%'
        else:
            self.pct_label.text = ''


class BankNiftyHeatmapApp(App):
    def build(self):
        Window.clearcolor = (0.05, 0.05, 0.05, 1)
        self.stock_data = {}
        self.index_data = {}
        self.tiles = {}

        root = BoxLayout(orientation='vertical', spacing=0)

        # ── Header ──────────────────────────────────────────────
        header = BoxLayout(size_hint_y=None, height=dp(44),
                           padding=[dp(8), dp(4)], spacing=dp(6))
        with header.canvas.before:
            Color(0.10, 0.10, 0.10, 1)
            self.hdr_rect = Rectangle(pos=header.pos, size=header.size)
        header.bind(pos=lambda i, v: setattr(self.hdr_rect, 'pos', v),
                    size=lambda i, v: setattr(self.hdr_rect, 'size', v))

        title = Label(text='[b]BANK NIFTY  HEATMAP[/b]', markup=True,
                      font_size=sp(14), color=(1, 0.85, 0.1, 1),
                      size_hint_x=0.40, halign='left', valign='middle')
        title.bind(size=title.setter('text_size'))

        self.status_label = Label(text='Tap Refresh', font_size=sp(10),
                                  color=(0.75, 0.75, 0.75, 1),
                                  size_hint_x=0.40, halign='right', valign='middle')
        self.status_label.bind(size=self.status_label.setter('text_size'))

        refresh_btn = Button(text='⟳ Refresh', size_hint_x=None, width=dp(82),
                             font_size=sp(11),
                             background_color=(0.15, 0.45, 0.85, 1),
                             background_normal='')
        refresh_btn.bind(on_release=self.start_refresh)

        header.add_widget(title)
        header.add_widget(self.status_label)
        header.add_widget(refresh_btn)

        # ── Index bar ────────────────────────────────────────────
        self.index_bar = BoxLayout(size_hint_y=None, height=dp(30),
                                   padding=[dp(8), dp(2)], spacing=dp(16))
        with self.index_bar.canvas.before:
            Color(0.08, 0.08, 0.08, 1)
            self.idx_rect = Rectangle(pos=self.index_bar.pos, size=self.index_bar.size)
        self.index_bar.bind(pos=lambda i, v: setattr(self.idx_rect, 'pos', v),
                            size=lambda i, v: setattr(self.idx_rect, 'size', v))

        self.nifty_label = Label(text='BANK NIFTY  --', font_size=sp(11),
                                 bold=True, color=(0.8, 0.8, 0.8, 1),
                                 halign='left', valign='middle', markup=True)
        self.nifty_label.bind(size=self.nifty_label.setter('text_size'))

        self.updated_label = Label(text='', font_size=sp(10),
                                   color=(0.55, 0.55, 0.55, 1),
                                   halign='right', valign='middle')
        self.updated_label.bind(size=self.updated_label.setter('text_size'))

        self.index_bar.add_widget(self.nifty_label)
        self.index_bar.add_widget(self.updated_label)

        # ── Heatmap grid ─────────────────────────────────────────
        # 3 columns for 12 stocks (4 rows x 3 cols)
        self.scroll = ScrollView(do_scroll_x=False)
        self.grid = GridLayout(cols=3, spacing=dp(3), padding=dp(3),
                               size_hint_y=None)
        self.grid.bind(minimum_height=self.grid.setter('height'))

        for ticker in BANKNIFTY:
            tile = StockTile(ticker, tile_height=dp(110))
            self.tiles[ticker] = tile
            self.grid.add_widget(tile)

        self.scroll.add_widget(self.grid)

        # ── Gainers / Losers bar ─────────────────────────────────
        self.bottom_bar = BoxLayout(size_hint_y=None, height=dp(90),
                                    padding=[dp(6), dp(4)], spacing=dp(4))
        with self.bottom_bar.canvas.before:
            Color(0.08, 0.08, 0.08, 1)
            self.bot_rect = Rectangle(pos=self.bottom_bar.pos, size=self.bottom_bar.size)
        self.bottom_bar.bind(pos=lambda i, v: setattr(self.bot_rect, 'pos', v),
                             size=lambda i, v: setattr(self.bot_rect, 'size', v))

        gainers_box = BoxLayout(orientation='vertical')
        self.gainers_title = Label(text='[b]TOP GAINERS[/b]', markup=True,
                                   font_size=sp(10), color=(0.3, 1.0, 0.4, 1),
                                   size_hint_y=None, height=dp(20),
                                   halign='left', valign='middle')
        self.gainers_title.bind(size=self.gainers_title.setter('text_size'))
        self.gainers_label = Label(text='', font_size=sp(10),
                                   color=(0.3, 1.0, 0.4, 1),
                                   halign='left', valign='top')
        self.gainers_label.bind(size=self.gainers_label.setter('text_size'))
        gainers_box.add_widget(self.gainers_title)
        gainers_box.add_widget(self.gainers_label)

        losers_box = BoxLayout(orientation='vertical')
        self.losers_title = Label(text='[b]TOP LOSERS[/b]', markup=True,
                                  font_size=sp(10), color=(1.0, 0.35, 0.35, 1),
                                  size_hint_y=None, height=dp(20),
                                  halign='left', valign='middle')
        self.losers_title.bind(size=self.losers_title.setter('text_size'))
        self.losers_label = Label(text='', font_size=sp(10),
                                  color=(1.0, 0.35, 0.35, 1),
                                  halign='left', valign='top')
        self.losers_label.bind(size=self.losers_label.setter('text_size'))
        losers_box.add_widget(self.losers_title)
        losers_box.add_widget(self.losers_label)

        self.bottom_bar.add_widget(gainers_box)
        self.bottom_bar.add_widget(losers_box)

        # ── Assemble ─────────────────────────────────────────────
        root.add_widget(header)
        root.add_widget(self.index_bar)
        root.add_widget(self.scroll)
        root.add_widget(self.bottom_bar)

        Clock.schedule_once(lambda dt: self.start_refresh(), 0.5)
        return root

    def start_refresh(self, *args):
        self.status_label.text = 'Loading...'
        threading.Thread(target=self.fetch_data, daemon=True).start()

    def fetch_data(self):
        dlog("fetch_data called")
        try:
            results, index_data = fetch_banknifty_data()

            def update_ui(dt):
                self.stock_data = results
                self.index_data = index_data

                # Sort tiles by pct descending
                sorted_tickers = sorted(
                    BANKNIFTY,
                    key=lambda t: results.get(t, (None, None))[1] or -999,
                    reverse=True
                )
                self.grid.clear_widgets()
                for ticker in sorted_tickers:
                    tile = self.tiles[ticker]
                    price, pct = results.get(ticker, (None, None))
                    tile.update(price, pct)
                    self.grid.add_widget(tile)

                # Update index bar
                if index_data:
                    p = index_data.get('price', 0)
                    pct = index_data.get('pct', 0)
                    pts = index_data.get('pts', 0)
                    sign = '+' if pct >= 0 else ''
                    color = '00cc44' if pct >= 0 else 'ff4444'
                    self.nifty_label.text = (
                        f'[b]BANK NIFTY[/b]  [color={color}]{p:,.2f}  '
                        f'{sign}{pct:.2f}%  ({sign}{pts:.2f} pts)[/color]'
                    )

                now = datetime.now().strftime('%d %b %Y  %H:%M:%S IST')
                self.updated_label.text = f'Updated: {now}'

                # Top gainers / losers
                valid = [(t, results[t][0], results[t][1])
                         for t in BANKNIFTY if results.get(t, (None, None))[1] is not None]
                gainers = sorted(valid, key=lambda x: x[2], reverse=True)[:3]
                losers = sorted(valid, key=lambda x: x[2])[:3]

                g_text = '\n'.join(
                    f'{get_short_name(t):<11}  +{pct:.2f}%  Rs.{price:,.2f}'
                    for t, price, pct in gainers
                )
                l_text = '\n'.join(
                    f'{get_short_name(t):<11}  {pct:.2f}%  Rs.{price:,.2f}'
                    for t, price, pct in losers
                )
                self.gainers_label.text = g_text
                self.losers_label.text = l_text

                loaded = sum(1 for p, _ in results.values() if p is not None)
                self.status_label.text = f'({loaded}/12)'

            Clock.schedule_once(update_ui, 0)

        except Exception as e:
            full_err = traceback.format_exc()
            dlog("FETCH ERROR: " + full_err)
            Clock.schedule_once(lambda dt: setattr(
                self.status_label, 'text', f'Err: {str(e)[:40]}'), 0)


if __name__ == '__main__':
    BankNiftyHeatmapApp().run()
