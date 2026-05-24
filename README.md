# 大市唱转UTAU - 作者:ciallo0721-cmd

---

是的,我在网上莫名其妙的看见了这坨大的 然后 我觉得有趣(沟槽)写下了这个**精彩**又**逆天**的"dashichang-to-UTAU"

---

# 用法

通过```python start.py```启动命令行 输入你.DSC的路径 然后输人输出的路径 就这么简单...

# 支持格式

- **输入**: `.dsc` (大市唱工程文件, 中文JSON格式) / `.ufdata` (大市唱导出数据, 英文JSON格式)
- **输出**: `.mid` (标准MIDI文件, UTAU兼容) / `.ust` (UTAU标准格式)

# 依赖

- Python 3.6+
- 无第三方依赖

# 技术说明

- DSC文件使用中文键名的JSON格式存储音符数据, 包含详细的音素参数
- UFDATA文件使用英文键名的JSON格式, 是大市唱的导出/交换格式
- MIDI输出采用SMF Format 1, 480 TPQN, 与UTAU的VSQ/MID读取兼容
- UST输出采用标准UTAU序列文本格式

---

# SEO

- **这里是给搜索引擎看的**

大市唱 UTAU 转换 Python
