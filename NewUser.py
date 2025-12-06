import streamlit as st
import yfinance as yf
import pandas as pd
import datetime
import json
import os
import pytz
from streamlit_autorefresh import st_autorefresh



# --- Sayfa Ayarları ---
st.set_page_config(page_title="Portföy Asistanı", layout="wide", page_icon="💼")

# ==========================================
# 🔄 CANLI YENİLEME VE CSS STİLLERİ
# ==========================================

# Sayfayı her 1 saniyede (1000ms) bir yenile (Canlı Saat için)
st_autorefresh(interval=1000, key="bist_clock")

# CSS: Radio butonlarını Toggle gibi gösterme
st.markdown("""
<style>
    div.row-widget.stRadio > div {
        flex-direction: row;
        background-color: #f0f2f6;
        padding: 4px;
        border-radius: 8px;
        width: fit-content;
        gap: 0px;
    }
    div.row-widget.stRadio > div > label {
        background-color: transparent;
        padding: 6px 16px;
        border-radius: 6px;
        cursor: pointer;
        margin: 0px;
        transition: all 0.2s;
        border: none;
    }
    div.row-widget.stRadio > div > label[data-baseweb="radio"] {
        background-color: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        font-weight: bold;
        color: #FF4B4B;
    }
    div.row-widget.stRadio div[role="radio"] {
        display: none;
    }
</style>
""", unsafe_allow_html=True)

# --- SABİTLER ---
DATA_FILE = "portfolio.json"
SYSTEM_START_DATE = datetime.date(2025, 12, 1)

# --- TEMETTÜ DÜZELTMELERİ (Opsiyonel Manuel Girişler) ---
DIVIDEND_OVERRIDES = {
    ("FROTO.IS", datetime.date(2025, 12, 3)): 215.99
}

# --- YARDIMCI FONKSİYONLAR ---

@st.cache_data(ttl=300)
def get_usd_rate():
    """Anlık Dolar/TL kurunu çeker."""
    try:
        ticker = yf.Ticker("TRY=X")
        rate = ticker.info.get('currentPrice', ticker.info.get('previousClose', 0))
        return rate if rate > 0 else 1.0
    except Exception:
        return 36.0 # Yedek kur

def get_market_status():
    """BIST Piyasa Durumunu ve Saati Döndürür"""
    tz = pytz.timezone('Europe/Istanbul')
    now = datetime.datetime.now(tz)
    current_time_str = now.strftime("%H:%M:%S")
    
    is_weekday = now.weekday() < 5
    is_open_hours = datetime.time(10, 0) <= now.time() <= datetime.time(18, 5)
    
    if is_weekday and is_open_hours:
        return "AÇIK", current_time_str, "#28a745" # Yeşil
    else:
        return "KAPALI", current_time_str, "#dc3545" # Kırmızı

def format_currency(value, currency_mode, usd_rate):
    if currency_mode == "USD":
        val_usd = value / usd_rate
        return f"${val_usd:,.2f}"
    else:
        return f"₺{value:,.2f}"

def save_data():
    """Verileri JSON dosyasına kaydeder."""
    # Adeti 0 olanları temizle
    if st.session_state.get("portfolio"):
        keys_to_remove = [k for k, v in st.session_state.portfolio.items() if v['adet'] <= 0]
        for k in keys_to_remove:
            del st.session_state.portfolio[k]

    portfolio_to_save = {}
    if st.session_state.get("portfolio"):
        for ticker, data in st.session_state.portfolio.items():
            data_copy = data.copy()
            if isinstance(data_copy["tarih"], datetime.date):
                data_copy["tarih"] = data_copy["tarih"].strftime("%Y-%m-%d")
            portfolio_to_save[ticker] = data_copy

    state_to_save = {
        "owner_name": st.session_state.get("owner_name"),
        "portfolio": portfolio_to_save,
        "spent_cash": st.session_state.get("spent_cash", 0.0),
        "deposited_cash": st.session_state.get("deposited_cash", 0.0),
        "withdrawn_cash": st.session_state.get("withdrawn_cash", 0.0),
        "sales_revenue": st.session_state.get("sales_revenue", 0.0)
    }
    
    with open(DATA_FILE, "w") as f:
        json.dump(state_to_save, f)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            saved_state = json.load(f)
        
        st.session_state.owner_name = saved_state.get("owner_name")
        loaded_portfolio = saved_state.get("portfolio", {})
        for ticker, data in loaded_portfolio.items():
            if isinstance(data["tarih"], str):
                loaded_portfolio[ticker]["tarih"] = datetime.datetime.strptime(data["tarih"], "%Y-%m-%d").date()
        
        st.session_state.portfolio = loaded_portfolio
        st.session_state.spent_cash = saved_state.get("spent_cash", 0.0)
        st.session_state.deposited_cash = saved_state.get("deposited_cash", 0.0)
        st.session_state.withdrawn_cash = saved_state.get("withdrawn_cash", 0.0)
        st.session_state.sales_revenue = saved_state.get("sales_revenue", 0.0)
    else:
        st.session_state.owner_name = None
        st.session_state.portfolio = {}
        st.session_state.spent_cash = 0.0
        st.session_state.deposited_cash = 0.0
        st.session_state.withdrawn_cash = 0.0
        st.session_state.sales_revenue = 0.0

