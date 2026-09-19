#!/usr/bin/env bash

set -euo pipefail

THIS_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

echo ${THIS_DIR}/*.py | xargs -n 1 -P 8 python
