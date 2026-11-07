# 긴 영상에서 시청자 관심 구간을 찾는 추천·평가 프로젝트

> **UniVTG 기반 영상 구간 검색 · LLM 질의 생성 · 시청자 관심도 평가**  
> 2026.06 ~ 2026.07 · 5인 팀 프로젝트

긴 영상에서 크리에이터가 인트로/하이라이트 후보로 검토할 수 있는 **Top-K 영상 구간**을 추천하기 위해
Video-Language 모델 **UniVTG**, 영상별 **LLM Query**, YouTube **Most Replayed** 데이터를 활용한 프로젝트입니다.

## 핵심 문제와 분석 결과

- 처음 사용한 모델은 학습 데이터에서는 성능이 높았지만 실제 평가에서는 크게 떨어졌습니다.
- 모델을 무작정 바꾸기보다 **검색 문장 → 후보 구간 생성 → 상위 순위 선정**으로 과정을 나눠 원인을 확인했습니다.
- 최종 평가에서 Top-50 후보에는 관련 구간이 있었지만 **Top-10으로 정렬하는 단계에서 성능 손실**이 컸습니다.
- **후보 생성보다 상위 순위 선정 단계가 주요 병목**임을 확인하고 후속 개선 대상을 좁혔습니다.

## 1. 문제 재정의

초기 DSNet은 Train Frame F1 **59.1%**였지만 Validation **4.2%**, Test **4.3%**로 일반화에 실패했습니다.
그래서 문제를 다음처럼 분해했습니다.

```text
Query
  ↓
Candidate Generation
  ↓
Ranking
  ↓
Top-K Candidate Segments
```

## 2. 영상별 검색 문장 설계

### 공통 검색 문장
카테고리별 공통 Query.

### 영상별 검색 문장
영상 제목과 Whisper 자막을 활용해 LLM으로 생성한 영상별 Query.

```text
Video Title + Whisper Transcript
              ↓
             LLM
              ↓
      Individual Queries
              ↓
            UniVTG
```

Most Replayed, 실제 Intro Label, Test 평가 결과는 Query 생성 입력에 사용하지 않았습니다.

## 3. 전체 처리 흐름

```text
Video
  ├─ Visual Feature
  └─ Whisper Transcript
          ↓
   LLM Query Generation
          ↓
 Fixed / Individual Query
          ↓
        UniVTG
 saliency + foreground
          ↓
   Top-50 Candidates
          ↓
        Ranking
          ↓
  Top-10 Suggestions
          ↓
 Most Replayed Evaluation
```

## 4. 담당 역할

- 관련 논문·선행연구 조사
- **LLM 기반 Individual Query 생성**
- UniVTG Retrieval Pipeline 구현
- Retrieval / Ranking 평가 코드 구현
- 실험 결과 분석
- 팀 데모 화면 구성 참여

## 5. 후보 구간 검색

UniVTG의 **Saliency Score**와 **Foreground Score**를 활용해 시간 구간별 관련도를 계산하고,
여러 Query 결과를 결합해 Top-50 Candidate Pool을 구성한 뒤 Top-10 후보를 Ranking했습니다.

실제 코드:
- [`notebooks/01_univtg_pipeline.ipynb`](notebooks/01_univtg_pipeline.ipynb)
- [`notebooks/02_top50_retrieval.ipynb`](notebooks/02_top50_retrieval.ipynb)
- [`src/univtg_csv_adapter.py`](src/univtg_csv_adapter.py)

## 6. 반복 재생 데이터는 평가에만 사용

Most Replayed Heatmap은 Candidate 생성 입력으로 사용하지 않고,
추천 구간의 품질을 평가하는 **독립적인 시청자 관심도 기준**으로 분리했습니다.

```text
Video + Query → UniVTG → Predicted Segments
                              │
                              │ compare
                              ▼
                     Most Replayed Heatmap
                       (Evaluation Only)
```

## 7. 평가 기준

| Metric | 의미 |
|---|---|
| **nDCG@10** | 관심도가 높은 구간이 상위 Rank에 위치하는 정도 |
| **Recall@10** | 관심구간 회수 정도 |
| **Any-Hit@10** | Top-10 안에 의미 있는 관심구간이 하나라도 존재하는 비율 |
| Query Coverage | 여러 Query 의도가 후보에 반영되는 정도 |
| Redundancy | 추천구간 간 중복 정도 |

