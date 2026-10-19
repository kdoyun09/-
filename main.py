import json
import re
import requests
import pandas as pd
import plotly.express as px
import streamlit as st

# 페이지 기본 설정
st.set_page_config(page_title="전국 고령화 단계구분도", layout="wide")

st.title("2026년 전국 시군구별 고령화율 단계구분도")
st.caption("전국 읍·면·동 인구 데이터를 시군구(5자리 코드) 단위로 집계하여 65세 이상 고령화율(%)을 시각화합니다.")


@st.cache_data
def load_data():
    # 1. 시군구 GeoJSON 불러오기
    geojson_url = "https://raw.githubusercontent.com/first2022-cyber/contents//main/sigungu_kr.geojson"
    res = requests.get(geojson_url)
    geojson_data = res.json()

    # 2. 인구 CSV (ZIP) 불러오기
    csv_url = "https://raw.githubusercontent.com/first2022-cyber/contents//main/population_ts_yearly_gender.zip"
    df = pd.read_csv(csv_url)

    # 3. 2026년 데이터만 필터링
    df_2026 = df[df["연도"] == 2026].copy()

    # 4. 코드를 5자리 문자열로 변환 (시군구 단위)
    df_2026["코드"] = df_2026["코드"].astype(str).str.zfill(8)
    df_2026["sigungu_code"] = df_2026["코드"].str[:5]

    # 5. 전체 인구 열 및 65세 이상 인구 열 추출
    # '계_'로 시작하는 모든 열
    total_cols = [c for c in df_2026.columns if c.startswith("계_")]

    # '계_65세' ~ '계_100세 이상' 열 추출
    senior_cols = []
    for c in total_cols:
        # 숫자 추출
        match = re.search(r"\d+", c)
        if match:
            age = int(match.group())
            if age >= 65:
                senior_cols.append(c)
        elif "100세 이상" in c:
            senior_cols.append(c)

    # 6. 각 행별 전체 인구 및 고령 인구 합계 계산
    df_2026["전체인구"] = df_2026[total_cols].sum(axis=1)
    df_2026["고령인구"] = df_2026[senior_cols].sum(axis=1)

    # 7. 시군구별 그룹화 및 고령화율 계산
    grouped = (
        df_2026.groupby("sigungu_code")[["전체인구", "고령인구"]].sum().reset_index()
    )
    grouped["고령화율"] = (grouped["고령인구"] / grouped["전체인구"]) * 100
    grouped["고령화율"] = grouped["고령화율"].round(2)

    # GeoJSON의 '시군구' 및 '시도' 이름을 코드와 매핑
    code_to_info = {}
    for feat in geojson_data["features"]:
        props = feat["properties"]
        code = str(props["코드"])
        sigungu_name = f"{props.get('시도', '')} {props.get('시군구', '')}".strip()
        code_to_info[code] = sigungu_name

    grouped["시군구명"] = grouped["sigungu_code"].map(code_to_info)

    return geojson_data, grouped


with st.spinner("데이터를 로드 중입니다..."):
    geojson_data, df_map = load_data()

# 8. Plotly 단계구분도(Choropleth) 생성
fig = px.choropleth_mapbox(
    df_map,
    geojson=geojson_data,
    locations="sigungu_code",
    featureidkey="properties.코드",
    color="고령화율",
    color_continuous_scale="Reds",
    range_color=(0, df_map["고령화율"].max()),
    mapbox_style="white-bg",
    center={"lat": 36.3, "lon": 127.8},
    zoom=6,
    hover_name="시군구명",
    hover_data={"sigungu_code": False, "고령화율": ":.2f%"},
    labels={"고령화율": "고령화율(%)"},
)

fig.update_layout(
    margin={"r": 0, "t": 30, "l": 0, "b": 0},
    height=750,
    title_text="전국 시군구별 65세 이상 고령화율 (%)",
)

# 스트림릿에 그래프 출력
st.plotly_chart(fig, use_container_width=True)

# 핵심 통계 요약
col1, col2, col3 = st.columns(3)
col1.metric("최고 고령화율 지역", f"{df_map.loc[df_map['고령화율'].idxmax(), '시군구명']}", f"{df_map['고령화율'].max()}%")
col2.metric("최저 고령화율 지역", f"{df_map.loc[df_map['고령화율'].idxmin(), '시군구명']}", f"{df_map['고령화율'].min()}%")
col3.metric("시군구 평균 고령화율", f"{df_map['고령화율'].mean():.2f}%")
