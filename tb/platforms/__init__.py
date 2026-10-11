"""平台注册表：名字 -> 命令行模块（用到才导入）。新增平台只在这里加一行。"""
PLATFORMS = {   # 顺序就是 tb modules 列表里的顺序
    "sycm": "tb.platforms.sycm.cli",
    "alimama": "tb.platforms.alimama.cli",
    "dmp": "tb.platforms.dmp.cli",
    "qianniu": "tb.platforms.qianniu.cli",
    "1688": "tb.platforms.alibaba.cli",
    "voc": "tb.platforms.voc.cli",
}

# 一个命令行下面可以有几套接口，各是一个 Platform：除了 <模块>/platform.py 里那个，还有这些（插件放行规则、打包都要算上）
EXTRA_PLATFORMS = {
    "1688": ("tb.platforms.alisycm",),   # 1688 生意参谋（sycm.1688.com），命令挂在 tb 1688 下面
}
