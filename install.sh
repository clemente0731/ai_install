#!/bin/bash
# 安装脚本 - 将 ai-install 安装到系统路径

set -e

# 确保脚本可执行
chmod +x ai_install.py

# 确定安装目录
DEFAULT_INSTALL_DIR="/usr/local/bin"
INSTALL_DIR=${1:-$DEFAULT_INSTALL_DIR}

# 创建配置目录
CONFIG_DIR="$HOME/.config/ai-install"
mkdir -p "$CONFIG_DIR"

# 检查目标是否存在
if [ ! -d "$INSTALL_DIR" ]; then
    echo "错误: 安装目录 '$INSTALL_DIR' 不存在"
    exit 1
fi

# 检查是否有写入权限
if [ ! -w "$INSTALL_DIR" ]; then
    echo "需要管理员权限来安装到 $INSTALL_DIR"
    echo "将使用 sudo 继续..."
    SUDO="sudo"
else
    SUDO=""
fi

# 复制可执行文件
$SUDO cp ai_install.py "$INSTALL_DIR/ai-install"
echo "已安装 ai-install 到 $INSTALL_DIR/ai-install"

# 初始化默认配置
python3 ai_install.py --init-config 2>/dev/null || true

echo "安装完成!"
echo ""
echo "使用方法:"
echo "  ai-install package_name      # 安装软件包"
echo "  ai-install --detect          # 检测系统信息"
echo "  ai-install --help            # 显示所有选项"
echo "" 