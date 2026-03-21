import streamlit as st

# ==========================================
# 【クラウド最適化版】初期設定（ここを書き換えて保存）
# ==========================================
DEFAULT_UNIT_PRICE = 20000.0  # 1km単価 (2.0万)
DEFAULT_PICKUP_FEE = 10000.0  # 配車手数料 (1.0万)
FIRST_RIDE_FEE = 10000.0      # 初乗り運賃 (1.0万)
FIRST_RIDE_DIST = 2.0         # 初乗り距離 (2.0km)
SLIP_LIMIT = 2.0              # スリップ上限 (2.0km)
# ==========================================

st.set_page_config(page_title="緑間タクシー専用料金計算機 Pro", layout="centered")
st.title("🚖 緑間タクシー専用料金計算機")

# セッション状態での設定管理（アプリを開いている間だけ有効）
if 'unit_price' not in st.session_state:
    st.session_state.unit_price = DEFAULT_UNIT_PRICE
if 'pickup_fee' not in st.session_state:
    st.session_state.pickup_fee = DEFAULT_PICKUP_FEE

# 1. 設定セクション（一時的な変更用）
with st.expander("⚙️ 料金設定の一時変更"):
    st.info("※ここで変更しても、アプリを再読み込みすると初期値に戻ります。")
    st.session_state.unit_price = st.number_input("1km単価 (円)", value=st.session_state.unit_price, step=1000.0)
    st.session_state.pickup_fee = st.number_input("配車手数料 (円)", value=st.session_state.pickup_fee, step=500.0)

st.divider()

# 2. 入力セクション
col1, col2 = st.columns(2)
with col1:
    pickup_dist = st.number_input("① 迎車距離 (km)", min_value=0.0, max_value=10.0, step=0.01, format="%.2f")
with col2:
    real_dist = st.number_input("② 実車距離 (km)", min_value=0.0, step=0.01, format="%.2f")

use_pickup_fee = st.toggle(f"配車手数料 ({int(st.session_state.pickup_fee):,}円) を適用", value=True)

# 3. 計算ロジック
applied_slip = min(pickup_dist, SLIP_LIMIT)
remaining_first_ride = max(0.0, FIRST_RIDE_DIST - applied_slip)
billable_dist = max(0.0, real_dist - remaining_first_ride)

fare_meter = billable_dist * st.session_state.unit_price
applied_pickup_fee = st.session_state.pickup_fee if use_pickup_fee else 0
total_fare = FIRST_RIDE_FEE + fare_meter + applied_pickup_fee

# 4. 結果表示
st.divider()
st.markdown(f"### 💰 合計請求金額:  **{int(total_fare):,} 円**")

# 領収書コピー用
receipt = f"【タクシー領収書】合計:{int(total_fare):,}円 (内訳:初乗り{int(FIRST_RIDE_FEE):,}円"
if fare_meter > 0:
    receipt += f"＋走行分{int(fare_meter):,}円"
if use_pickup_fee:
    receipt += f"＋配車料{int(applied_pickup_fee):,}円"
receipt += ")"

st.text_input("チャット用コピー（スマホなら長押し）", value=receipt)

with st.expander("詳細な内部計算"):
    st.write(f"迎車スリップ(上限{SLIP_LIMIT}km): {applied_slip:.2f} km")
    st.write(f"初乗り無料の残り: {remaining_first_ride:.2f} km")
    st.write(f"加算対象距離: {billable_dist:.2f} km")

st.divider()
st.caption(f"設定: 単価{int(st.session_state.unit_price):,}円 / 初乗り{FIRST_RIDE_DIST}km / スリップ上限{SLIP_LIMIT}km")