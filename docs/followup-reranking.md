# 후속 MR 학습 기반 재정렬 실험

## 실험 목적

초기 UniVTG 기반 검색은 영상별 Top-50 후보를 구성했지만, 상위 Top-10으로 정렬하는 단계에 개선 여지가 남았습니다. 팀 후속 실험에서는 Most Replayed 관심도를 지도학습 목표값으로 활용하여 후보를 다시 정렬하는 경량 모델을 추가했습니다.

## 구현 과정

1. 영상별 UniVTG Top-50 후보 생성 (Fixed / Individual 검색 문장)
2. Train·Validation 영상의 Most Replayed heatmap과 후보 구간의 겹침으로 학습용 relevance 구성
3. 후보 점수 등 특징을 이용한 **ExtraTreesRegressor** 학습
4. Test에서 **모델의 예측 점수만으로** 상위 후보 재정렬
5. Test Most Replayed는 성능 평가에만 사용

원본 실행 기록: 팀 Drive의 `eval_final.ipynb` 및 `01_v10_performance_summary.csv`. 원본 영상·heatmap·실험용 대형 CSV는 공개 저장소에 포함하지 않았습니다.

## Test 전용 평가

| 방식 | 기준 nDCG@10 | 후속 재정렬 nDCG@10 | 상승 |
|---|---:|---:|---:|
| Fixed | 0.373164 | 0.454311 | 0.081147 |
| Individual | 0.380922 | 0.430003 | 0.049081 |

총 Test 172개 영상, Test Most Replayed 입력 사용 비율 0.

## 해석상 주의점

- GitHub의 [초기 평가 노트북](../notebooks/03_most_replayed_evaluation.ipynb)은 후속 모델과 **다른 버전의 실험**입니다.
- Drive의 `eval_final.ipynb`에는 후속 학습 과정이 있으나, 모델 가중치·원본 영상·heatmap이 연결되지 않은 공개 저장소에서 전체 재학습을 재현한 것은 아닙니다.
- Train·Val에서 실제 MR가 후보 점수 계산 과정에 사용된 기록이 있어 전체 데이터 성능 수치는 Test 성능으로 사용할 수 없습니다.
- 기능 단위 담당 역할과 팀 전체 실험 결과를 구분해야 합니다.
