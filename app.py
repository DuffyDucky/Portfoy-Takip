import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime, date
import json
import os

# --- Sayfa Ayarları ---
st.set_page_config(page_title="Duffy'nin Portföyü", layout="wide", page_icon="📈")

# --- Başlık ---
st.title("📈 Duffy'nin Portföyü & İşlem Merkezi")
st.markdown("---")

# --- VERİTABANI DOSYASI ---
DATA_FILE = "portfolio.json"

# --- MİLAT ---
SYSTEM_START_DATE = date(2025, 12, 1)

# --- VARSAYILANLAR ---
DEFAULT_PORTFOLIO = {
    "TUPRS.IS": {"adet": 26,  "maliyet": 158.60, "tarih": "2025-12-01"},
    "AKSA.IS":  {"adet": 400, "maliyet": 10.01,  "tarih": "2025-12-01"},
    "TOASO.IS": {"adet": 16,  "maliyet": 234.20, "tarih": "2025-12-01"},
    "ISMEN.IS": {"adet": 94,  "maliyet": 41.31,  "tarih": "2025-12-01"},
    "ENJSA.IS": {"adet": 53,  "maliyet": 70.70,  "tarih": "2025-12-01"},
    "FROTO.IS": {"adet": 44,  "maliyet": 101.08, "tarih": "2025-12-01"},
    "BIMAS.IS": {"adet": 7,   "maliyet": 508.10, "tarih": "2025-12-01"},
    "TTRAK.IS": {"adet": 6,   "maliyet": 616.50, "tarih": "2025-12-01"},
    "ASTOR.IS": {"adet": 40,  "maliyet": 96.65,  "tarih": "2025-12-01"}
}
DEFAULT_CASH_STATE = {
    "spent_cash": 210.00,
    "deposited_cash": 0.0,
    "withdrawn_cash": 0.0,
    "sales_revenue": 0.0
}

# --- TEMETTÜ DÜZELTMELERİ ---
DIVIDEND_OVERRIDES = {
    ("FROTO.IS", date(2025, 12, 3)): 215.99 
}

# --- FONKSİYONLAR ---
def save_data():
    # ÖNCE TEMİZLİK YAP: Adeti 0 veya daha az olanları sil
    keys_to_remove = [k for k, v in st.session_state.portfolio.items() if v['adet'] <= 0]
    for k in keys_to_remove:
        del st.session_state.portfolio[k]

    portfolio_to_save = {}
    for ticker, data in st.session_state.portfolio.items():
        data_copy = data.copy()
        if isinstance(data_copy["tarih"], date):
            data_copy["tarih"] = data_copy["tarih"].strftime("%Y-%m-%d")
        portfolio_to_save[ticker] = data_copy

    state_to_save = {
        "portfolio": portfolio_to_save,
        "spent_cash": st.session_state.spent_cash,
        "deposited_cash": st.session_state.deposited_cash,
        "withdrawn_cash": st.session_state.withdrawn_cash,
        "sales_revenue": st.session_state.sales_revenue
    }
    
    with open(DATA_FILE, "w") as f:
        json.dump(state_to_save, f)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            saved_state = json.load(f)
        
        loaded_portfolio = saved_state.get("portfolio", DEFAULT_PORTFOLIO)
        for ticker, data in loaded_portfolio.items():
            if isinstance(data["tarih"], str):
                loaded_portfolio[ticker]["tarih"] = datetime.strptime(data["tarih"], "%Y-%m-%d").date()
        
        st.session_state.portfolio = loaded_portfolio
        st.session_state.spent_cash = saved_state.get("spent_cash", 210.0)
        st.session_state.deposited_cash = saved_state.get("deposited_cash", 0.0)
        st.session_state.withdrawn_cash = saved_state.get("withdrawn_cash", 0.0)
        st.session_state.sales_revenue = saved_state.get("sales_revenue", 0.0)
    else:
        clean_default = DEFAULT_PORTFOLIO.copy()
        for t, d in clean_default.items():
            if isinstance(d["tarih"], str):
                clean_default[t]["tarih"] = datetime.strptime(d["tarih"], "%Y-%m-%d").date()
        
        st.session_state.portfolio = clean_default
        st.session_state.spent_cash = DEFAULT_CASH_STATE["spent_cash"]
        st.session_state.deposited_cash = DEFAULT_CASH_STATE["deposited_cash"]
        st.session_state.withdrawn_cash = DEFAULT_CASH_STATE["withdrawn_cash"]
        st.session_state.sales_revenue = DEFAULT_CASH_STATE["sales_revenue"]
    
    # Yüklerken de temizlik yapalım (Eski kalıntıları silmek için)
    save_data()

