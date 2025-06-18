import os
import json
import streamlit as st
from streamlit.runtime.scriptrunner import RerunException
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import plotly.express as px

# 共通CSS（ライトモード想定）
css = """
<style>
    body, .block-container {
        background-color: white !important;
        color: black !important;
    }
    input, textarea, select, .stTextInput>div>input, .stTextArea>div>textarea {
        background-color: white !important;
        color: black !important;
        border: 1px solid #ccc !important;
    }
    .stButton>button {
        background-color: #eee !important;
        color: black !important;
        border: 1px solid #ccc !important;
    }
    div[role="combobox"] > div {
        background-color: white !important;
        color: black !important;
        border: 1px solid #ccc !important;
    }
</style>
"""

st.markdown(css, unsafe_allow_html=True)

plt.rcParams['font.family'] = 'Meiryo'

# --- Google Sheets認証セットアップ ---

SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

# 環境変数からJSON文字列を取得して辞書に変換
service_account_info = json.loads(os.environ['GOOGLE_SERVICE_ACCOUNT_JSON'])

credentials = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
gc = gspread.authorize(credentials)


SPREADSHEET_ID = '1a9fDIVwcUUHAZZpsAPdLZRsy42WsyIhi8fC-xmqkJd0'
sh = gc.open_by_key(SPREADSHEET_ID)
worksheet = sh.sheet1

# --- サイドバーでページ選択 ---
st.sidebar.title("メニュー")
page = st.sidebar.radio("ページを選択", ["記録入力", "これまでの記録", "グラフ表示", "絞り込み", "今日歌った曲"])

# --- データ取得 ---
records = worksheet.get_all_records()
df = pd.DataFrame(records) if records else pd.DataFrame(columns=['歌った日付','アーティスト名','曲名','キー','点数','カラオケ機種','コメント','リベンジ'])
df['歌った日付'] = pd.to_datetime(df['歌った日付'], format='%y/%m/%d', errors='coerce')

# --- 前処理 ---
song_counts = df.groupby('曲名').size()
df['曲名_曲数'] = df['曲名'].map(song_counts).fillna(0).astype(int)

artist_counts = df['アーティスト名'].value_counts()
artist_list = artist_counts.index.tolist()


# --- 記録入力 ---
if page == "記録入力":
    st.title("カラオケ点数入力")

    new_artist = st.text_input("新しいアーティスト名を入力（選択肢にない場合）")
    selected_artist = new_artist if new_artist else (st.selectbox('アーティスト名を選択', artist_list) if artist_list else '')

    if selected_artist:
        artist_df = df[df['アーティスト名'] == selected_artist]
        song_max_scores = artist_df.groupby('曲名')['点数'].max().sort_values(ascending=False)
        songs_for_artist = song_max_scores.index.tolist()
    else:
        songs_for_artist = []

    new_song = st.text_input("新しい曲名を入力（選択肢にない場合）")
    selected_song = new_song if new_song else (st.selectbox('曲名を選択', songs_for_artist) if songs_for_artist else '')

    date = st.date_input('歌った日付', datetime.date.today())
    key = st.text_input('キー', value='原')

    default_score = None
    if selected_artist and selected_song:
        match = df[(df['アーティスト名'] == selected_artist) & (df['曲名'] == selected_song)]
        if not match.empty:
            default_score = match['点数'].max()

    score = st.number_input(
        '点数', min_value=0.0, max_value=100.0, step=0.001, format="%.3f",
        value=float(f"{default_score:.3f}") if default_score else 0.0
    )

    karaoke_machine = st.selectbox('カラオケ機種', ['JOYSOUND AI','JOYSOUND 分析採点', 'DAM AI', 'DAM DXG','DAM DX'], index=2)
    comment = st.text_area('コメント・メモ')

    if st.button('記録する', key='record_button'):
        if not selected_artist or not selected_song:
            st.error('アーティスト名と曲名は必須です。')
        else:
            row = [
    date.strftime('%y/%m/%d'),
    selected_artist,
    selected_song,
    key,
    f"{score:.3f}",
    karaoke_machine,
    comment
]

            worksheet.append_row(row)
            st.success('データをGoogle Sheetsに記録しました！')
            st.experimental_rerun()


# --- これまでの記録 ---

