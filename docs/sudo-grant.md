# One-time setup: network-shaping permission (blocks the C2 measurements)

The C2 network condition (100 ms RTT / 1% loss) is applied with macOS dummynet
(`dnctl` + `pfctl`), which needs root. Granting passwordless sudo for exactly
these two binaries — nothing else — lets the harness arm and clear phases
unattended (overnight windows included).

Run this once (it will ask for your password):

```sh
sudo tee /etc/sudoers.d/rtveval-netshape <<'EOF'
joseph ALL=(root) NOPASSWD: /usr/sbin/dnctl, /sbin/pfctl
EOF
sudo chmod 440 /etc/sudoers.d/rtveval-netshape
```

Verify (should print a dummynet config header, no password prompt):

```sh
sudo -n dnctl list
```

To revoke after the study:

```sh
sudo rm /etc/sudoers.d/rtveval-netshape
```

Scope note: this grants root only for the traffic shaper (`dnctl`) and packet
filter control (`pfctl`) — the two commands `rtveval/orchestrator/netshape.py`
issues. The harness always applies shaping inside the `rtveval` pf anchor and
clears it on teardown.