평가 코드:
[`notebooks/03_most_replayed_evaluation.ipynb`](notebooks/03_most_replayed_evaluation.ipynb)

## 8. 대표 평가 결과

| Metric | Result |
|---|---:|
| **nDCG@10** | **0.3398** |
| Recall@10 (tIoU 0.3) | 0.1806 |
| **Any-Hit@10 (tIoU 0.3)** | **68.89%** |
| Any-Hit@10 (tIoU 0.5) | 48.89% |
| Query Coverage | 0.7356 |
| Redundancy | 0.0019 |

약 **68.9%의 영상에서 Top-10 후보 안에 의미 있는 Most Replayed 구간이 최소 하나 포함**되었습니다.

## 9. 확인한 병목

Top-50 Candidate Pool을 이상적으로 재정렬한 Oracle과 비교했습니다.

| Individual Mode | nDCG@10 |
|---|---:|
| Final Ranking | 0.3398 |
| **Top-50 Oracle** | **0.6319** |
| Ranking Gap | **0.2921** |

즉 좋은 후보는 Top-50 안에 존재하지만 최종 Top-10 Ranking에서 충분히 위로 끌어올리지 못했습니다.
후속 개선 방향을 Candidate 확대보다 **Ranking Feature 개선**으로 좁혔습니다.

## 10. 후속 재정렬 실험 — Test 172개 영상

초기 프로젝트에서는 Most Replayed를 **검색 단계의 입력이 아닌 평가 지표**로 사용했습니다. 이후 팀의 후속 실험에서는 Train·Validation의 Most Replayed 값을 학습 신호로 활용해 **ExtraTrees 기반 후보 구간 재정렬 모델**을 추가했습니다.

| 방식 | 이전 정렬 nDCG@10 | 학습 기반 재정렬 nDCG@10 |
|---|---:|---:|
| Fixed 검색 문장 | 0.3732 | **0.4543** |
| Individual 검색 문장 | 0.3809 | **0.4300** |

*Test 172개 영상 기준. Test 영상의 Most Replayed는 예측 입력에 미사용(`mr_input_used_rate = 0`). 1,142개 전체 영상의 집계 수치에는 Train·Val 정보가 섞여 있어 Test 성능과 구분.*

[후속 실험 방법·제약](docs/followup-reranking.md) · [평가 지표](results/final_metrics.md)

## 실행과 재현 범위

CSV 입력 검증과 실행 설정은 **합성 샘플만으로 테스트 가능**합니다.

```bash
python -m pip install pandas pytest
python -m examples.run_csv_demo
python -m pytest -q tests/
```

실제 UniVTG 추론 노트북은 별도 `univtg_preview_v2.zip` 패키지와 공식 모델 가중치, 원본 영상·시간 데이터에 의존합니다. **해당 패키지는 이 저장소에 없으므로 전체 영상 실험은 즉시 재현할 수 없습니다.** CSV 검증 예제와 전체 실험은 별개입니다.

## 11. 파일 구조

```text
.
├── README.md
├── CONTRIBUTION.md
├── requirements.txt
├── notebooks/
│   ├── 01_univtg_pipeline.ipynb
│   ├── 02_top50_retrieval.ipynb
│   └── 03_most_replayed_evaluation.ipynb
├── src/
│   └── univtg_csv_adapter.py
├── examples/
│   └── run_csv_demo.py
├── tests/
│   └── test_csv_inputs.py
├── .github/workflows/
│   └── csv-tests.yml
├── data/
│   ├── README.md
│   ├── sample_category_queries.csv
│   ├── sample_timings.csv
│   └── sample_queries.csv
├── docs/
│   ├── methodology.md
│   └── followup-reranking.md
├── results/
│   └── final_metrics.md
└── third_party/
    └── UniVTG.md
```

## 12. 사용한 공개 모델

공개 영상 구간 검색 모델 **UniVTG** 사용.

Original Repository: https://github.com/showlab/UniVTG

프로젝트에서 개발한 **입력 변환·후보 검색·순위 선정·평가 코드**를 정리했습니다. UniVTG 원본은 공식 저장소를 참조합니다.

## 13. 데이터·실험 환경

YouTube 영상·자막·Most Replayed 원본 대신 검색 문장 샘플을 포함했습니다. 전체 실험 실행에는 원본 데이터와 UniVTG 모델 가중치가 별도로 필요합니다.

[`data/sample_queries.csv`](data/sample_queries.csv)