elif page == "これまでの記録":
    st.title("これまでの記録")

    idx = df.groupby(['アーティスト名', '曲名'])['点数'].idxmax()
    df = df.loc[idx].copy()

    df['歌った日付'] = df['歌った日付'].dt.strftime('%Y-%m-%d')
    df['点数'] = df['点数'].apply(lambda x: f"{x:.3f}")

    def insert_blank_rows(df, group_col='アーティスト名'):
        rows, prev = [], None
        for _, row in df.iterrows():
            if prev and row[group_col] != prev:
                rows.append({col: '' for col in df.columns})
            rows.append(row.to_dict())
            prev = row[group_col]
        return pd.DataFrame(rows)

    def highlight_score(val):
        try:
            v = float(val)
        except:
            return ''
        if v >= 95:
            return 'background-color: #ff9999; font-weight: bold;'
        elif v >= 90:
            return 'background-color: #ffcc80;'
        return ''

    if not df.empty:
        artist_song_counts = df.groupby('アーティスト名')['曲名'].nunique()
        df['アーティスト_曲数'] = df['アーティスト名'].map(artist_song_counts).fillna(0).astype(int)
        df_one = df[df['アーティスト_曲数'] == 1].sort_values(by=['点数', '歌った日付'], ascending=[False, False])
        df_multi = df[df['アーティスト_曲数'] > 1].sort_values(by=['アーティスト_曲数', 'アーティスト名', '点数', '歌った日付'], ascending=[False, True, False, False])
        df_sorted = pd.concat([df_multi, df_one]).drop(columns=['アーティスト_曲数']).reset_index(drop=True)
        styled_df = insert_blank_rows(df_sorted).style.applymap(highlight_score, subset=['点数'])
        st.dataframe(styled_df)
    else:
        st.write("まだ記録がありません。")


# --- グラフ表示ページ ---
elif page == "グラフ表示":
    st.title("点数推移グラフ")

    filter_artist = st.selectbox('グラフ表示: アーティスト選択', [''] + artist_list)
    if filter_artist:
        songs_for_filter = sorted(df[df['アーティスト名'] == filter_artist]['曲名'].dropna().unique().tolist())
        filter_song = st.selectbox('グラフ表示: 曲名選択（空欄で全曲表示）', [''] + songs_for_filter)

        df_orig = pd.DataFrame(records)
        df_orig['歌った日付'] = pd.to_datetime(df_orig['歌った日付'], format='%y/%m/%d', errors='coerce')

        if filter_song:
            df_filtered = df_orig[(df_orig['アーティスト名'] == filter_artist) & (df_orig['曲名'] == filter_song)]
            if not df_filtered.empty:
                df_filtered = df_filtered.sort_values('歌った日付')
                fig = px.line(df_filtered, x='歌った日付', y='点数', title=f"{filter_artist} - {filter_song} の点数推移", markers=True)
                fig.update_traces(hovertemplate='日付: %{x|%Y-%m-%d}<br>点数: %{y:.3f}')
                fig.update_xaxes(tickformat="%Y年%-m月%-d日")  # ←ここで日本語日付フォーマットに変更
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.write("該当するデータがありません。")
        else:
            df_filtered = df_orig[df_orig['アーティスト名'] == filter_artist]
            if not df_filtered.empty:
                df_filtered = df_filtered.sort_values('歌った日付')
                fig = px.line(df_filtered, x='歌った日付', y='点数', color='曲名', title=f"{filter_artist} の全曲点数推移", markers=True)
                fig.update_traces(hovertemplate='曲名: %{legendgroup}<br>日付: %{x|%Y-%m-%d}<br>点数: %{y:.3f}')
                fig.update_xaxes(tickformat="%Y年%-m月%-d日")  # ←ここも同じく日本語表示
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.write("該当するデータがありません。")
    else:
        st.write("まだ記録がありません。")


# --- 絞り込みページ ---
def highlight_score(val):
    try:
        v = float(val)
    except:
        return ''
    if v >= 95:
        return 'background-color: #ff9999; font-weight: bold;'
    elif v >= 90:
        return 'background-color: #ffcc80;'
    return ''

if page == '絞り込み':
    st.subheader("絞り込み検索")

    if df.empty:
        st.write("まだ記録がありません。")
    else:
        # 日付フィルター
        st.markdown("#### 日付で絞り込み（任意）")
        min_date = df['歌った日付'].min().date()
        max_date = df['歌った日付'].max().date()

        use_date_filter = st.checkbox('日付で絞り込む', value=False)

        today = datetime.date.today()

        if use_date_filter:
            if min_date <= today <= max_date:
                default_start = today
            else:
                default_start = max_date
            default_end = default_start
            start_date = st.date_input('開始日', min_value=min_date, max_value=max_date, value=default_start)
            end_date = st.date_input('終了日', min_value=min_date, max_value=max_date, value=default_end)
        else:
            start_date = None
            end_date = None

        # アーティストフィルター
        st.markdown("#### アーティストで絞り込み")
        artist_option = st.selectbox('アーティストを選択（任意）', [''] + artist_list)

        # フィルター処理
        df_filtered = df.copy()
        df_filtered['歌った日付'] = pd.to_datetime(df_filtered['歌った日付'], errors='coerce')

        if use_date_filter and start_date and end_date:
            df_filtered = df_filtered[(df_filtered['歌った日付'].dt.date >= start_date) & (df_filtered['歌った日付'].dt.date <= end_date)]

        if artist_option:
            df_filtered = df_filtered[df_filtered['アーティスト名'] == artist_option]

        df_filtered['歌った日付'] = df_filtered['歌った日付'].dt.strftime('%Y-%m-%d')
        df_filtered['点数'] = df_filtered['点数'].apply(lambda x: f"{float(x):.3f}")

        # 点数順でソート（降順）
        df_filtered = df_filtered.sort_values(by='点数', ascending=False)

        st.markdown("#### 絞り込み結果")
        if not df_filtered.empty:
            styled_df = df_filtered.style.applymap(highlight_score, subset=['点数'])
            st.dataframe(styled_df)
        else:
            st.write("該当するデータがありません。")

