# UniVTG 실제 추론 재현성 점검 (2026-11-08)

## 확인된 실행 구조
Google Drive의 `univtg_preview` 원본은 파이프라인 오케스트레이션(`pipeline.py`), 모델·CLIP 추론 래퍼(`runtime.py`), 미디어·후처리·워크스페이스 모듈로 나뉩니다. GitHub의 `notebooks/01_univtg_pipeline.ipynb`는 `univtg_preview_v2.zip` 및 모델 가중치와 원본 영상·데이터가 없으면 전체 실험을 실행할 수 없습니다.

## 이번 추가 검증
`tests/test_adapter_edge_cases.py`에서 실제 `src/univtg_csv_adapter.py`를 합성 CSV/비디오 placeholder 및 monkeypatch로 검증합니다.
- fixed+individual Query 결합, Query 누락·잘못된 유형과 미존재 영상 ID
- 인트로 시간 순서·영상 종료시간 보정·설정 예외
- ffmpeg 미실행 상태의 컷 명령 생성·카테고리별 Batch Plan

## 아직 수행하지 않은 검증
- `univtg_preview` 패키지의 실제 모델·영상·CLIP 특징 추론
- 공개 가중치와 원본 미디어를 이용한 재실험 결과 대조
- 영상 수준 Top-50/Top-10, nDCG 수치의 원본 재계산

원본 패키지는 팀 작업·외부 UniVTG 코드와 라이선스/공개 승인을 검토한 뒤 분리해야 합니다. 이를 공개 저장소에 허가 없이 복제해 올리지 않습니다. 모델 실행을 제외한 CSV 어댑터 테스트 성공을 전체 모델 실행 성공이라고 표현하지 않습니다.