def reset_app():
    if os.path.exists(DATA_FILE):
        os.remove(DATA_FILE)
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- BAŞLANGIÇ YÜKLEMESİ ---
if 'owner_name' not in st.session_state:
    load_data()
if 'last_prices' not in st.session_state:
    st.session_state.last_prices = {} 

# ==========================================
# 🛑 1. GİRİŞ EKRANI
# ==========================================
if st.session_state.owner_name is None:
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("👋 Hoşgeldiniz!")
        with st.form("login_form"):
            name_input = st.text_input("Portföy Adı", placeholder="Örn: Duffy'nin Cüzdanı")
            start_cash = st.number_input("Başlangıç Nakit (TL)", min_value=0.0, step=100.0)
            if st.form_submit_button("Başla 🚀"):
                if name_input.strip() == "":
                    st.error("İsim gerekli.")
                else:
                    st.session_state.owner_name = name_input
                    st.session_state.deposited_cash = start_cash
                    st.session_state.portfolio = {}
                    save_data()
                    st.rerun()
    st.stop()

# ==========================================
# 🚀 2. ANA UYGULAMA
# ==========================================

usd_rate = get_usd_rate()
market_status_text, market_time, market_color = get_market_status()

# --- SOL MENÜ (ÜST KISIM) ---
# BIST 100 HTML Kutusu
st.sidebar.markdown(f"""
    <div style="
        border: 1px solid {market_color};
        border-radius: 10px;
        padding: 8px;
        text-align: center;
        background-color: rgba(240, 242, 246, 0.5);
        margin-bottom: 20px;
        font-family: sans-serif;
    ">
        <span style="font-weight:bold; color:{market_color};">BIST 100:</span> 
        <span style="color:{market_color}; font-weight:bold;">⬤ {market_status_text}</span> 
        <br>
        <span style="color:#555; font-size: 0.9em;">{market_time}</span>
    </div>
    """, unsafe_allow_html=True)

# Ayarlar ve Döviz Seçimi
c_set, c_tog = st.sidebar.columns([1, 1.5])
with c_set:
    with st.popover("⚙️ Ayar", use_container_width=True):
        st.caption("Uygulama Ayarları")
        if st.button("Sıfırla 🗑️", use_container_width=True):
            reset_app()

with c_tog:
    currency_mode = st.radio(
        "Para Birimi",
        options=["TL", "USD"],
        format_func=lambda x: "₺ TL" if x == "TL" else "$ USD",
        horizontal=True,
        label_visibility="collapsed"
    )

# --- İSTEK 1: SABİT KUR YAZISI ---
# Burada if/else yok, her zaman kuru gösterir.
st.sidebar.caption(f"&nbsp;&nbsp;&nbsp;Kur: 1$ = {usd_rate:.2f}₺")

st.sidebar.markdown("---")

# --- CALLBACKS (BUTON FONKSİYONLARI) ---
def deposit_cb():
    if st.session_state.dep_input > 0:
        st.session_state.deposited_cash += st.session_state.dep_input
        save_data()
        st.toast("Yatırıldı")

def withdraw_cb():
    if st.session_state.with_input > 0:
        st.session_state.withdrawn_cash += st.session_state.with_input
        save_data()
        st.toast("Çekildi")