# --- YÜKLE ---
if 'portfolio' not in st.session_state:
    load_data()

if 'last_prices' not in st.session_state:
    st.session_state.last_prices = {} 

# --- DATA ÇEKME ---
@st.cache_data(ttl=60) 
def get_portfolio_data(portfolio_dict):
    wallet_data = []      
    future_dividends = []   
    past_dividends = []     
    
    today = datetime.now().date()
    total_portfolio_value = 0
    total_profit_loss = 0
    total_cost_basis = 0 
    total_dividend_income = 0.0 
    
    current_prices = {}

    for ticker, data in portfolio_dict.items():
        qty = data["adet"]
        
        # Ekstra Güvenlik: Adeti 0 olanları listede gösterme
        if qty <= 0:
            continue

        cost = data["maliyet"]
        entry_date = data.get("tarih", SYSTEM_START_DATE)
        
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            current_price = info.get('currentPrice', info.get('previousClose', 0))
            current_prices[ticker] = current_price
            
            total_cost_basis += (cost * qty)
            last_div_amount_gross = info.get('dividendRate', 0)
            ex_div_timestamp = info.get('exDividendDate', None)
            
            div_date_obj = None
            total_net_income = 0
            
            if ex_div_timestamp:
                div_date_obj = datetime.fromtimestamp(ex_div_timestamp).date()
                override_key = (ticker, div_date_obj)
                if override_key in DIVIDEND_OVERRIDES:
                    total_net_income = DIVIDEND_OVERRIDES[override_key]
                else:
                    last_div_amount_net = last_div_amount_gross * 0.90
                    total_net_income = last_div_amount_net * qty
                
                if div_date_obj > today:
                    future_dividends.append({
                        "Hisse": ticker.replace(".IS", ""),
                        "Mevcut Adet": qty,
                        "Tahmini Net": f"₺{total_net_income:.2f}",
                        "Ödeme Tarihi": div_date_obj
                    })
                else:
                    if div_date_obj >= entry_date:
                        total_dividend_income += total_net_income
                        status = "✅ Kasaya Girdi"
                    else:
                        status = "❌ (Alımdan Önceydi)"

                    past_dividends.append({
                        "Hisse": ticker.replace(".IS", ""),
                        "Net Tutar": f"₺{total_net_income:.2f}",
                        "Durum": status,
                        "Tarih": div_date_obj
                    })

            market_value = current_price * qty 
            profit_loss = (current_price - cost) * qty 
            profit_loss_percent = ((current_price - cost) / cost) * 100 if cost != 0 else 0
            
            total_portfolio_value += market_value
            total_profit_loss += profit_loss

            wallet_data.append({
                "Hisse": ticker.replace(".IS", ""),
                "Adet": qty,
                "Maliyet": f"₺{cost:.2f}",
                "Fiyat": f"₺{current_price:.2f}",
                "Toplam Değer": market_value, 
                "Kâr/Zarar (TL)": profit_loss,
                "Kâr (%)": profit_loss_percent,
            })
            
        except Exception as e:
            continue
    
    total_pl_ratio = (total_profit_loss / total_cost_basis * 100) if total_cost_basis > 0 else 0
    return pd.DataFrame(wallet_data), pd.DataFrame(future_dividends), pd.DataFrame(past_dividends), total_portfolio_value, total_profit_loss, total_dividend_income, total_pl_ratio, current_prices

# --- ÇALIŞTIR ---
if st.button("Verileri Güncelle 🔄"):
    st.cache_data.clear()

df_wallet, df_future, df_past, total_val, total_pl, div_income, pl_ratio, prices = get_portfolio_data(st.session_state.portfolio)
st.session_state.last_prices = prices

