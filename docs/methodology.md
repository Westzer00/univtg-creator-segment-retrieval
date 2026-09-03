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
UniVTG Saliency / Foreground Score를 이용해 Top-50 후보 생성.

## Evaluation
Most Replayed를 독립 평가 신호로 사용.
주요 지표는 nDCG@10, Recall@10, Any-Hit@10, Query Coverage, Redundancy.

## Bottleneck
Individual Final nDCG@10 = 0.3398  
Top-50 Oracle nDCG@10 = 0.6319  
Gap = 0.2921

따라서 Candidate Pool보다 Ranking 개선 여지가 큰 것으로 해석했습니다.
