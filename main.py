import json
import re
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

# 페이지 기본 설정
st.set_page_config(page_title="전국 고령화 단계구분도", layout="wide")

st.title("2026년 전국 시군구별 고령화율 단계구분도")
st.caption(
    "전국 읍·면·동 인구 데이터를 시군구(5자리 코드) 단위로 집계하여 65세 이상 고령화율(%)을 시각화합니다."
)


@st.cache_data
def load_data():
    # 1. 시군구 GeoJSON 불러오기 (우선순위: 로컬 파일 -> Raw URL)
    geojson_data = None
    try:
        with open("sigungu_kr.geojson.txt", "r", encoding="utf-8") as f:
            geojson_data = json.load(f)
    except Exception:
        geojson_url = "https://raw.githubusercontent.com/kdoyun09/-/main/sigungu_kr.geojson.txt"
        res = requests.get(geojson_url, timeout=10)
        res.raise_for_status()
        geojson_data = res.json()

    # 2. 인구 CSV (ZIP) 불러오기
    csv_url = "https://raw.githubusercontent.com/first2022-cyber/contents/main/population_ts_yearly_gender.zip"
    df = pd.read_csv(csv_url)

    # 3. 2026년 데이터만 필터링 (숫자/문자열 모두 안전하게 처리)
    df_2026 = df[df["연도"].astype(str) == "2026"].copy()

    # 4. 코드를 8자리 문자열로 가공 후 시군구 5자리 코드 추출
    df_2026["코드"] = (
        df_2026["코드"].astype(str).str.split(".").str[0].str.zfill(8)
    )
    df_2026["sigungu_code"] = df_2026["코드"].str[:5]

    # 5. 전체 인구 열 및 65세 이상 인구 열 구분
    total_cols = [c for c in df_2026.columns if str(c).startswith("계_")]

    senior_cols = []
    for c in total_cols:
        match = re.search(r"\d+", str(c))
        if match:
            if int(match.group()) >= 65:
                senior_cols.append(c)
        elif "100" in str(c):
            senior_cols.append(c)

    # 6. 인구 열 숫자형 강제 변환 및 결측치 0 처리
    for c in total_cols:
        df_2026[c] = pd.to_numeric(df_2026[c], errors="coerce").fillna(0)

    # 7. 행별 인구 합계 계산
    df_2026["전체인구"] = df_2026[total_cols].sum(axis=1)
    df_2026["고령인구"] = df_2026[senior_cols].sum(axis=1)

    # 8. 시군구별 집계 및 고령화율 계산
    grouped = (
        df_2026.groupby("sigungu_code")[["전체인구", "고령인구"]]
        .sum()
        .reset_index()
    )

    # 분모가 0인 경우 예외 처리
    grouped["고령화율"] = 0.0
    valid_mask = grouped["전체인구"] > 0
    grouped.loc[valid_mask, "고령화율"] = (
        grouped.loc[valid_mask, "고령인구"] / grouped.loc[valid_mask, "전체인구"]
    ) * 100
    grouped["고령화율"] = grouped["고령화율"].round(2)

    # GeoJSON의 시군구/시도 명칭 매핑
    code_to_info = {}
    for feat in geojson_data.get("features", []):
        props = feat.get("properties", {})
        code = str(props.get("코드", "")).strip()
        sigungu_name = f"{props.get('시도', '')} {props.get('시군구', '')}".strip()
        code_to_info[code] = sigungu_name

    grouped["시군구명"] = grouped["sigungu_code"].map(code_to_info)
    grouped["시군구명"] = grouped["시군구명"].fillna(grouped["sigungu_code"])

    return geojson_data, grouped


# 데이터 로드 실행
with st.spinner("데이터를 불러오는 중입니다..."):
    geojson_data, df_map = load_data()

# 9. Plotly 단계구분도 지도 생성
fig = px.choropleth_mapbox(
    df_map,
    geojson=geojson_data,
    locations="sigungu_code",
    featureidkey="properties.코드",
    color="고령화율",
    color_continuous_scale="Reds",
    range_color=(0, df_map["고령화율"].max()),
    mapbox_style="white-bg",
    center={"lat": 35.9, "lon": 127.8},
    zoom=6,
    hover_name="시군구명",
    hover_data={"sigungu_code": False, "고령화율": ":.2f%"},
    labels={"고령화율": "고령화율(%)"},
)

fig.update_layout(
    margin={"r": 0, "t": 30, "l": 0, "b": 0},
    height=720,
    title_text="전국 시군구별 65세 이상 고령화율 (%)",
)

st.plotly_chart(fig, use_container_width=True)

# 주요 통계 출력
col1, col2, col3 = st.columns(3)
max_idx = df_map["고령화율"].idxmax()
min_idx = df_map["고령화율"].idxmin()

col1.metric(
    "최고 고령화율 지역",
    f"{df_map.loc[max_idx, '시군구명']}",
    f"{df_map.loc[max_idx, '고령화율']}%",
)
col2.metric(
    "최저 고령화율 지역",
    f"{df_map.loc[min_idx, '시군구명']}",
    f"{df_map.loc[min_idx, '고령화율']}%",
)
col3.metric("시군구 평균 고령화율", f"{df_map['고령화율'].mean():.2f}%")