def buy_new_cb():
    tkr = st.session_state.new_ticker_input.strip().upper()
    qty = st.session_state.new_buy_qty
    if tkr:
        try:
            inf = yf.Ticker(tkr).info
            prc = inf.get('currentPrice', inf.get('previousClose', 0))
            if prc > 0:
                cost = prc * qty
                purchase_date = datetime.datetime.now().date()
                
                if tkr in st.session_state.portfolio:
                    old_qty = st.session_state.portfolio[tkr]["adet"]
                    old_cost = st.session_state.portfolio[tkr]["maliyet"]
                    nq = old_qty + qty
                    nc = ((old_qty * old_cost) + cost) / nq
                    st.session_state.portfolio[tkr]["adet"] = nq
                    st.session_state.portfolio[tkr]["maliyet"] = nc
                else:
                    st.session_state.portfolio[tkr] = {
                        "adet": qty, 
                        "maliyet": prc, 
                        "tarih": purchase_date
                    }
                st.session_state.spent_cash += cost
                save_data()
                st.toast(f"{tkr} alındı")
        except Exception:
            st.error("Hata")

# --- VERİ HESAPLAMA (TEMETTÜ MANTIĞI BURADA) ---
@st.cache_data(ttl=60) 
def get_portfolio_data(portfolio_dict):
    wallet_data = []      
    future_dividends = []   
    past_dividends = []     
    
    today = datetime.datetime.now().date()
    total_val = 0
    total_pl = 0
    total_cost_basis = 0 
    total_div_income = 0.0 
    
    current_prices = {}

    for ticker, data in portfolio_dict.items():
        qty = data["adet"]
        if qty <= 0: continue
        
        cost = data["maliyet"]
        entry_date = data.get("tarih", SYSTEM_START_DATE)
        
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            price = info.get('currentPrice', info.get('previousClose', 0))
            current_prices[ticker] = price
            
            market_val = price * qty
            pl = (price - cost) * qty
            total_val += market_val
            total_pl += pl
            total_cost_basis += (cost * qty)

            # --- İSTEK 2: TEMETTÜ MANTIĞI ---
            div_rate = info.get('dividendRate', 0)
            ex_date_ts = info.get('exDividendDate', None)
            
            if ex_date_ts:
                ex_date = datetime.datetime.fromtimestamp(ex_date_ts).date()
                net_div = DIVIDEND_OVERRIDES.get((ticker, ex_date), div_rate * 0.90 * qty)
                
                if ex_date > today:
                    # Gelecek temettü (Henüz tarihi gelmemiş)
                    future_dividends.append({
                        "Hisse": ticker.replace(".IS", ""), 
                        "Tahmini Tutar": net_div, 
                        "Ödeme Tarihi": ex_date
                    })
                else:
                    # Geçmiş temettü (Tarihi geçmiş)
                    # SADECE hisse o tarihte elimizdeyse göster!
                    if ex_date >= entry_date:
                        total_div_income += net_div
                        past_dividends.append({
                            "Hisse": ticker.replace(".IS", ""), 
                            "Kazanılan Tutar": net_div, 
                            "Tarih": ex_date
                        })
                    # Eğer ex_date < entry_date ise (biz almadan önce dağıtılmışsa)
                    # HİÇBİR ŞEY YAPMA, LİSTEYE EKLEME.

            wallet_data.append({
                "Hisse": ticker.replace(".IS", ""),
                "Adet": qty,
                "Maliyet": cost,
                "Fiyat": price,
                "Toplam Değer": market_val, 
                "Kâr/Zarar (TL)": pl,
                "Kâr (%)": ((price - cost) / cost) * 100 if cost else 0
            })
        except: continue
            
    pl_ratio = (total_pl / total_cost_basis * 100) if total_cost_basis else 0
    return pd.DataFrame(wallet_data), pd.DataFrame(future_dividends), pd.DataFrame(past_dividends), total_val, total_pl, total_div_income, pl_ratio, current_prices

# Hesaplamaları çalıştır
df_wallet, df_future, df_past, total_val, total_pl, div_income, pl_ratio, prices = get_portfolio_data(st.session_state.portfolio)
st.session_state.last_prices = prices

