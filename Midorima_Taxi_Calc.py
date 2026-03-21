import streamlit as st
import pandas as pd
import requests
import base64
from datetime import datetime
import pytz
import io

# 設定
GITHUB_REPO = "Lichtmido/Midorima_Taxi_Calculator" 
CSV_FILE = "taxi_log.csv"
TOKEN = st.secrets["GH_TOKEN"]

# 定数\
DEFAULT_UNIT_PRICE = 20000.0  # 1km単価 (2.0万)
DEFAULT_PICKUP_FEE = 10000.0  # 配車手数料 (1.0万)
FIRST_RIDE_FEE = 10000.0      # 初乗り運賃 (1.0万)
FIRST_RIDE_DIST = 2.0         # 初乗り距離 (2.0km)
SLIP_LIMIT = 2.0              # スリップ上限 (2.0km)

st.set_page_config(page_title="緑間タクシー専用料金計算機 Pro", layout="centered")

# GitHub API連携関数
def get_csv_from_github():
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CSV_FILE}"
    headers = {"Authorization": f"token {TOKEN}"}
    res = requests.get(url, headers=headers)
    if res.status_code == 200:
        content = base64.b64decode(res.json()["content"]).decode("utf-8")
        df = pd.read_csv(io.StringIO(content))
        return df, res.json()["sha"]
    # ファイルがない場合は空のDFを返す
    return pd.DataFrame(columns=["timestamp", "driver", "pickup_dist", "real_dist", "fare", "details"]), None

def save_to_github(df, sha, message):
    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{CSV_FILE}"
    headers = {"Authorization": f"token {TOKEN}"}
    content = base64.b64encode(df.to_csv(index=False).encode("utf-8")).decode("utf-8")
    data = {"message": message, "content": content, "sha": sha}
    requests.put(url, headers=headers, json=data)

# メイン画面
st.title("🚖 緑間タクシー専用料金計算機")

# ドライバー選択の追加
driver = st.radio("担当ドライバー", ["緑間理人", "緑間きのこ"], horizontal=True)

# 料金設定
if 'unit_price' not in st.session_state:
    st.session_state.unit_price = DEFAULT_UNIT_PRICE
if 'pickup_fee' not in st.session_state:
    st.session_state.pickup_fee = DEFAULT_PICKUP_FEE

with st.expander("⚙️ 料金設定の一時変更"):
    st.info("※ここで変更しても、アプリを再読み込みすると初期値に戻ります。")
    st.session_state.unit_price = st.number_input("1km単価 (円)", value=st.session_state.unit_price, step=1000.0)
    st.session_state.pickup_fee = st.number_input("配車手数料 (円)", value=st.session_state.pickup_fee, step=500.0)

st.divider()

col1, col2 = st.columns(2)
with col1:
    # 小数点第二位まで、step=0.01
    pickup_dist = st.number_input("① 迎車距離 (km)", min_value=0.0, max_value=10.0, step=0.01, format="%.2f")
with col2:
    real_dist = st.number_input("② 実車距離 (km)", min_value=0.0, step=0.01, format="%.2f")

use_pickup_fee = st.toggle(f"配車手数料 ({int(st.session_state.pickup_fee):,}円) を適用", value=True)

# 計算ロジック
applied_slip = min(pickup_dist, SLIP_LIMIT)
remaining_first_ride = max(0.0, FIRST_RIDE_DIST - applied_slip)
billable_dist = max(0.0, real_dist - remaining_first_ride)

fare_meter = billable_dist * st.session_state.unit_price
applied_pickup_fee = st.session_state.pickup_fee if use_pickup_fee else 0
total_fare = FIRST_RIDE_FEE + fare_meter + applied_pickup_fee

st.divider()
st.markdown(f"### 💰 合計請求金額:  **{int(total_fare):,} 円**")

receipt = f"【タクシー領収書】合計:{int(total_fare):,}円 (内訳:初乗り{int(FIRST_RIDE_FEE):,}円"
if fare_meter > 0:
    receipt += f"＋走行分{int(fare_meter):,}円"
if use_pickup_fee:
    receipt += f"＋配車料{int(applied_pickup_fee):,}円"
receipt += f" / 担当:{driver})"

st.text_input("チャット用コピー（スマホなら長押し）", value=receipt)

# 日報保存ボタン
if st.button(f"🚀 {driver} の実績として日報に記録する"):
    with st.spinner("GitHubに記録中..."):
        df, sha = get_csv_from_github()
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst).strftime("%Y-%m-%d %H:%M:%S")
        
        new_row = pd.DataFrame([[now, driver, pickup_dist, real_dist, total_fare, receipt]], 
                                columns=["timestamp", "driver", "pickup_dist", "real_dist", "fare", "details"])
        df = pd.concat([df, new_row], ignore_index=True)
        save_to_github(df, sha, f"Taxi log by {driver}")
        st.success(f"保存しました！お疲れ様です。")
        st.rerun()

# 実績の見える化（ダッシュボード）
st.divider()
st.subheader("📊 本日の運行実績")
df_all, sha_latest = get_csv_from_github()

if not df_all.empty:
    df_all['timestamp'] = pd.to_datetime(df_all['timestamp'])
    today = datetime.now(pytz.timezone('Asia/Tokyo')).date()
    df_today = df_all[df_all['timestamp'].dt.date == today]

    if not df_today.empty:
        m1, m2, m3 = st.columns(3)
        m1.metric("今日の総売上", f"{int(df_today['fare'].sum()):,}円")
        m2.metric("総実車距離", f"{df_today['real_dist'].sum():.2f}km")
        m3.metric("乗車回数", f"{len(df_today)}回")
        
        # ドライバー別
        st.write("▼ ドライバー別内訳")
        summary = df_today.groupby('driver').agg({
            'fare': 'sum',
            'real_dist': 'sum'
        }).rename(columns={'fare': '売上合計', 'real_dist': '距離合計'})
        st.table(summary.style.format({'売上合計': '{:,.0f}円', '距離合計': '{:.2f}km'}))
    else:
        st.info("本日の記録はまだありません。")

    # 履歴取り消し（直近5件）
    with st.expander("🕒 直近5件の履歴・取り消し"):
        recent = df_all.tail(5).iloc[::-1]
        for idx, row in recent.iterrows():
            c_left, c_right = st.columns([4, 1])
            c_left.write(f"{row['timestamp'].strftime('%H:%M')} | {row['driver']} | {int(row['fare']):,}円")
            if c_right.button("消去", key=f"del_{idx}"):
                df_all = df_all.drop(idx)
                save_to_github(df_all, sha_latest, f"Delete log at {row['timestamp']}")
                st.rerun()

# 内部計算の詳細（既存コード維持）
with st.expander("詳細な内部計算"):
    st.write(f"迎車スリップ(上限{SLIP_LIMIT}km): {applied_slip:.2f} km")
    st.write(f"初乗り無料の残り: {remaining_first_ride:.2f} km")
    st.write(f"加算対象距離: {billable_dist:.2f} km")

st.divider()
st.caption(f"設定: 単価{int(st.session_state.unit_price):,}円 / 初乗り{FIRST_RIDE_DIST}km / スリップ上限{SLIP_LIMIT}km")
