#!/usr/bin/env python3
# ainstall - intelligent package installer that adapts to OS and environment

import argparse
import subprocess
import os
import sys
import platform
import socket
import json
import shutil
from pathlib import Path


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


def load_config():
    """load the configuration from the config file or use defaults"""
    config_paths = [
        # current directory
        os.path.join(os.getcwd(), "config.json"),
        # user config directory
        os.path.expanduser("~/.config/ainstall/config.json"),
        # system config directory
        "/etc/ainstall/config.json"
    ]
    
    # check if any config file exists
    for config_path in config_paths:
        if os.path.exists(config_path):
            try:
                with open(config_path, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"警告: 无法加载配置文件 {config_path}: {e}")
    
    # if no config file found, use defaults
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
        "package_aliases": {},
        "default_options": {}
    }


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
    config_dir = os.path.expanduser("~/.config/ainstall")
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
    info_file = os.path.expanduser("~/.config/ainstall/system_info.json")
    
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
        config_dir = os.path.expanduser("~/.config/ainstall")
        config_path = os.path.join(config_dir, "config.json")
        os.makedirs(config_dir, exist_ok=True)
    
    # don't overwrite existing config
    if os.path.exists(config_path):
        print(f"配置文件已存在: {config_path}")
        return False
    
    # get default config
    default_config = load_config()
    
    try:
        with open(config_path, "w") as f:
            json.dump(default_config, f, indent=2)
        print(f"创建了默认配置文件: {config_path}")
        return True
    except Exception as e:
        print(f"无法创建配置文件: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="智能包安装工具 - 根据操作系统和环境自动适配安装方式")
    parser.add_argument("package", nargs="*", help="要安装的包名")
    parser.add_argument("--detect", action="store_true", help="仅检测系统类型和环境")
    parser.add_argument("--force-detect", action="store_true", help="强制重新检测系统，不使用缓存信息")
    parser.add_argument("--option", "-o", action="append", help="传递给包管理器的额外选项")
    parser.add_argument("--init-config", action="store_true", help="创建默认配置文件")
    parser.add_argument("--config", help="指定配置文件路径")
    parser.add_argument("--list-aliases", action="store_true", help="列出当前配置中的包别名")
    parser.add_argument("--version", action="store_true", help="显示版本信息")
    
    args = parser.parse_args()
    
    # 显示版本信息
    if args.version:
        print("ainstall 版本 1.0.0")
        return 0
    
    # 初始化配置文件
    if args.init_config:
        if setup_config_file(args.config):
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