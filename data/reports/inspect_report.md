# 원본 데이터 검사 보고서

## regional_usage — `데이터_지역별스포츠강좌이용권활용정보.csv`
- 행 460 · 컬럼 11 · SHA-256 `09189a606e513ffb…`
- 결측 상위: CRRSPND_FLAG_TRGET_NMPR_CO 0%, BASE_YEAR 0%, CTPRVN_CD 0%, CTPRVN_NM 0%, SIGNGU_CD 0%, SIGNGU_NM 0%, SIGNGU_ACCTO_POPLTN_CO 0%, SIGNGU_ACCTO_FCLTY_CO 0%

## voucher_facilities — `데이터_스포츠강좌이용권시설.csv`
- 행 28,892 · 컬럼 18 · SHA-256 `d16d39029f353986…`
- 결측 상위: COURSE_ITEM_NM 100%, COURSE_NM 100%, RPRSNTV_TEL_NO 58%, FCLTY_COURSE_SDIV_NM 32%, FCLTY_X_CRDNT_VALUE 1%, FCLTY_Y_CRDNT_VALUE 1%, DETAIL_ADDR 1%, FCLTY_DECSN_DE 0%

## voucher_courses — `데이터_스포츠강좌이용권이용시설강좌.csv`
- 행 66,808 · 컬럼 12 · SHA-256 `9f4f0055c3135795…`
- 결측 상위: SUPLI_SLE_AT 100%, COURSE_DETAIL_CN 39%, ATNLC_PRC 3%, LCTRR_NM 0%, WKDAY_NM 0%, ITEM_CD 0%, ITEM_NM 0%, COURSE_NM 0%
- timeParseRate: 1.0
- weekdayParseRate: 0.9956
- descriptionLength: {'0': 26254, '100+': 16729, '20-99': 18586, '1-19': 5239}
- uniqueItemCourseName: 22297

## voucher_usage — `데이터_스포츠강좌이용권.csv`
- 행 517,101 · 컬럼 20 · SHA-256 `13f5528b9f6e5c8c…`
- 결측 상위: TEL_NO 31%, FCLTY_DETAIL_ADDR 1%, COURSE_BEGIN_DE 0%, COURSE_END_DE 0%, BSNS_NO 0%, FCLTY_NM 0%, ITEM_CD 0%, ITEM_NM 0%

## all_facilities — `데이터_전국체육시설현황.csv`
- 행 152,968 · 컬럼 58 · SHA-256 `c27a428f40295298…`
- 결측 상위: FCLTY_MANAGE_LI_CD 100%, FCLTY_MANAGE_LI_NM 100%, LVLH_OPN_AT 99%, SSS_DE 99%, UTILIIZA_GRP_NM 99%, LVLH_GMNSM_NM 99%, ADTM_CO 98%, ACMD_NMPR_CO 98%

## public_facilities — `데이터_전국공공체육시설.csv`
- 행 44,612 · 컬럼 33 · SHA-256 `f1ec5eca249f7876…`
- 결측 상위: ROAD_NM_LI_CD 100%, ROAD_NM_LI_NM 100%, ADTM_CO 96%, ACMD_NMPR_CO 95%, FCLTY_HMPG_URL 95%, FCLTY_AR_CO 76%, RSPNSBLTY_TEL_NO 72%, RSPNSBLTY_DEPT_NM 71%

## open_schools — `데이터_개방학교체육시설.csv`
- 행 1,206 · 컬럼 13 · SHA-256 `c1cce5adedc98ae4…`
- 결측 상위: OPER_TIME_CN 2%, ALSFC_SIGNGU_NM 1%, BASE_YEAR 0%, ALSFC_CTPRVN_NM 0%, SCHUL_TY_NM 0%, SCHUL_NM 0%, OPN_PD 0%, ARBY_COT_CO_VALUE 0%

## safety — `데이터_체육시설안전점검정보.csv`
- 행 192,314 · 컬럼 30 · SHA-256 `146020d09012a597…`
- 결측 상위: FCLTY_NCM_NM 97%, OPER_CLSBIZ_DE 75%, FCLTY_DETAIL_ADDR 69%, FCLTY_ROAD_NM_DETAIL_ADDR 68%, FCLTY_TEL_NO 49%, SAFECHK_DE 36%, SAFECHK_OTHBC_DE 36%, FCLTY_TOTAR_CO 17%

## transit_voucher — `데이터_스포츠강좌이용권시설인접대중교통정보.csv`
- 행 1,004,165 · 컬럼 18 · SHA-256 `bbc4ea6a9fb17b4b…`
- 결측 상위: SVCH_FCLTY_DETAIL_ADDR 0%, WLKG_DSTNC_VALUE 0%, WLKG_MVMN_TIME 0%, SVCH_FCLTY_NM 0%, SVCH_FCLTY_SDIV_NM 0%, SVCH_FCLTY_ITEM_NM 0%, SVCH_FCLTY_CTPRVN_CD 0%, SVCH_FCLTY_CTPRVN_NM 0%

## transit_public — `데이터_체육시설인접대중교통정보.csv`
- 행 1,639,279 · 컬럼 17 · SHA-256 `afe951e47cd23c04…`
- 결측 상위: WLKG_DSTNC_VALUE 53%, WLKG_MVMN_TIME 53%, ALSFC_ADDR 12%, ALSFC_NM 0%, ALSFC_SDIV_NM 0%, ALSFC_TY_NM 0%, ALSFC_CTPRVN_CD 0%, ALSFC_CTPRVN_NM 0%

## 조인 검사
```json
{
  "voucher_vs_all_facilities": {
    "voucherRows": 28892,
    "voucherUniqueFacilities": 27973,
    "allRows": 152968,
    "exactNameAddr": 6803,
    "nameOnlySameSigungu": 5489,
    "telOnlySameSigungu": 1670,
    "exactMatchedStateDist": {
      "정상운영": 6127,
      "폐업": 669,
      "": 7
    },
    "voucherCoverageByExact": 0.2432
  },
  "usage_vs_courses_vs_facilities": {
    "usageRows": 517101,
    "usageYears": {
      "2022": 18391,
      "2025": 200505,
      "2026": 123406,
      "2021": 11828,
      "2024": 124135,
      "2023": 30763,
      "2020": 8073
    },
    "usageUniqueFacilities": 24802,
    "usageFacilitiesFoundInVoucherFacilities": 20539,
    "usageUniqueCourseNo": 58955,
    "usageCoursesMatchedToCourseTable(item+name)": 53523,
    "courseTableRows": 66808
  },
  "region_codes": {
    "regionalUsageSigungu": 230,
    "voucherFacilitySigungu": 276,
    "voucherSigunguNotInRegional": [
      "12110",
      "12130",
      "12150",
      "12170",
      "12190",
      "12210",
      "12240",
      "12270",
      "12300",
      "12330",
      "12710",
      "12720",
      "12740",
      "12750",
      "12760",
      "12770",
      "12780",
      "12790",
      "12800",
      "12810"
    ],
    "regionalSigunguWithoutVoucherFacility": 2
  }
}
```