# Nakit Dengesi
total_cash_in = div_income + st.session_state.deposited_cash + st.session_state.sales_revenue
total_cash_out = st.session_state.spent_cash + st.session_state.withdrawn_cash
net_cash_balance = total_cash_in - total_cash_out

# Sol Menü Bilgileri
st.sidebar.info(f"Nakit: {format_currency(net_cash_balance, currency_mode, usd_rate)}")

with st.sidebar.expander("➕ Para Yatır"):
    st.number_input("Tutar", min_value=0.0, step=100.0, key="dep_input")
    st.button("Yatır 💰", on_click=deposit_cb)

with st.sidebar.expander("➖ Para Çek"):
    st.number_input("Tutar", min_value=0.0, step=100.0, key="with_input")
    st.button("Çek 💸", on_click=withdraw_cb)

with st.sidebar.expander("🆕 Yeni Hisse Ekle", expanded=True):
    st.text_input("Hisse Kodu (Örn: THYAO.IS)", key="new_ticker_input")
    st.number_input("Adet", min_value=1, step=1, key="new_buy_qty")
    if st.session_state.new_ticker_input:
        tkr = st.session_state.new_ticker_input.strip().upper()
        try:
            info = yf.Ticker(tkr).info
            prc = info.get('currentPrice', info.get('previousClose', 0))
            if prc > 0:
                tot = prc * st.session_state.new_buy_qty
                disp_prc = format_currency(prc, currency_mode, usd_rate)
                disp_tot = format_currency(tot, currency_mode, usd_rate)
                st.caption(f"Fiyat: {disp_prc} | Tutar: {disp_tot}")
                if tot > net_cash_balance: st.error("Bakiye Yetersiz!")
        except: pass
    st.button("Satın Al ✅", on_click=buy_new_cb)

st.sidebar.markdown("---")

# Mevcut Hisse Ekle/Sat Tabları
buy_tab, sell_tab = st.sidebar.tabs(["📈 Ekle", "📉 Sat"])
with buy_tab:
    if len(st.session_state.portfolio) > 0:
        sel_buy = st.selectbox("Hisse", list(st.session_state.portfolio.keys()), key="bs")
        qty_buy = st.number_input("Adet", 1, key="bq")
        prc_buy = st.session_state.last_prices.get(sel_buy, 0)
        cost_buy = prc_buy * qty_buy
        st.caption(f"Tutar: {format_currency(cost_buy, currency_mode, usd_rate)}")
        if st.button("Ekle ✅"):
            if cost_buy > net_cash_balance: st.error("Yetersiz")
            else:
                st.session_state.spent_cash += cost_buy
                d = st.session_state.portfolio[sel_buy]
                nq = d["adet"] + qty_buy
                nc = ((d["adet"] * d["maliyet"]) + cost_buy) / nq
                st.session_state.portfolio[sel_buy]["adet"] = nq
                st.session_state.portfolio[sel_buy]["maliyet"] = nc
                save_data()
                st.rerun()
with sell_tab:
    if len(st.session_state.portfolio) > 0:
        sel_sell = st.selectbox("Hisse", list(st.session_state.portfolio.keys()), key="ss")
        have = st.session_state.portfolio[sel_sell]["adet"]
        st.caption(f"Elde: {have}")
        qty_sell = st.number_input("Adet", 1, max_value=max(1, have), key="sq")
        prc_sell = st.session_state.last_prices.get(sel_sell, 0)
        rev = prc_sell * qty_sell
        st.caption(f"Gelir: {format_currency(rev, currency_mode, usd_rate)}")
        if st.button("Sat 💰"):
            st.session_state.sales_revenue += rev
            st.session_state.portfolio[sel_sell]["adet"] -= qty_sell
            save_data()
            st.rerun()

# ==========================================
# ANA EKRAN İÇERİĞİ
# ==========================================
st.title(f"💼 {st.session_state.owner_name}")
if st.button("Verileri Güncelle 🔄"):
    st.cache_data.clear()
    st.rerun()

disp_total_val = format_currency(total_val, currency_mode, usd_rate)
disp_total_pl = format_currency(total_pl, currency_mode, usd_rate)
disp_cash = format_currency(net_cash_balance, currency_mode, usd_rate)

