# 개인 기여 범위

- 프로젝트 관련 논문·선행연구 조사
- 영상 제목 + Whisper 자막 기반 LLM Individual Query 구성
- Fixed / Individual Query 비교 구조
- UniVTG Retrieval Pipeline 구성·실험 참여(실제 추론용 `univtg_preview` 패키지는 공개 범위 밖)
- Top-50 Candidate 생성 및 Top-K Ranking
- Most Replayed 기반 Evaluation 코드 및 재정렬 병목 분석
- 실험 결과 분석 및 Demo Site 구축

**5인 팀 프로젝트.** 영상 수집·크롤링과 원천 데이터 구축은 팀 내 분담 작업입니다. ExtraTrees 기반 후속 재정렬은 팀 실험 결과이며 개인 단독 모델 개발로 표시하지 않습니다.

**공개된 개인 작업 증거:** [CSV 어댑터](src/univtg_csv_adapter.py), [검색·평가 노트북](notebooks/), [합성 테스트](tests/). 실제 영상 추론의 외부 패키지와 원본 데이터가 없어 모델 실행은 공개 저장소만으로 검증되지 않습니다.
