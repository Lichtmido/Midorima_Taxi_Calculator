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

# 定数
UNIT_PRICE = 20000.0  # 1km単価
PICKUP_FEE = 10000.0  # 配車手数料（10km以下の時に適用）
FIRST_FEE = 10000.0   # 初乗り運賃（10.01km以上の時に適用）

st.set_page_config(page_title="緑間タクシー 料金計算機", layout="centered")

# GitHub連携関数
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

# メイン画面
st.title("🚖 緑間タクシー 料金計算機")

driver = st.radio("担当ドライバー", ["緑間理人", "緑間きのこ"], horizontal=True)

st.divider()

# 距離入力
col1, col2 = st.columns(2)
with col1:
    pickup_dist = st.number_input("① 迎車距離 (km)", min_value=0.0, step=0.01, format="%.2f", help="10.00kmまで固定、10.01kmからスリップ")
with col2:
    real_dist = st.number_input("② 実車距離 (km)", min_value=0.0, step=0.01, format="%.2f")

# 自動判定ロジック (10.00km境界) ---
if pickup_dist > 10.00:
    # 【パターン1：10.01km以上はスリップ制】
    calc_type = "遠距離スリップ（10.01km以上）"
    # 計算式: (迎車 + 実車) - 10kmサービス
    billable_dist = (pickup_dist + real_dist) - 10.0
    fare_meter = billable_dist * UNIT_PRICE
    total_fare = fare_meter + FIRST_FEE
    detail_msg = f"スリップ走行({billable_dist:.2f}km)＋初乗り"
else:
    # 【パターン2：10.00kmまでは固定制】
    calc_type = "近距離固定（10.00km以下）"
    # 計算式: 実車距離のみ課金 + 配車手数料
    fare_meter = real_dist * UNIT_PRICE
    total_fare = fare_meter + PICKUP_FEE
    detail_msg = f"実車走行({real_dist:.2f}km)＋配車手数料"

# 結果表示
with st.container(border=True):
    st.write(f"📊 判定結果: **{calc_type}**")
    st.markdown(f"### 💰 合計金額:  **{int(total_fare):,} 円**")

# 領収書テキスト
receipt = f"【タクシー領収書】合計:{int(total_fare):,}円 ({detail_msg} / 担当:{driver})"
st.text_input("チャット用コピー", value=receipt)

# 保存・履歴表示
if st.button(f"🚀 {driver} の実績を記録"):
    with st.spinner("記録中..."):
        df, sha = get_csv_from_github()
        jst = pytz.timezone('Asia/Tokyo')
        now = datetime.now(jst).strftime("%Y-%m-%d %H:%M:%S")
        new_row = pd.DataFrame([[now, driver, pickup_dist, real_dist, total_fare, receipt]], 
                                columns=["timestamp", "driver", "pickup_dist", "real_dist", "fare", "details"])
        df = pd.concat([df, new_row], ignore_index=True)
        save_to_github(df, sha, f"Taxi log by {driver}")
        st.success("日報に記録しました！"); st.rerun()

st.divider()
with st.expander("📋 計算の根拠を表示"):
    if pickup_dist > 10.00:
        st.write(f"10.01km以上の判定により **スリップ制** を適用しました。")
        st.write(f"計算: (({pickup_dist} + {real_dist}) - 10.0) × {int(UNIT_PRICE):,} + {int(FIRST_FEE):,}")
    else:
        st.write(f"10.00km以下の判定により **固定制** を適用しました。")
        st.write(f"計算: ({real_dist} × {int(UNIT_PRICE):,}) + {int(PICKUP_FEE):,}")

# 履歴表示
st.subheader("📊 本日の実績")
df_all, _ = get_csv_from_github()
if not df_all.empty:
    df_all['timestamp'] = pd.to_datetime(df_all['timestamp'])
    today = datetime.now(pytz.timezone('Asia/Tokyo')).date()
    df_today = df_all[df_all['timestamp'].dt.date == today]
    if not df_today.empty:
        st.metric("今日の総売上", f"{int(df_today['fare'].sum()):,}円")
