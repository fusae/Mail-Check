#!/bin/bash

# Git + SSH 更新脚本
# 适用于使用Git管理代码的情况

# 颜色输出
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# 配置
SERVER_USER="${SERVER_USER:-your_username}"
SERVER_HOST="${SERVER_HOST:-your.server.com}"
SERVER_PATH="${SERVER_PATH:-/home/yourname/Mail_Check}"

echo -e "${BLUE}=================================="
echo "   Git 代码更新"
echo "==================================${NC}"
echo ""

# 检查是否在Git仓库中
if [ ! -d ".git" ]; then
    echo -e "${RED}错误: 当前目录不是Git仓库${NC}"
    echo "如果还没有初始化Git仓库，请先运行:"
    echo "  git init"
    echo "  git add ."
    echo "  git commit -m 'Initial commit'"
    exit 1
fi

# 检查是否有未提交的更改
if [ -n "$(git status --porcelain)" ]; then
    echo -e "${YELLOW}检测到未提交的更改${NC}"
    echo ""
    git status --short
    echo ""
    
    read -p "是否先提交这些更改? (y/n): " commit_choice
    if [ "$commit_choice" == "y" ] || [ "$commit_choice" == "Y" ]; then
        echo ""
        read -p "请输入提交信息: " commit_message
        git add .
        git commit -m "$commit_message"
        echo -e "${GREEN}✓ 提交完成${NC}"
    else
        echo -e "${YELLOW}跳过提交，仅更新已提交的代码${NC}"
    fi
    echo ""
fi

# 获取当前分支
CURRENT_BRANCH=$(git branch --show-current)
echo -e "${BLUE}当前分支: ${CURRENT_BRANCH}${NC}"
echo ""

# 推送到远程仓库
if git remote | grep -q "origin"; then
    echo -e "${BLUE}推送代码到远程仓库...${NC}"
    git push origin $CURRENT_BRANCH
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}✗ 推送失败${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}✓ 推送完成${NC}"
    echo ""
else
    echo -e "${YELLOW}未配置远程仓库${NC}"
    echo "跳过推送步骤"
    echo ""
fi

# 在服务器上更新
echo -e "${BLUE}在服务器上更新代码...${NC}"
echo ""

ssh ${SERVER_USER}@${SERVER_HOST} << EOF
cd ${SERVER_PATH}

echo "拉取最新代码..."
git pull origin ${CURRENT_BRANCH}

echo "检查是否需要更新依赖..."
if [ "requirements.txt" -nt "venv/.last_update" ]; then
    echo "检测到依赖更新，重新安装..."
    source venv/bin/activate
    pip install -r requirements.txt
    touch venv/.last_update
fi

echo ""
echo "重启服务..."
./stop.sh
sleep 2
./run.sh --daemon

echo ""
echo "服务状态:"
./status.sh
EOF

if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✓ 代码更新完成${NC}"
else
    echo ""
    echo -e "${RED}✗ 代码更新失败${NC}"
    exit 1
fi