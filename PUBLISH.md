# 发布到 PyPI 的步骤

本文档描述了如何将 ai-install 发布到 PyPI（Python Package Index），使其能够通过 pip 安装。

## 准备工作

1. 确保你有 PyPI 帐户。如果没有，请在 [PyPI](https://pypi.org/account/register/) 上注册。

2. 安装必要的工具：

```bash
pip install setuptools wheel twine
```

## 构建分发包

1. 确保你位于项目根目录下：

```bash
cd /path/to/ai-install
```

2. 构建分发包：

```bash
python setup.py sdist bdist_wheel
```

这将在 `dist/` 目录下创建源代码分发包（.tar.gz）和轮子（.whl）。

## 上传到 TestPyPI（推荐先测试）

在上传到正式 PyPI 之前，建议先上传到 TestPyPI 进行测试：

```bash
twine upload --repository-url https://test.pypi.org/legacy/ dist/*
```

然后你可以通过以下命令测试安装：

```bash
pip install --index-url https://test.pypi.org/simple/ ai-install
```

## 上传到 PyPI

当你确认一切正常后，可以上传到正式的 PyPI：

```bash
twine upload dist/*
```

## 版本更新

1. 修改 `ai_install.py` 文件中的 `__version__` 变量。
2. 重新构建分发包并上传：

```bash
rm -rf dist/
python setup.py sdist bdist_wheel
twine upload dist/*
```

## 清理

上传完成后，可以清理生成的分发文件：

```bash
rm -rf build/ dist/ *.egg-info/
``` 