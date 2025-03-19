#!/usr/bin/env python3
# ai-install - 智能软件包安装工具，适应不同操作系统和环境

import argparse
import subprocess
import os
import sys
import platform
import socket
import json
import shutil
import re
from pathlib import Path


__version__ = "0.1.0"


def detect_os():
    """detect the operating system"""
    system = platform.system().lower()
    
    if system == "linux":
        # check for specific linux distributions
        try:
            with open("/etc/os-release") as f:
                os_info = {}
                for line in f:
                    if "=" in line:
                        key, value = line.strip().split("=", 1)
                        os_info[key] = value.strip('"')
                
                if "ID" in os_info:
                    distro_id = os_info["ID"].lower()
                    if distro_id in ["ubuntu", "debian"]:
                        return "debian"
                    elif distro_id in ["rhel", "centos", "fedora"]:
                        return "rhel"
                    elif distro_id in ["alpine"]:
                        return "alpine"
                    elif distro_id in ["arch"]:
                        return "arch"
                    else:
                        return "linux_other"
        except FileNotFoundError:
            pass
        return "linux_other"
    elif system == "darwin":
        return "macos"
    elif system == "windows":
        return "windows"
    else:
        return "unknown"


def detect_environment():
    """detect if running in container, kubernetes, or host"""
    # check for kubernetes
    if os.path.exists("/var/run/secrets/kubernetes.io"):
        return "kubernetes"
    
    # check for docker/container
    container_indicators = [
        "/.dockerenv",
        "/run/.containerenv",
    ]
    
    for indicator in container_indicators:
        if os.path.exists(indicator):
            return "container"
    
    # check cgroup for container evidence
    try:
        with open("/proc/1/cgroup", "r") as f:
            if any(("docker" in line or "lxc" in line or "containerd" in line) for line in f):
                return "container"
    except FileNotFoundError:
        pass
    
    # if none of the above, assume host
    return "host"


def get_config_paths():
    """get paths where config files can be located"""
    return [
        # current directory
        os.path.join(os.getcwd(), "ai_install_config.json"),
        # user config directory
        os.path.expanduser("~/.config/ai-install/config.json"),
        # system config directory
        "/etc/ai-install/config.json"
    ]


def get_default_config():
    """get default configuration"""
    return {
        "package_managers": {
            "debian": {
                "command": "apt-get",
                "install_args": ["install", "-y"],
                "use_sudo": True
            },
            "rhel": {
                "command": "yum",
                "install_args": ["install", "-y"],
                "use_sudo": True
            },
            "alpine": {
                "command": "apk",
                "install_args": ["add"],
                "use_sudo": False
            },
            "arch": {
                "command": "pacman",
                "install_args": ["-S", "--noconfirm"],
                "use_sudo": True
            },
            "macos": {
                "command": "brew",
                "install_args": ["install"],
                "use_sudo": False
            },
            "windows": {
                "command": "choco",
                "install_args": ["install", "-y"],
                "use_sudo": False
            }
        },
        "environment_config": {
            "host": {
                "respect_sudo": True
            },
            "container": {
                "respect_sudo": False
            },
            "kubernetes": {
                "respect_sudo": False
            }
        },
        "package_aliases": {
            "python": {
                "debian": "python3",
                "rhel": "python3",
                "alpine": "python3",
                "arch": "python",
                "macos": "python"
            },
            "git": {
                "debian": "git",
                "rhel": "git",
                "alpine": "git",
                "arch": "git",
                "macos": "git"
            }
        },
        "default_options": {
            "debian": ["--no-install-recommends"],
            "rhel": [],
            "alpine": []
        },
        "bash_aliases": {
            "sai": "sudo apt install",
            "sau": "sudo apt update",
            "update": "sudo apt update",
            "ports": "sudo netstat -tulanp",
            "meminfo": "free -m -l -t",
            "psmem": "ps auxf | sort -nr -k 4",
            "pscpu": "ps auxf | sort -nr -k 3"
        }
    }


def load_config():
    """load the configuration from the config file or use defaults"""
    config_paths = get_config_paths()
    
    # check if any config file exists
    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"警告: 无法加载配置文件 {config_path}: {e}")
    
    # if no config file found, use defaults
    return get_default_config()


