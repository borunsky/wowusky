# systemd user timer for daily update checks

These units run `wowusky update --all-profiles --quiet` once a day as your
user (no root required).

## Install

```bash
mkdir -p ~/.config/systemd/user
cp wowusky-update.service wowusky-update.timer ~/.config/systemd/user/

systemctl --user daemon-reload
systemctl --user enable --now wowusky-update.timer
```

## Check status

```bash
systemctl --user list-timers wowusky-update.timer
systemctl --user status wowusky-update.service
journalctl --user -u wowusky-update.service
```

## Run once now

```bash
systemctl --user start wowusky-update.service
```

## Disable

```bash
systemctl --user disable --now wowusky-update.timer
```

## Notes

- The service calls `~/.local/bin/wowusky` (the launcher created by
  `install.sh`). If wowusky is installed elsewhere, edit `ExecStart` in
  `wowusky-update.service` — a commented `python -m wowusky` fallback is
  included.
- wowusky takes an automatic full backup before updating each profile.
  To skip that in the timer, add `--no-backup` to the `ExecStart` line.