# --- NAKİT HESABI ---
total_cash_in = div_income + st.session_state.deposited_cash + st.session_state.sales_revenue
total_cash_out = st.session_state.spent_cash + st.session_state.withdrawn_cash
net_cash_balance = total_cash_in - total_cash_out

# ==========================================
# 🧱 YAN MENÜ: İŞLEMLER
# ==========================================
st.sidebar.header("İşlemler")
st.sidebar.info(f"Harcanabilir Nakit: ₺{net_cash_balance:,.2f}")

# --- 1. KASA İŞLEMLERİ ---
with st.sidebar.expander("➕ Para Yatır", expanded=False):
    deposit_amount = st.number_input("Tutar (TL)", min_value=0.0, step=100.0, key="dep_input")
    if st.button("Yatır 💰"):
        st.session_state.deposited_cash += deposit_amount
        save_data()
        st.success(f"₺{deposit_amount} eklendi!")
        st.rerun()

with st.sidebar.expander("➖ Para Çek", expanded=False):
    withdraw_amount = st.number_input("Tutar (TL)", min_value=0.0, step=100.0, key="with_input")
    if st.button("Çek 💸"):
        if withdraw_amount > net_cash_balance:
            st.error("❌ Yetersiz Bakiye!")
        else:
            st.session_state.withdrawn_cash += withdraw_amount
            save_data()
            st.success(f"₺{withdraw_amount} çekildi.")
            st.rerun()

# --- 2. YENİ HİSSE AL ---
with st.sidebar.expander("🆕 Yeni Hisse Al (Portföy Dışı)", expanded=False):
    new_ticker_input = st.text_input("Hisse Kodu (Örn: THYAO.IS)", value="").upper().strip()
    new_buy_qty = st.number_input("Adet", min_value=1, step=1, key="new_buy_qty")
    
    # Fiyatı göstermek için geçici değişken
    preview_price = 0.0
    preview_total = 0.0

    if new_ticker_input:
        try:
            temp_ticker = yf.Ticker(new_ticker_input)
            temp_info = temp_ticker.info
            preview_price = temp_info.get('currentPrice', temp_info.get('previousClose', 0))
            preview_total = preview_price * new_buy_qty
            
            if preview_price > 0:
                st.write(f"Birim Fiyat: ₺{preview_price:.2f}")
                st.write(f"Toplam Tutar: **₺{preview_total:.2f}**")
            else:
                st.error("Fiyat alınamadı.")
        except:
            st.error("Hisse kodu bulunamadı.")
    
    if st.button("Satın Al ve Ekle ✅", key="btn_new_add"):
        if not new_ticker_input:
            st.error("Lütfen bir hisse kodu girin.")
        elif preview_price == 0:
            st.error("Güncel fiyat alınamadığı için işlem yapılamadı.")
        elif preview_total > net_cash_balance:
            st.error(f"❌ Yetersiz Bakiye! (Eksik: ₺{preview_total - net_cash_balance:.2f})")
        else:
            purchase_date = datetime.now().date()
            
            if new_ticker_input in st.session_state.portfolio:
                old_qty = st.session_state.portfolio[new_ticker_input]["adet"]
                old_cost = st.session_state.portfolio[new_ticker_input]["maliyet"]
                final_qty = old_qty + new_buy_qty
                final_cost = ((old_qty * old_cost) + preview_total) / final_qty
                st.session_state.portfolio[new_ticker_input]["adet"] = final_qty
                st.session_state.portfolio[new_ticker_input]["maliyet"] = final_cost
                msg = f"{new_ticker_input} üzerine eklendi."
            else:
                st.session_state.portfolio[new_ticker_input] = {
                    "adet": new_buy_qty,
                    "maliyet": preview_price,
                    "tarih": purchase_date 
                }
                msg = f"{new_ticker_input} portföye eklendi."
            
            st.session_state.spent_cash += preview_total
            save_data()
            st.success(msg)
            st.rerun()

st.sidebar.markdown("---")