def get_package_manager_info(os_type, config):
    """get the package manager info for the OS from the config"""
    package_managers = config.get("package_managers", {})
    return package_managers.get(os_type, None)


def resolve_package_alias(package_name, os_type, config):
    """resolve package aliases if defined in config"""
    aliases = config.get("package_aliases", {})
    if package_name in aliases and os_type in aliases[package_name]:
        return aliases[package_name][os_type]
    return package_name


def get_default_options(os_type, config):
    """get default options for the OS from config"""
    default_options = config.get("default_options", {})
    return default_options.get(os_type, [])


def check_command_exists(command):
    """check if a command exists in the PATH"""
    return shutil.which(command) is not None


def install_package(package_name, os_type, env_type, user_options=None, config=None):
    """install a package using the appropriate package manager"""
    if config is None:
        config = load_config()
    
    # get package manager info
    pm_info = get_package_manager_info(os_type, config)
    
    if not pm_info:
        print(f"错误: 未支持的操作系统: {os_type}")
        return False
    
    # resolve package alias if any
    resolved_package = resolve_package_alias(package_name, os_type, config)
    
    # check if package manager is installed
    command = pm_info.get("command")
    if not check_command_exists(command):
        print(f"错误: 未找到包管理器 '{command}'。请先安装它。")
        return False
    
    # build command
    cmd = []
    
    # add sudo if required and environment respects sudo
    use_sudo = pm_info.get("use_sudo", False)
    env_config = config.get("environment_config", {}).get(env_type, {})
    respect_sudo = env_config.get("respect_sudo", True)
    
    if use_sudo and respect_sudo and check_command_exists("sudo"):
        cmd.append("sudo")
    
    # add command and install arguments
    cmd.append(command)
    cmd.extend(pm_info.get("install_args", []))
    
    # add default options for OS
    default_options = get_default_options(os_type, config)
    if default_options:
        cmd.extend(default_options)
    
    # add user options
    if user_options:
        cmd.extend(user_options)
    
    # add package name
    cmd.append(resolved_package)
    
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"安装失败: {e}")
        print(f"错误输出: {e.stderr}")
        return False
    except Exception as e:
        print(f"安装过程中出现错误: {e}")
        return False


def save_system_info(os_type, env_type):
    """save system information to a config file"""
    config_dir = os.path.expanduser("~/.config/ai-install")
    info_file = os.path.join(config_dir, "system_info.json")
    
    # create config directory if it doesn't exist
    os.makedirs(config_dir, exist_ok=True)
    
    info = {
        "os_type": os_type,
        "env_type": env_type,
        "last_updated": subprocess.check_output(["date", "+%Y-%m-%d %H:%M:%S"]).decode().strip()
    }
    
    try:
        with open(info_file, "w") as f:
            json.dump(info, f, indent=2)
    except Exception as e:
        print(f"无法保存系统信息: {e}")


def load_system_info():
    """load system information from config file"""
    info_file = os.path.expanduser("~/.config/ai-install/system_info.json")
    
    try:
        if os.path.exists(info_file):
            with open(info_file, "r") as f:
                return json.load(f)
    except Exception as e:
        print(f"无法加载系统信息: {e}")
    
    return None


def setup_config_file(config_path=None):
    """create default config in the specified path or in user config dir"""
    if not config_path:
        config_dir = os.path.expanduser("~/.config/ai-install")
        config_path = os.path.join(config_dir, "config.json")
        os.makedirs(config_dir, exist_ok=True)
    
    # don't overwrite existing config
    if os.path.exists(config_path):
        print(f"配置文件已存在: {config_path}")
        return False
    
    # get default config
    default_config = get_default_config()
    
    try:
        with open(config_path, "w") as f:
            json.dump(default_config, f, indent=2)
        print(f"创建了默认配置文件: {config_path}")
        return True
    except Exception as e:
        print(f"无法创建配置文件: {e}")
        return False