# --- 今日歌った曲 ---
if page == "今日歌った曲":
    st.title("今日歌った曲")

    today = datetime.date.today()

    # 文字列整形（全体データ）
    df['曲名'] = df['曲名'].astype(str).str.strip()
    df['アーティスト名'] = df['アーティスト名'].astype(str).str.strip()

    # 点数をfloatに変換（全体データ）
    df['点数'] = pd.to_numeric(df['点数'], errors='coerce')

    # ① 全体データで同曲内順位を計算
    df['同曲内順位'] = df.groupby('曲名')['点数'].rank(method='min', ascending=False).astype(int)

    # 曲名ごとの歌唱回数（全体）
    曲名曲数 = df.groupby('曲名')['曲名'].transform('count')
    df['曲名_曲数'] = 曲名曲数

    # ② アーティストごとの曲の最高点を取得し、アーティスト内順位を計算
    artist_top = df.groupby(['アーティスト名', '曲名'], as_index=False)['点数'].max()
    artist_top['アーティスト内順位'] = artist_top.groupby('アーティスト名')['点数'].rank(method='min', ascending=False).astype(int)

    # ③ 曲ごとの最高点を取得し、全体順位を計算
    overall_top = df.groupby('曲名', as_index=False)['点数'].max()
    overall_top['全体順位'] = overall_top['点数'].rank(method='min', ascending=False).astype(int)

    # 今日歌った曲だけ抽出
    df_today = df[df['歌った日付'].dt.date == today].copy()

    if df_today.empty:
        st.write("今日の記録はありません。")
    else:
        # 今日のデータも文字列整形（念のため）
        df_today['曲名'] = df_today['曲名'].astype(str).str.strip()
        df_today['アーティスト名'] = df_today['アーティスト名'].astype(str).str.strip()

        # 点数数値変換チェック（念のため）
        df_today['点数'] = pd.to_numeric(df_today['点数'], errors='coerce')
        if df_today['点数'].isnull().any():
            st.warning("点数に数値でない値が含まれています。")

        # --- ① 同曲内順位 と 曲名_曲数 はすでに df_today にある（全体基準の順位）
        # 表示用の列を整理
        cols_1 = ['曲名_曲数', '同曲内順位', '歌った日付', 'アーティスト名', '曲名', 'キー', '点数', 'カラオケ機種']
        if 'コメント' in df_today.columns:
            cols_1.append('コメント')

        # 日付文字列化
        df_today['歌った日付'] = df_today['歌った日付'].dt.strftime('%Y-%m-%d')

        df_today_display = df_today[cols_1]
        st.markdown("### ① 同じ曲を複数回歌った場合の中での点数順位（重複あり）")
        styled_df1 = df_today_display.sort_values(by=['曲名', '同曲内順位']).style.applymap(highlight_score, subset=['点数'])
        st.dataframe(styled_df1)

        # --- ② アーティスト内順位を df_today にマージする
        df_today_artist_top = pd.merge(df_today, artist_top[['アーティスト名', '曲名', 'アーティスト内順位']], 
                                      on=['アーティスト名', '曲名'], how='left')

        cols_2 = ['アーティスト内順位', 'アーティスト名', '曲名', '点数']
        artist_top_display = df_today_artist_top[cols_2].drop_duplicates()
        st.markdown("### ② アーティストごとの曲（重複なし）の中での最高得点順位")
        styled_df2 = artist_top_display.sort_values(by=['アーティスト名', 'アーティスト内順位']).style.applymap(highlight_score, subset=['点数'])
        st.dataframe(styled_df2)

        # --- ③ 全体順位を df_today にマージする
        df_today_overall_top = pd.merge(df_today, overall_top[['曲名', '全体順位']], on='曲名', how='left')

        cols_3 = ['全体順位', '曲名', '点数']
        overall_top_display = df_today_overall_top[cols_3].drop_duplicates()
        st.markdown("### ③ 全曲（重複なし）の中での最高得点順位")
        styled_df3 = overall_top_display.sort_values(by='全体順位').style.applymap(highlight_score, subset=['点数'])
        st.dataframe(styled_df3)
