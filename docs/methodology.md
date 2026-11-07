# Methodology

## Baseline Failure
DSNet: Train Frame F1 59.1% → Validation 4.2% → Test 4.3%.

## Problem Decomposition
`Query → Candidate Generation → Ranking → Evaluation`

## Query
- Fixed: 카테고리 공통
- Individual: 제목 + Whisper Transcript 기반 LLM 생성
- Most Replayed / Intro Label / Test 결과는 Query 입력에 사용하지 않음

## Retrieval
UniVTG Saliency / Foreground Score를 이용해 Top-50 후보 생성. 실험 당시 원본 파이프라인은 별도 `univtg_preview` 모듈을 사용했습니다. 현재 공개 저장소에서 직접 실행·검증할 수 있는 부분은 CSV 어댑터·실험 설정과 합성 테스트이며, 영상 모델 추론의 재실행은 아닙니다.

## Evaluation
초기 검색·정렬 실험에서는 Most Replayed를 독립 평가 신호로만 사용했습니다. 이후 후속 실험에서는 Train·Validation의 Most Replayed를 재정렬 모델의 지도학습 목표값으로 활용했습니다. Test에서는 해당 값을 예측 입력으로 사용하지 않았습니다.
주요 지표는 nDCG@10, Recall@10, Any-Hit@10, Query Coverage, Redundancy.

## Bottleneck
Individual Final nDCG@10 = 0.3398  
Top-50 Oracle nDCG@10 = 0.6319  
Gap = 0.2921

따라서 Candidate Pool보다 Ranking 개선 여지가 큰 것으로 해석했습니다.

## 후속 학습 기반 재정렬

[후속 실험과 Test 결과](followup-reranking.md)
