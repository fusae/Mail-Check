#!/bin/bash

echo "=================================="
echo "   快速系统检查"
echo "=================================="
echo ""

# 确保在项目根目录
cd "$(dirname "$0")"

# 1. 检查文件
echo "1. 检查关键文件..."
files_ok=true

if [ -f "config/config.yaml" ]; then
    echo "   ✓ config.yaml"
else
    echo "   ✗ config.yaml 不存在"
    files_ok=false
fi

if [ -f "src/main.py" ]; then
    echo "   ✓ src/main.py"
else
    echo "   ✗ src/main.py 不存在"
    files_ok=false
fi

if [ -d "venv" ]; then
    echo "   ✓ venv/ 目录"
else
    echo "   ✗ venv 不存在"
    files_ok=false
fi

echo ""

# 2. 测试导入
echo "2. 测试Python模块..."
source venv/bin/activate

if python3 -c "import sys; sys.path.insert(0, 'src'); import main" 2>/dev/null; then
    echo "   ✓ main模块可导入"
else
    echo "   ✗ main模块导入失败"
    files_ok=false
fi

echo ""

# 3. 检查数据库
echo "3. 检查数据库目录..."
if [ -d "data" ]; then
    echo "   ✓ data/ 目录"
else
    mkdir -p data
    echo "   ✓ data/ 目录（已创建）"
fi

echo ""
echo "=================================="
if [ "$files_ok" = true ]; then
    echo "   ✓ 系统就绪！可以运行"
    echo "   运行命令: ./run.sh"
else
    echo "   ✗ 系统未就绪，请检查错误"
fi
echo "=================================="
