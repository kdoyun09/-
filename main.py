import json
import re
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="전국 고령화 단계구분도", layout="wide")

st.title("2026년 전국 시군구별 고령화율 단계구분도")
st.caption(
    "전국 읍·면·동 인구 데이터를 시군구(5자리 코드) 단위로 집계하여 65세 이상 고령화율(%)을 시각화합니다."
)


@st.cache_data
def load_data():
    # 1. GeoJSON 로드
    geojson_data = None
    try:
        with open("sigungu_kr.geojson.txt", "r", encoding="utf-8") as f:
            geojson_data = json.load(f)
    except Exception:
        geojson_url = "https://raw.githubusercontent.com/kdoyun09/-/main/sigungu_kr.geojson.txt"
        res = requests.get(geojson_url, timeout=15)
        res.raise_for_status()
        geojson_data = res.json()

    # GeoJSON 내부 속성 코드 정리 (문자열 변환 및 앞 5자리 보장)
    code_to_info = {}
    for feat in geojson_data.get("features", []):
        props = feat.get("properties", {})
        raw_code = str(props.get("코드", "")).strip()
        # 소수점 제거 및 앞 5자리 문자열로 가공
        clean_code = raw_code.split(".")[0].zfill(5)[:5]
        props["코드"] = clean_code

        sigungu_name = f"{props.get('시도', '')} {props.get('시군구', '')}".strip()
        code_to_info[clean_code] = sigungu_name

    # 2. CSV 인구 데이터 로드
    csv_url = "https://raw.githubusercontent.com/first2022-cyber/contents/main/population_ts_yearly_gender.zip"
    df = pd.read_csv(csv_url)

    # 3. 2026년 데이터만 필터링
    df_2026 = df[df["연도"].astype(str) == "2026"].copy()

    # 4. 시군구 5자리 코드 추출 (문자열)
    df_2026["코드_str"] = (
        df_2026["코드"].astype(str).str.split(".").str[0].str.zfill(8)
    )
    df_2026["sigungu_code"] = df_2026["코드_str"].str[:5]

    # 5. 전체 인구 열('계_') 및 65세 이상 열 선택
    total_cols = [c for c in df_2026.columns if str(c).startswith("계_")]

    senior_cols = []
    for c in total_cols:
        match = re.search(r"\d+", str(c))
        if match:
            if int(match.group()) >= 65:
                senior_cols.append(c)
        elif "100" in str(c):
            senior_cols.append(c)

    # 6. 숫자형 변환
    for c in total_cols:
        df_2026[c] = pd.to_numeric(df_2026[c], errors="coerce").fillna(0)

    # 7. 합계 구하기
    df_2026["전체인구"] = df_2026[total_cols].sum(axis=1)
    df_2026["고령인구"] = df_2026[senior_cols].sum(axis=1)

    # 8. 시군구 그룹화 및 비율 계산
    grouped = (
        df_2026.groupby("sigungu_code")[["전체인구", "고령인구"]]
        .sum()
        .reset_index()
    )

    grouped["고령화율"] = 0.0
    valid_mask = grouped["전체인구"] > 0
    grouped.loc[valid_mask, "고령화율"] = (
        grouped.loc[valid_mask, "고령인구"] / grouped.loc[valid_mask, "전체인구"]
    ) * 100
    grouped["고령화율"] = grouped["고령화율"].round(2)

    # 지자체 이름 부여
    grouped["시군구명"] = grouped["sigungu_code"].map(code_to_info)
    grouped["시군구명"] = grouped["시군구명"].fillna(grouped["sigungu_code"])

    return geojson_data, grouped


try:
    with st.spinner("데이터를 처리하는 중입니다..."):
        geojson_data, df_map = load_data()

    # 9. Plotly 시각화
    fig = px.choropleth_mapbox(
        df_map,
        geojson=geojson_data,
        locations="sigungu_code",
        featureidkey="properties.코드",
        color="고령화율",
        color_continuous_scale="Reds",
        range_color=(df_map["고령화율"].min(), df_map["고령화율"].max()),
        mapbox_style="white-bg",
        center={"lat": 35.9, "lon": 127.8},
        zoom=6,
        hover_name="시군구명",
        hover_data={"sigungu_code": False, "고령화율": ":.2f%"},
        labels={"고령화율": "고령화율(%)"},
    )

    fig.update_layout(
        margin={"r": 0, "t": 30, "l": 0, "b": 0},
        height=700,
        title_text="전국 시군구별 65세 이상 고령화율 (%)",
    )

    st.plotly_chart(fig, use_container_width=True)

    # 주요 데이터 카드
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

except Exception as e:
    st.error(f"오류가 발생했습니다: {e}")