def edit_config(config_path=None, edit_action=None, edit_key=None, edit_value=None):
    """edit configuration file"""
    if not config_path:
        config_dir = os.path.expanduser("~/.config/ai-install")
        config_path = os.path.join(config_dir, "config.json")
        os.makedirs(config_dir, exist_ok=True)
    
    # load existing config or create new one
    if os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config = json.load(f)
        except Exception as e:
            print(f"无法加载配置文件 {config_path}: {e}")
            return False
    else:
        config = get_default_config()
    
    # perform edit action
    if edit_action == "add-alias":
        # format: python:debian=python3
        if not edit_key or ":" not in edit_key or "=" not in edit_value:
            print("错误: 格式应为 --edit-key package:os_type --edit-value alias_name")
            return False
        
        package, os_type = edit_key.split(":", 1)
        alias_value = edit_value
        
        if "package_aliases" not in config:
            config["package_aliases"] = {}
        
        if package not in config["package_aliases"]:
            config["package_aliases"][package] = {}
        
        config["package_aliases"][package][os_type] = alias_value
        print(f"已添加别名: {package} 在 {os_type} 上将安装为 {alias_value}")
    
    elif edit_action == "remove-alias":
        # format: python:debian
        if not edit_key or ":" not in edit_key:
            print("错误: 格式应为 --edit-key package:os_type")
            return False
        
        package, os_type = edit_key.split(":", 1)
        
        if "package_aliases" in config and package in config["package_aliases"] and os_type in config["package_aliases"][package]:
            del config["package_aliases"][package][os_type]
            if not config["package_aliases"][package]:
                del config["package_aliases"][package]
            print(f"已删除别名: {package} 在 {os_type} 上的别名")
        else:
            print(f"别名不存在: {package} 在 {os_type} 上没有定义别名")
            return False
    
    elif edit_action == "add-pm":
        # format: os_type
        if not edit_key or not edit_value:
            print("错误: 格式应为 --edit-key os_type --edit-value '{\"command\": \"apt-get\", \"install_args\": [\"install\", \"-y\"], \"use_sudo\": true}'")
            return False
        
        os_type = edit_key
        try:
            pm_info = json.loads(edit_value)
        except json.JSONDecodeError:
            print(f"错误: 包管理器信息必须是有效的JSON: {edit_value}")
            return False
        
        if "package_managers" not in config:
            config["package_managers"] = {}
        
        config["package_managers"][os_type] = pm_info
        print(f"已添加/更新包管理器: {os_type}")
    
    elif edit_action == "remove-pm":
        # format: os_type
        if not edit_key:
            print("错误: 格式应为 --edit-key os_type")
            return False
        
        os_type = edit_key
        
        if "package_managers" in config and os_type in config["package_managers"]:
            del config["package_managers"][os_type]
            print(f"已删除包管理器: {os_type}")
        else:
            print(f"包管理器不存在: {os_type}")
            return False
    
    elif edit_action == "add-bash-alias":
        # format: alias_name=command
        if not edit_key or not edit_value:
            print("错误: 格式应为 --edit-key alias_name --edit-value command")
            return False
        
        alias_name = edit_key
        alias_command = edit_value
        
        if "bash_aliases" not in config:
            config["bash_aliases"] = {}
        
        config["bash_aliases"][alias_name] = alias_command
        print(f"已添加bash别名: alias {alias_name}='{alias_command}'")
    
    elif edit_action == "remove-bash-alias":
        # format: alias_name
        if not edit_key:
            print("错误: 格式应为 --edit-key alias_name")
            return False
        
        alias_name = edit_key
        
        if "bash_aliases" in config and alias_name in config["bash_aliases"]:
            del config["bash_aliases"][alias_name]
            print(f"已删除bash别名: {alias_name}")
        else:
            print(f"bash别名不存在: {alias_name}")
            return False
    
    else:
        print(f"错误: 未知的编辑操作: {edit_action}")
        return False
    
    # save updated config
    try:
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)
        print(f"已更新配置文件: {config_path}")
        return True
    except Exception as e:
        print(f"无法保存配置文件: {e}")
        return False