col1, col2, col3 = st.columns(3)
col1.metric("Toplam Portföy", disp_total_val)
col2.metric("Toplam Kâr/Zarar", disp_total_pl, f"%{pl_ratio:.2f}")
col3.metric("Kasa", disp_cash)

if not df_wallet.empty:
    st.subheader("📊 Portföy Durumu")
    
    df_display = df_wallet.copy()
    if currency_mode == "USD":
        for col in ["Maliyet", "Fiyat", "Toplam Değer", "Kâr/Zarar (TL)"]:
            df_display[col] = df_display[col].apply(
                lambda x: float(str(x).replace('₺','').replace(',','').strip()) / usd_rate
            )
        currency_symbol = "$"
        pl_col_name = "Kâr/Zarar ($)"
    else:
        currency_symbol = "₺"
        pl_col_name = "Kâr/Zarar (TL)"

    st.dataframe(
        df_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Maliyet": st.column_config.NumberColumn(format=f"{currency_symbol}%.2f"),
            "Fiyat": st.column_config.NumberColumn(format=f"{currency_symbol}%.2f"),
            "Toplam Değer": st.column_config.NumberColumn(format=f"{currency_symbol}%.2f"),
            "Kâr/Zarar (TL)": st.column_config.NumberColumn(pl_col_name, format=f"{currency_symbol}%.2f"),
            "Kâr (%)": st.column_config.ProgressColumn("Kâr", format="%.2f%%", min_value=-20, max_value=100)
        }
    )
else:
    st.info("Portföy boş. Soldan yeni hisse ekleyebilirsin 👈")
    with st.container(border=True):
        st.markdown("### ➕ İlk Hisseni Ekle")
        c1, c2 = st.columns([1,1])
        ft_ticker = c1.text_input("Hisse Kodu (Örn: GARAN.IS)", key="main_t").upper().strip()
        ft_qty = c2.number_input("Adet", 1, key="main_q")
        if c1.button("Satın Al ve Başla 🚀", key="main_b"):
            try:
                inf = yf.Ticker(ft_ticker).info
                pr = inf.get('currentPrice', inf.get('previousClose', 0))
                ct = pr * ft_qty
                if ct > net_cash_balance: st.error(f"Yetersiz Bakiye! Gereken: ₺{ct:.2f}")
                else:
                    st.session_state.portfolio[ft_ticker] = {"adet": ft_qty, "maliyet": pr, "tarih": datetime.datetime.now().date()}
                    st.session_state.spent_cash += ct
                    save_data()
                    st.success("Başladık!")
                    st.rerun()
            except: st.error("Hata")

st.markdown("---")
# --- İSTEK 3: TEMETTÜ TABLOLARININ AYRILMASI ---
st.subheader("♻️ Temettü Akışı")
t1, t2 = st.tabs(["Gelecek (Tahmini)", "Geçmiş (Kazanılan)"])

# Gelecek Sekmesi
with t1:
    if not df_future.empty:
        df_fut_show = df_future.copy()
        if currency_mode == "USD":
             df_fut_show["Tahmini Tutar"] = df_fut_show["Tahmini Tutar"].apply(lambda x: x / usd_rate)
        st.dataframe(
            df_fut_show, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Ödeme Tarihi": st.column_config.DateColumn("Tarih", format="DD.MM.YYYY"),
                "Tahmini Tutar": st.column_config.NumberColumn(format=f"{currency_symbol}%.2f")
            }
        )
    else:
        st.info("Yakın tarihte kesinleşmiş bir temettü ödemesi görünmüyor.")

# Geçmiş Sekmesi
with t2:
    if not df_past.empty:
        df_past_show = df_past.copy()
        if currency_mode == "USD":
             df_past_show["Kazanılan Tutar"] = df_past_show["Kazanılan Tutar"].apply(lambda x: x / usd_rate)
        st.dataframe(
            df_past_show, 
            use_container_width=True, 
            hide_index=True,
            column_config={
                "Tarih": st.column_config.DateColumn("Tarih", format="DD.MM.YYYY"),
                "Kazanılan Tutar": st.column_config.NumberColumn(format=f"{currency_symbol}%.2f")
            }
        )
    else:
        st.info("Henüz hesabına geçmiş bir temettü bulunmuyor.")