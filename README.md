# grippers-host-mac — 새 Host(vla_robot/host) macOS 대응

팀 저장소 [grippers-intel/grippers](https://github.com/grippers-intel/grippers) main `dd9e319` 의 Host 를
가져와 macOS 에서도 돌게 고친 브랜치다. 코드는 Windows 와 한 벌이라 Windows 에서도 그대로 돈다.

- `vla_robot/host/` — Host(탑뷰 측위 · 검출 · 미션 FSM · 시연 UI). 설치·실행은 [vla_robot/host/README.md](vla_robot/host/README.md)
- `vla_robot/ros2_ws/src/vla_common/` — Host ↔ Pi UDP 규약(`protocol.py`). 팀 저장소와 같은 경로에 두어
  `host_config.py` 의 경로 처리와 `requirements.txt` 의 `-e ../ros2_ws/src/vla_common` 이 그대로 돈다.

이 브랜치의 첫 커밋은 원본을 수정 없이 복사한 것이고, 맥 대응은 그 위의 커밋에만 있다 —
`git diff <첫 커밋> HEAD` 로 바꾼 곳만 볼 수 있다. 예전 Host(run_mission.py 계열)는 main 브랜치에 있다.