def is_alias_in_bashrc(alias_name, bashrc_path):
    """检查别名是否已存在于bashrc文件中"""
    if not os.path.exists(bashrc_path):
        return False
    
    try:
        with open(bashrc_path, "r") as f:
            content = f.read()
            # 查找 "alias name="
            pattern = re.compile(r"alias\s+{}=".format(re.escape(alias_name)))
            return bool(pattern.search(content))
    except Exception as e:
        print(f"读取 {bashrc_path} 时出错: {e}")
        return False


def install_bash_aliases(aliases=None, bashrc_path=None, check_exists=True):
    """安装bash别名到.bashrc文件"""
    if aliases is None:
        config = load_config()
        aliases = config.get("bash_aliases", {})
    
    if not aliases:
        print("没有要安装的别名")
        return False
    
    if bashrc_path is None:
        bashrc_path = os.path.expanduser("~/.bashrc")
    
    # 检查.bashrc文件是否存在，如果不存在则创建
    if not os.path.exists(bashrc_path):
        try:
            with open(bashrc_path, "w") as f:
                f.write("# ~/.bashrc: 由 ai-install 创建\n\n")
        except Exception as e:
            print(f"无法创建 {bashrc_path}: {e}")
            return False
    
    # 准备要添加的别名列表
    aliases_to_add = {}
    
    # 如果需要检查已存在的别名
    if check_exists:
        for name, command in aliases.items():
            if not is_alias_in_bashrc(name, bashrc_path):
                aliases_to_add[name] = command
    else:
        aliases_to_add = aliases
    
    if not aliases_to_add:
        print("所有别名已存在，无需添加")
        return True
    
    # 添加别名到.bashrc
    try:
        with open(bashrc_path, "a") as f:
            f.write("\n# 由 ai-install 添加的别名\n")
            for name, command in aliases_to_add.items():
                f.write(f"alias {name}='{command}'\n")
            f.write("\n")
        
        print(f"已成功将以下别名添加到 {bashrc_path}:")
        for name, command in aliases_to_add.items():
            print(f"  alias {name}='{command}'")
        
        print("\n要立即启用这些别名，请运行:")
        print(f"  source {bashrc_path}")
        
        return True
    except Exception as e:
        print(f"无法将别名添加到 {bashrc_path}: {e}")
        return False


def list_bash_aliases(config=None):
    """列出配置中的bash别名"""
    if config is None:
        config = load_config()
    
    aliases = config.get("bash_aliases", {})
    
    if not aliases:
        print("当前配置中没有定义任何bash别名")
    else:
        print("已定义的bash别名:")
        for name, command in aliases.items():
            print(f"  alias {name}='{command}'")


