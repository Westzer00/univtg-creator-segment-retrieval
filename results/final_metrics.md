# Final Metrics

## Representative Individual Query Result

| Metric | Value |
|---|---:|
| nDCG@10 | 0.3398 |
| Recall@10 (tIoU 0.3) | 0.1806 |
| Any-Hit@10 (tIoU 0.3) | 0.6889 |
| Any-Hit@10 (tIoU 0.5) | 0.4889 |
| MR Mean | 0.2306 |
| Query Coverage | 0.7356 |
| Redundancy | 0.0019 |

## Ranking Diagnostic

| Metric | Value |
|---|---:|
| Final Ranking nDCG@10 | 0.3398 |
| Top-50 Oracle nDCG@10 | 0.6319 |
| Ranking Gap | 0.2921 |

## 후속 MR 학습 기반 재정렬 — 별도 실험

**Test Split 172개 영상.** 아래 값은 위의 초기 `Individual nDCG@10 0.3398`과 **실험 버전이 다릅니다.**

| Mode | Global Original nDCG@10 | MR-Learned Re-ranker nDCG@10 | 변화 |
|---|---:|---:|---:|
| Fixed | 0.373164 | **0.454311** | +0.081147 |
| Individual | 0.380922 | **0.430003** | +0.049081 |

- Test `mr_input_used_rate = 0` (MR은 학습·평가 신호로만 사용)
- 전체 Train·Val·Test 합산 성능은 위 Test 결과와 직접 비교할 수 없음
- 팀의 후속 실험 결과. 개인이 해당 재정렬 모델 전체를 단독 개발한 성과로 표시하지 않음
