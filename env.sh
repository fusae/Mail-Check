#!/bin/bash

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

resolve_env_prefix() {
    if [ -n "${ENV_PREFIX:-}" ] && [ -d "${ENV_PREFIX}" ]; then
        echo "${ENV_PREFIX}"
        return 0
    fi

    local candidates=(
        "${PROJECT_ROOT}/venv-ubuntu"
        "${PROJECT_ROOT}/venv"
    )
    local candidate
    for candidate in "${candidates[@]}"; do
        if [ -d "${candidate}" ]; then
            echo "${candidate}"
            return 0
        fi
    done

    return 1
}

ENV_PREFIX="$(resolve_env_prefix)"
ENV_BIN="${ENV_PREFIX}/bin"
PYTHON_BIN="${PYTHON_BIN:-${ENV_BIN}/python}"
PIP_BIN="${PIP_BIN:-${ENV_BIN}/pip}"
NODE_BIN="${NODE_BIN:-${ENV_BIN}/node}"

ensure_runtime() {
    if [ -z "${ENV_PREFIX}" ] || [ ! -d "${ENV_PREFIX}" ]; then
        echo "错误: 未找到运行环境目录，请检查 venv 或 venv-ubuntu"
        return 1
    fi
    if [ ! -x "${PYTHON_BIN}" ]; then
        echo "错误: 未找到 Python: ${PYTHON_BIN}"
        return 1
    fi
    return 0
}

run_in_env() {
    ensure_runtime || return 1
    PATH="${ENV_BIN}:$PATH" \
    LD_LIBRARY_PATH="${ENV_PREFIX}/lib:${LD_LIBRARY_PATH:-}" \
    PLAYWRIGHT_NODEJS_PATH="${NODE_BIN}" \
    "$@"
}