def main():
    parser = argparse.ArgumentParser(description="AI-Install - 智能包安装工具 - 根据操作系统和环境自动适配安装方式")
    parser.add_argument("package", nargs="*", help="要安装的包名")
    parser.add_argument("--detect", action="store_true", help="仅检测系统类型和环境")
    parser.add_argument("--force-detect", action="store_true", help="强制重新检测系统，不使用缓存信息")
    parser.add_argument("--option", "-o", action="append", help="传递给包管理器的额外选项")
    parser.add_argument("--init-config", action="store_true", help="创建默认配置文件")
    parser.add_argument("--config", help="指定配置文件路径")
    parser.add_argument("--list-aliases", action="store_true", help="列出当前配置中的包别名")
    parser.add_argument("--list-package-managers", action="store_true", help="列出当前配置中的包管理器")
    parser.add_argument("--version", action="store_true", help="显示版本信息")
    
    # 配置编辑选项
    parser.add_argument("--edit-config", choices=["add-alias", "remove-alias", "add-pm", "remove-pm", "add-bash-alias", "remove-bash-alias"], 
                        help="编辑配置文件 (add-alias: 添加包别名, remove-alias: 删除包别名, add-pm: 添加包管理器, remove-pm: 删除包管理器, add-bash-alias: 添加bash别名, remove-bash-alias: 删除bash别名)")
    parser.add_argument("--edit-key", help="编辑操作的键 (add-alias: package:os_type, remove-alias: package:os_type, add-pm: os_type, remove-pm: os_type, add-bash-alias: alias_name, remove-bash-alias: alias_name)")
    parser.add_argument("--edit-value", help="编辑操作的值 (add-alias: alias_name, add-pm: 包管理器JSON配置, add-bash-alias: command)")
    
    # Bash别名管理
    parser.add_argument("--list-bash-aliases", action="store_true", help="列出当前配置中的bash别名")
    parser.add_argument("--install-bash-aliases", action="store_true", help="将配置中的bash别名安装到 ~/.bashrc")
    parser.add_argument("--bashrc", help="指定bashrc文件路径，默认为 ~/.bashrc")
    parser.add_argument("--force-install-aliases", action="store_true", help="强制安装别名，即使已存在")
    
    args = parser.parse_args()
    
    # 显示版本信息
    if args.version:
        print(f"ai-install 版本 {__version__}")
        return 0
    
    # 初始化配置文件
    if args.init_config:
        if setup_config_file(args.config):
            return 0
        else:
            return 1
    
    # 编辑配置
    if args.edit_config:
        if edit_config(args.config, args.edit_config, args.edit_key, args.edit_value):
            return 0
        else:
            return 1
    
    # 加载配置
    if args.config and os.path.exists(args.config):
        try:
            with open(args.config, "r") as f:
                config = json.load(f)
        except Exception as e:
            print(f"无法加载配置文件 {args.config}: {e}")
            return 1
    else:
        config = load_config()
    
    # 列出包别名
    if args.list_aliases:
        aliases = config.get("package_aliases", {})
        if not aliases:
            print("当前配置中没有定义任何包别名")
        else:
            print("已定义的包别名:")
            for package, os_aliases in aliases.items():
                print(f"- {package}:")
                for os_type, alias in os_aliases.items():
                    print(f"  - {os_type}: {alias}")
        return 0
    
    # 列出bash别名
    if args.list_bash_aliases:
        list_bash_aliases(config)
        return 0
    
    # 安装bash别名
    if args.install_bash_aliases:
        if install_bash_aliases(
            aliases=config.get("bash_aliases", {}), 
            bashrc_path=args.bashrc, 
            check_exists=not args.force_install_aliases
        ):
            return 0
        else:
            return 1
    
    # 列出包管理器
    if args.list_package_managers:
        package_managers = config.get("package_managers", {})
        if not package_managers:
            print("当前配置中没有定义任何包管理器")
        else:
            print("已定义的包管理器:")
            for os_type, pm_info in package_managers.items():
                print(f"- {os_type}:")
                for key, value in pm_info.items():
                    print(f"  - {key}: {value}")
        return 0
    
    # 处理仅检测模式
    if args.detect or args.force_detect:
        os_type = detect_os()
        env_type = detect_environment()
        
        print(f"操作系统类型: {os_type}")
        print(f"环境类型: {env_type}")
        
        pm_info = get_package_manager_info(os_type, config)
        if pm_info:
            print(f"包管理器: {pm_info.get('command')}")
        else:
            print(f"警告: 未找到支持的包管理器")
        
        # 检查包管理器是否存在
        if pm_info and not check_command_exists(pm_info.get("command")):
            print(f"警告: 包管理器 '{pm_info.get('command')}' 未安装")
        
        # 保存检测结果
        save_system_info(os_type, env_type)
        return 0
    
    # 无包名参数时显示帮助
    if not args.package:
        parser.print_help()
        return 1
    
    # 获取系统信息 (从缓存或重新检测)
    if args.force_detect:
        os_type = detect_os()
        env_type = detect_environment()
        save_system_info(os_type, env_type)
    else:
        # 尝试从配置加载，如果失败则重新检测
        system_info = load_system_info()
        if system_info:
            os_type = system_info.get("os_type")
            env_type = system_info.get("env_type")
        else:
            os_type = detect_os()
            env_type = detect_environment()
            save_system_info(os_type, env_type)
    
    print(f"当前环境: OS={os_type}, 环境={env_type}")
    
    # 安装所有指定的包
    success = True
    for package in args.package:
        print(f"正在安装 {package}...")
        if not install_package(package, os_type, env_type, args.option, config):
            success = False
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main()) 