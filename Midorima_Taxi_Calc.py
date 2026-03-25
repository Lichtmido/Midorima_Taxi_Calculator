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

# --- 料金設定のセッション管理（一時変更用） ---
if 'u_price' not in st.session_state: st.session_state.u_price = D_UNIT_PRICE
if 'p_fee' not in st.session_state: st.session_state.p_fee = D_PICKUP_FEE
if 'f_fee' not in st.session_state: st.session_state.f_fee = D_FIRST_FEE

# --- メイン画面 ---
st.title("🚖 緑間タクシー 料金計算機")

driver = st.radio("担当ドライバー", ["緑間理人", "緑間きのこ"], horizontal=True)

# 料金設定の一時変更セクション
with st.expander("⚙️ 料金単価・手数料の一時設定"):
    st.info("※リロードすると初期値（2万/1万）に戻ります。")
    st.session_state.u_price = st.number_input("1km単価 (円)", value=st.session_state.u_price, step=1000.0)
    st.session_state.p_fee = st.number_input("配車手数料 (円)", value=st.session_state.p_fee, step=500.0)
    st.session_state.f_fee = st.number_input("初乗り運賃 (円)", value=st.session_state.f_fee, step=500.0)

st.divider()

# 距離入力
col1, col2 = st.columns(2)
with col1:
    pickup_dist = st.number_input("① 迎車距離 (km)", min_value=0.0, step=0.01, format="%.2f", help="10.00kmまで固定、10.01kmからスリップ")
with col2:
    real_dist = st.number_input("② 実車距離 (km)", min_value=0.0, step=0.01, format="%.2f")

# オプションスイッチ
st.write("🔧 手数料・運賃の適用設定")
c1, c2 = st.columns(2)
with c1:
    use_pickup = st.toggle("配車手数料を適用", value=True)
with c2:
    use_first = st.toggle("初乗り運賃を適用", value=True)

# --- 🚀 理人さん専用・自動判定計算ロジック ---
# 手数料の適用値を決定
applied_p_fee = st.session_state.p_fee if use_pickup else 0.0
applied_f_fee = st.session_state.f_fee if use_first else 0.0

if pickup_dist > 10.00:
    # 【遠距離スリップ】10.01km〜
    calc_type = "遠距離スリップ（10.01km〜）"
    # 計算式: (迎車 + 実車 - 10km) × 単価 + 初乗り
    billable_dist = max(0.0, (pickup_dist + real_dist) - 10.0)
    fare_meter = billable_dist * st.session_state.u_price
    total_fare = fare_meter + applied_f_fee
    method_label = f"走行分({billable_dist:.2f}km)"
else:
    # 【近距離固定】〜10.00km
    calc_type = "近距離固定（〜10.00km）"
    # 計算式: (実車 × 単価) + 配車手数料
    fare_meter = real_dist * st.session_state.u_price
    total_fare = fare_meter + applied_p_fee
    method_label = f"実車走行分({real_dist:.2f}km)"

# --- 結果表示 ---
with st.container(border=True):
    st.write(f"📊 判定結果: **{calc_type}**")
    st.markdown(f"### 💰 合計金額:  **{int(total_fare):,} 円**")

# 領収書テキスト生成
detail_parts = []
if fare_meter > 0: detail_parts.append(method_label)
if use_pickup and pickup_dist <= 10.00: detail_parts.append(f"配車料{int(applied_p_fee):,}円")
if use_first and pickup_dist > 10.00: detail_parts.append(f"初乗り{int(applied_f_fee):,}円")

receipt_details = "＋".join(detail_parts) if detail_parts else "基本料金のみ"
receipt = f"【タクシー領収書】合計:{int(total_fare):,}円 (内訳:{receipt_details} / 担当:{driver})"

st.text_input("チャット用コピー（スマホ長押し）", value=receipt)

# 保存ボタン
if st.button(f"🚀 {driver} の実績を記録"):
    with st.spinner("GitHubに保存中..."):
        df, sha = get_csv_from_github()
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst).strftime("%Y-%m-%d %H:%M:%S")
        new_row = pd.DataFrame([[now, driver, pickup_dist, real_dist, total_fare, receipt]], 
                                columns=["timestamp", "driver", "pickup_dist", "real_dist", "fare", "details"])
        df = pd.concat([df, new_row], ignore_index=True)
        save_to_github(df, sha, f"Taxi log by {driver}")
        st.success("日報に記録しました！"); st.rerun()

st.divider()
with st.expander("🕒 本日の実績・履歴"):
    df_all, _ = get_csv_from_github()
    if not df_all.empty:
        df_all['timestamp'] = pd.to_datetime(df_all['timestamp'])
        today = datetime.now(pytz.timezone('Asia/Tokyo')).date()
        df_today = df_all[df_all['timestamp'].dt.date == today]
        if not df_today.empty:
            st.metric("今日の総売上", f"{int(df_today['fare'].sum()):,}円")
            st.table(df_today[['timestamp', 'driver', 'fare']].tail(5))
        else:
            st.info("本日のデータはありません。")
