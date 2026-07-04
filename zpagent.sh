#!/bin/bash
#
# ZpAgent 启动/停止/重启脚本
# 用法: ./zpagent.sh {start|stop|restart|status} [backend|frontend|all]
#

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/back"
FRONTEND_DIR="$PROJECT_DIR/front"
LOG_DIR="$PROJECT_DIR/log"
VENV_PYTHON="$BACKEND_DIR/venv/bin/python"
BACKEND_PID_FILE="/tmp/zpagent_backend.pid"
FRONTEND_PID_FILE="/tmp/zpagent_frontend.pid"

# =============================================
# 颜色输出
# =============================================
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

info()  { echo -e "${CYAN}[INFO]${NC} $1"; }
ok()    { echo -e "${GREEN}[OK]${NC} $1"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()   { echo -e "${RED}[ERR]${NC} $1"; }

# =============================================
# 通用进程检测工具函数
# =============================================

# 获取指定端口上的进程 PID（macOS compatible）
get_pid_by_port() {
    local port=$1
    if command -v lsof >/dev/null 2>&1; then
        lsof -ti TCP:$port 2>/dev/null | head -1
    fi
}

# 检测后端是否运行（PID 文件优先，端口检测兜底）
is_backend_running() {
    if [ -f "$BACKEND_PID_FILE" ] && kill -0 "$(cat "$BACKEND_PID_FILE")" 2>/dev/null; then
        return 0
    fi
    # 兜底：通过端口检测
    if lsof -ti TCP:8000 >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

# 检测前端是否运行（PID 文件优先，端口检测兜底）
is_frontend_running() {
    if [ -f "$FRONTEND_PID_FILE" ] && kill -0 "$(cat "$FRONTEND_PID_FILE")" 2>/dev/null; then
        return 0
    fi
    # 兜底：通过端口检测
    if lsof -ti TCP:5173 >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

# =============================================
# 后端操作
# =============================================

backend_start() {
    info "启动后端服务..."
    if is_backend_running; then
        warn "后端服务已在运行 (端口: 8000)"
        return 0
    fi

    if [ ! -f "$VENV_PYTHON" ]; then
        err "未找到 Python 虚拟环境: $VENV_PYTHON"
        err "请先执行: cd back && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
        return 1
    fi

    # 检查依赖是否已安装
    if ! "$VENV_PYTHON" -c "import fastapi" 2>/dev/null; then
        warn "检测到依赖未安装，正在安装..."
        "$VENV_PYTHON" -m pip install -r "$BACKEND_DIR/requirements.txt" -q
    fi

    cd "$BACKEND_DIR"
    mkdir -p "$LOG_DIR"
    nohup "$VENV_PYTHON" -m uvicorn main:app \
        --host 0.0.0.0 \
        --port 8000 \
        --reload \
        > "$LOG_DIR/backend.log" 2>&1 &
    BACKEND_PID=$!
    echo $BACKEND_PID > "$BACKEND_PID_FILE"

    # 等待服务就绪
    sleep 2
    if kill -0 $BACKEND_PID 2>/dev/null; then
        ok "后端服务已启动 (PID: $BACKEND_PID)"
        info "API 文档: http://localhost:8000/docs"
    else
        err "后端服务启动失败，请检查日志: $LOG_DIR/backend.log"
        rm -f "$BACKEND_PID_FILE"
        return 1
    fi
}

backend_stop() {
    info "停止后端服务..."

    # 先尝试通过 PID 文件停止
    if [ -f "$BACKEND_PID_FILE" ]; then
        BACKEND_PID=$(cat "$BACKEND_PID_FILE")
        if kill -0 "$BACKEND_PID" 2>/dev/null; then
            kill "$BACKEND_PID" 2>/dev/null
            for i in $(seq 1 5); do
                if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
                    break
                fi
                sleep 1
            done
            if kill -0 "$BACKEND_PID" 2>/dev/null; then
                kill -9 "$BACKEND_PID" 2>/dev/null
            fi
            ok "后端服务已停止 (PID: $BACKEND_PID)"
        else
            warn "后端进程已不存在"
        fi
        rm -f "$BACKEND_PID_FILE"
        return 0
    fi

    # 兜底：通过进程名停止
    if pkill -f "uvicorn main:app" 2>/dev/null; then
        ok "后端服务已停止 (通过进程名)"
    else
        warn "未发现运行中的后端进程"
    fi
}

backend_status() {
    if [ -f "$BACKEND_PID_FILE" ] && kill -0 "$(cat "$BACKEND_PID_FILE")" 2>/dev/null; then
        local pid=$(cat "$BACKEND_PID_FILE")
        local uptime=$(ps -o etime= -p "$pid" 2>/dev/null | xargs)
        echo -e "  后端: ${GREEN}运行中${NC} (PID: $pid, 已运行: $uptime)"
        echo -e "        端口: ${CYAN}8000${NC}"
        echo -e "        日志: ${CYAN}$LOG_DIR/backend.log${NC}"
        return 0
    else
        # 端口检测兜底
        local port_pid=$(get_pid_by_port 8000)
        if [ -n "$port_pid" ]; then
            local uptime=$(ps -o etime= -p "$port_pid" 2>/dev/null | xargs)
            echo -e "  后端: ${GREEN}运行中${NC} (PID: $port_pid, 已运行: $uptime, ${YELLOW}非脚本管理${NC})"
            echo -e "        端口: ${CYAN}8000${NC}"
            return 0
        fi
        echo -e "  后端: ${RED}未运行${NC}"
        return 1
    fi
}

backend_health() {
    if is_backend_running; then
        if curl -s --max-time 2 http://localhost:8000/api/health >/dev/null 2>&1; then
            echo -e "  API 健康: ${GREEN}OK${NC} (http://localhost:8000/api/health)"
        else
            echo -e "  API 健康: ${YELLOW}进程在运行但 API 未响应${NC}"
        fi
    else
        echo -e "  API 健康: ${RED}未运行${NC}"
    fi
}

# =============================================
# 前端操作
# =============================================

frontend_start() {
    info "启动前端服务..."
    if is_frontend_running; then
        warn "前端服务已在运行 (端口: 5173)"
        return 0
    fi

    if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
        info "检测到 node_modules 不存在，正在安装依赖..."
        cd "$FRONTEND_DIR" && npm install
    fi

    cd "$FRONTEND_DIR"
    mkdir -p "$LOG_DIR"
    nohup npx vite --host > "$LOG_DIR/frontend.log" 2>&1 &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > "$FRONTEND_PID_FILE"

    # 等待服务就绪
    sleep 3
    if kill -0 $FRONTEND_PID 2>/dev/null; then
        ok "前端服务已启动 (PID: $FRONTEND_PID)"
        info "前端地址: http://localhost:5173"
    else
        err "前端服务启动失败，请检查日志: $LOG_DIR/frontend.log"
        rm -f "$FRONTEND_PID_FILE"
        return 1
    fi
}

frontend_stop() {
    info "停止前端服务..."

    if [ -f "$FRONTEND_PID_FILE" ]; then
        FRONTEND_PID=$(cat "$FRONTEND_PID_FILE")
        if kill -0 "$FRONTEND_PID" 2>/dev/null; then
            kill "$FRONTEND_PID" 2>/dev/null
            for i in $(seq 1 5); do
                if ! kill -0 "$FRONTEND_PID" 2>/dev/null; then
                    break
                fi
                sleep 1
            done
            if kill -0 "$FRONTEND_PID" 2>/dev/null; then
                kill -9 "$FRONTEND_PID" 2>/dev/null
            fi
            ok "前端服务已停止 (PID: $FRONTEND_PID)"
        else
            warn "前端进程已不存在"
        fi
        rm -f "$FRONTEND_PID_FILE"
        return 0
    fi

    if pkill -f "vite" 2>/dev/null; then
        ok "前端服务已停止 (通过进程名)"
    else
        warn "未发现运行中的前端进程"
    fi
}

frontend_status() {
    if [ -f "$FRONTEND_PID_FILE" ] && kill -0 "$(cat "$FRONTEND_PID_FILE")" 2>/dev/null; then
        local pid=$(cat "$FRONTEND_PID_FILE")
        local uptime=$(ps -o etime= -p "$pid" 2>/dev/null | xargs)
        echo -e "  前端: ${GREEN}运行中${NC} (PID: $pid, 已运行: $uptime)"
        echo -e "        端口: ${CYAN}5173${NC}"
        echo -e "        日志: ${CYAN}$LOG_DIR/frontend.log${NC}"
        return 0
    else
        local port_pid=$(get_pid_by_port 5173)
        if [ -n "$port_pid" ]; then
            local uptime=$(ps -o etime= -p "$port_pid" 2>/dev/null | xargs)
            echo -e "  前端: ${GREEN}运行中${NC} (PID: $port_pid, 已运行: $uptime, ${YELLOW}非脚本管理${NC})"
            echo -e "        端口: ${CYAN}5173${NC}"
            return 0
        fi
        echo -e "  前端: ${RED}未运行${NC}"
        return 1
    fi
}

# =============================================
# 主控制逻辑
# =============================================

usage() {
    echo "用法: $0 {start|stop|restart|status} [backend|frontend|all]"
    echo ""
    echo "  命令:"
    echo "    start    启动服务"
    echo "    stop     停止服务"
    echo "    restart  重启服务"
    echo "    status   查看服务状态"
    echo ""
    echo "  目标 (可选, 默认: all):"
    echo "    backend  仅操作后端"
    echo "    frontend 仅操作前端"
    echo "    all      操作前后端 (默认)"
    echo ""
    echo "  示例:"
    echo "    $0 start            启动所有服务"
    echo "    $0 start backend    仅启动后端"
    echo "    $0 stop frontend    仅停止前端"
    echo "    $0 restart all      重启所有服务"
    echo "    $0 status           查看所有服务状态"
}

CMD=${1:-}
TARGET=${2:-all}

case "$CMD" in
    start)
        echo ""
        echo "=============================="
        echo "  ZpAgent 启动"
        echo "=============================="
        case "$TARGET" in
            backend)
                backend_start
                ;;
            frontend)
                frontend_start
                ;;
            all)
                backend_start
                frontend_start
                echo ""
                echo "=============================="
                echo -e "  ${GREEN}ZpAgent 服务已全部启动${NC}"
                echo -e "  后端:  ${CYAN}http://localhost:8000${NC}"
                echo -e "  前端:  ${CYAN}http://localhost:5173${NC}"
                echo -e "  API:   ${CYAN}http://localhost:8000/docs${NC}"
                echo "=============================="
                ;;
            *)
                err "无效的目标: $TARGET (可选: backend, frontend, all)"
                exit 1
                ;;
        esac
        ;;
    stop)
        echo ""
        echo "=============================="
        echo "  ZpAgent 停止"
        echo "=============================="
        case "$TARGET" in
            backend)
                backend_stop
                ;;
            frontend)
                frontend_stop
                ;;
            all)
                frontend_stop
                backend_stop
                ok "ZpAgent 所有服务已停止"
                ;;
            *)
                err "无效的目标: $TARGET (可选: backend, frontend, all)"
                exit 1
                ;;
        esac
        ;;
    restart)
        case "$TARGET" in
            backend|frontend|all)
                echo ""
                echo "=============================="
                echo "  ZpAgent 重启 ($TARGET)"
                echo "=============================="
                $0 stop "$TARGET"
                sleep 1
                $0 start "$TARGET"
                ;;
            *)
                err "无效的目标: $TARGET (可选: backend, frontend, all)"
                exit 1
                ;;
        esac
        ;;
    status)
        echo ""
        echo "=============================="
        echo "  ZpAgent 服务状态"
        echo "=============================="
        if [ "$TARGET" = "all" ] || [ "$TARGET" = "backend" ]; then
            backend_status
        fi
        if [ "$TARGET" = "all" ] || [ "$TARGET" = "frontend" ]; then
            frontend_status
        fi
        echo ""
        # 额外的健康检查
        if [ "$TARGET" = "all" ] || [ "$TARGET" = "backend" ]; then
            backend_health
        fi
        echo "=============================="
        ;;
    *)
        usage
        exit 1
        ;;
esac
