import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime
import pytz
import io

# --- 設定 ---
GITHUB_REPO = "Lichtmido/Midorima_Taxi_Calculator" 
CSV_FILE = "taxi_log.csv"
TOKEN = st.secrets["GH_TOKEN"]

# デフォルト定数
D_UNIT_PRICE = 20000.0  # 1km単価
D_PICKUP_FEE = 10000.0  # 配車手数料
D_FIRST_FEE = 10000.0   # 初乗り運賃

st.set_page_config(page_title="緑間タクシー 料金計算機", layout="centered")

# --- GitHub連携関数 ---
def get_csv_from_github():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CSV_FILE}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        content = base64.b64decode(res.json()["content"]).decode("utf-8")
        df = pd.read_csv(io.StringIO(content))
        return df, res.json()["sha"]
    return pd.DataFrame(columns=["timestamp", "driver", "pickup_dist", "real_dist", "fare", "details"]), None

def save_to_github(df, sha, message):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CSV_FILE}"
    headers = {"Authorization": f"token {TOKEN}"}
    content = base64.b64encode(df.to_csv(index=False).encode("utf-8")).decode("utf-8")
    data = {"message": message, "content": content, "sha": sha}
    requests.put(url, headers=headers, json=data)

# --- 料金設定のセッション管理 ---
if 'u_price' not in st.session_state: st.session_state.u_price = D_UNIT_PRICE
if 'p_fee' not in st.session_state: st.session_state.p_fee = D_PICKUP_FEE
if 'f_fee' not in st.session_state: st.session_state.f_fee = D_FIRST_FEE

st.title("🚖 緑間タクシー 料金計算機")
driver = st.radio("担当ドライバー", ["緑間理人", "緑間きのこ","白黒つけ男","猫之街五十鈴"], horizontal=True)

with st.expander("⚙️ 料金単価・手数料の一時設定"):
    st.session_state.u_price = st.number_input("1km単価 (円)", value=st.session_state.u_price, step=1000.0)
    st.session_state.p_fee = st.number_input("配車手数料 (円)", value=st.session_state.p_fee, step=500.0)
    st.session_state.f_fee = st.number_input("初乗り運賃 (円)", value=st.session_state.f_fee, step=500.0)

st.divider()

# --- 新機能：モード選択 ---
pay_mode = st.toggle("💰 金額を手動で直接入力する", value=False)

detail_parts = []
total_fare = 0.0

if pay_mode:
    # 【手動入力モード】
    manual_fare = st.number_input("決済金額 (円)", min_value=0, step=10000, value=0)
    pickup_dist, real_dist = 0.0, 0.0
    total_fare = float(manual_fare)
    calc_type = "手動定額決済"
    detail_parts.append("定額料金")
else:
    # 【通常計算モード（ベースコードのロジック）】
    col1, col2 = st.columns(2)
    with col1:
        pickup_dist = st.number_input("① 迎車距離 (km)", min_value=0.0, step=0.01, format="%.2f")
    with col2:
        real_dist = st.number_input("② 実車距離 (km)", min_value=0.0, step=0.01, format="%.2f")

    st.write("🔧 オプション設定（ボタンOFFでその項目を0円にします）")
    c1, c2 = st.columns(2)
    with c1:
        use_pickup = st.toggle("配車手数料を適用", value=True)
    with c2:
        use_first = st.toggle("初乗り運賃を適用", value=True)

    # --- チップ入力（通常モード時のみ表示） ---
    tip_amount = st.number_input("🧧 お気持ち / チップ (円)", min_value=0.0, step=1000.0, format="%.0f")

    # ロジック適用
    applied_p_fee = st.session_state.p_fee if use_pickup else 0.0
    applied_f_fee = st.session_state.f_fee if use_first else 0.0

    if pickup_dist > 10.00:
        calc_type = "遠距離スリップ適用（10.01km〜）"
        billable_dist = max(0.0, (pickup_dist + real_dist) - 10.0)
        fare_meter = billable_dist * st.session_state.u_price
        total_fare = fare_meter + applied_f_fee + tip_amount
        if fare_meter > 0: detail_parts.append(f"スリップ走行({billable_dist:.2f}km)")
        if use_first: detail_parts.append(f"初乗り{int(applied_f_fee):,}円")
    else:
        calc_type = "近距離固定適用（〜10.00km）"
        fare_meter = real_dist * st.session_state.u_price
        total_fare = fare_meter + applied_p_fee + applied_f_fee + tip_amount
        if fare_meter > 0: detail_parts.append(f"実車走行({real_dist:.2f}km)")
        if use_first: detail_parts.append(f"初乗り{int(applied_f_fee):,}円")
        if use_pickup: detail_parts.append(f"配車料{int(applied_p_fee):,}円")
    
    if tip_amount > 0:
        detail_parts.append(f"お気持ち{int(tip_amount):,}円")

# --- 結果表示 ---
with st.container(border=True):
    st.write(f"📊 判定結果: **{calc_type}**")
    st.markdown(f"### 💰 合計金額:  **{int(total_fare):,} 円**")

# 領収書テキスト
receipt_details = "＋".join(detail_parts) if detail_parts else "基本料金のみ"
receipt = f"【タクシー領収書】合計:{int(total_fare):,}円 (内訳:{receipt_details} / 担当:{driver})"
st.text_input("チャット用コピー", value=receipt)

if st.button(f"🚀 {driver} の実績を記録"):
    with st.spinner("記録中..."):
        df, sha = get_csv_from_github()
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst).strftime("%Y-%m-%d %H:%M:%S")
        new_row = pd.DataFrame([[now, driver, pickup_dist, real_dist, total_fare, receipt]], columns=["timestamp", "driver", "pickup_dist", "real_dist", "fare", "details"])
        df = pd.concat([df, new_row], ignore_index=True)
        save_to_github(df, sha, f"Taxi log by {driver}")
        st.success("日報に記録しました！"); st.rerun()

st.divider()
with st.expander("📋 計算の根拠"):
    if pay_mode:
        st.write("手動入力モードのため、計算式は使用していません。")
    elif pickup_dist > 10.00:
        st.write("10km超のため配車手数料は0円として計算します。")
        st.write(f"式: (({pickup_dist} + {real_dist}) - 10.0) × {st.session_state.u_price} + 初乗り({applied_f_fee}) + チップ")
    else:
        st.write("10km以内のため配車手数料と初乗りを両方加算します。")
        st.write(f"式: ({real_dist} × {st.session_state.u_price}) + 配車料({applied_p_fee}) + 初乗り({applied_f_fee}) + チップ")

st.subheader("📊 緑間タクシー 運行日報")
if st.button("🔄 最新の履歴を読み込む"):
    df_display, _ = get_csv_from_github()
    if not df_display.empty:
        # 最新の記録が上にくるようにソートして表示
        st.dataframe(df_display.sort_values(by="timestamp", ascending=False), use_container_width=True)
    else:
        st.info("記録はありません。")