# --- 3. MEVCUT HİSSE İŞLEMLERİ ---
st.sidebar.markdown("### Mevcut Hisseler")
buy_tab, sell_tab = st.sidebar.tabs(["📈 Ekleme Yap", "📉 Satış Yap"])

with buy_tab:
    if len(st.session_state.portfolio) > 0:
        selected_stock_buy = st.selectbox("Hisse Seç", list(st.session_state.portfolio.keys()), key="buy_select")
        buy_qty = st.number_input("Adet", min_value=1, step=1, key="buy_qty")
        current_buy_price = st.session_state.last_prices.get(selected_stock_buy, 0)
        estimated_cost = current_buy_price * buy_qty
        st.write(f"Tutar: **₺{estimated_cost:.2f}**")
        
        if st.button("Ekleme Yap ✅", key="btn_buy"):
            if estimated_cost > net_cash_balance:
                st.error("Yetersiz Bakiye")
            else:
                st.session_state.spent_cash += estimated_cost
                old_qty = st.session_state.portfolio[selected_stock_buy]["adet"]
                old_cost = st.session_state.portfolio[selected_stock_buy]["maliyet"]
                new_qty = old_qty + buy_qty
                new_cost = ((old_qty * old_cost) + estimated_cost) / new_qty
                st.session_state.portfolio[selected_stock_buy]["adet"] = new_qty
                st.session_state.portfolio[selected_stock_buy]["maliyet"] = new_cost
                save_data()
                st.success(f"Alındı.")
                st.rerun()

with sell_tab:
    if len(st.session_state.portfolio) > 0:
        selected_stock_sell = st.selectbox("Hisse Seç", list(st.session_state.portfolio.keys()), key="sell_select")
        current_qty_held = st.session_state.portfolio[selected_stock_sell]["adet"]
        st.caption(f"Eldeki: {current_qty_held}")
        sell_qty = st.number_input("Adet", min_value=1, max_value=max(1, current_qty_held), step=1, key="sell_qty")
        current_sell_price = st.session_state.last_prices.get(selected_stock_sell, 0)
        total_sale_income = current_sell_price * sell_qty
        st.write(f"Gelir: **₺{total_sale_income:.2f}**")
        
        if st.button("Satış Yap 💰", key="btn_sell"):
            st.session_state.sales_revenue += total_sale_income
            st.session_state.portfolio[selected_stock_sell]["adet"] -= sell_qty
            save_data() # <--- BURADA OTOMATİK SİLME DEVREYE GİRER
            st.success(f"Satıldı.")
            st.rerun()

# ==========================================
# ANA EKRAN
# ==========================================
col1, col2, col3 = st.columns(3)
col1.metric("Toplam Portföy Değeri", f"₺{total_val:,.2f}")
col2.metric("Toplam Kâr/Zarar", f"₺{total_pl:,.2f}", f"%{pl_ratio:.2f}")
col3.metric("Harcanabilir Nakit", f"₺{net_cash_balance:,.2f}")

st.subheader("📊 Portföy Durumu")
st.dataframe(
    df_wallet,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Toplam Değer": st.column_config.NumberColumn(format="₺%.2f"),
        "Kâr/Zarar (TL)": st.column_config.NumberColumn(format="₺%.2f"),
        "Kâr (%)": st.column_config.ProgressColumn("Kâr Durumu", format="%.2f%%", min_value=-20, max_value=100),
    }
)

st.markdown("---")
st.subheader("♻️ Temettü Akışı")
tab1, tab2 = st.tabs(["🚀 Gelecek Ödemeler", "✅ Geçmiş Ödemeler"])
with tab1:
    if not df_future.empty:
        df_future = df_future.sort_values(by="Ödeme Tarihi")
        st.dataframe(df_future, use_container_width=True, hide_index=True, column_config={"Ödeme Tarihi": st.column_config.DateColumn("Tarih", format="DD-MM-YYYY")})
with tab2:
    if not df_past.empty:
        df_past = df_past.sort_values(by="Tarih", ascending=False)
        st.dataframe(df_past, use_container_width=True, hide_index=True, column_config={"Tarih": st.column_config.DateColumn("Tarih", format="DD-MM-YYYY")})
    else:
        st.info("Kayıtlı temettü girişi yok.")