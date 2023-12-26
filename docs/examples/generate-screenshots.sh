#!/usr/bin/env bash

set -euxo pipefail

THIS_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )

echo ${THIS_DIR}/*.py | xargs --verbose --max-args 1 --max-procs 4 python
