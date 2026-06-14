# 大市唱转UTAU

**作者**: ciallo0721-cmd | **许可**: MIT

---

是的，我在网上莫名其妙地看见了这玩意。
于是就写下了这个**精彩**又**逆天**的 `dashichang-to-UTAU`。

把大市唱的项目文件转成 UTAU 能读的格式，就这么简单。


---

## 用法

```bash
python start.py
```

按提示输入 `.dsc` / `.ufdata` 文件路径，选输出格式（mid / ust / both），指定输出路径，完事。

## 支持格式

| 方向 | 格式 | 说明 |
|------|------|------|
| **输入** | `.dsc` | 大市唱工程文件（中文键名 JSON） |
| **输入** | `.ufdata` | 大市唱导出数据（英文键名 JSON） |
| **输出** | `.mid` | 标准 MIDI 文件（SMF Format 1, 480 TPQN，UTAU 兼容） |
| **输出** | `.ust` | UTAU 标准序列文本格式 |

## 依赖

- Python 3.6+
- 无第三方依赖（零 pip install）

## 技术说明

- DSC 文件使用中文键名的 JSON 格式存储音符数据，包含详细的音素参数
- UFDATA 文件使用英文键名的 JSON 格式，是大市唱的导出/交换格式
- MIDI 输出采用 SMF Format 1、480 TPQN，歌词通过 Meta Event `FF 05` 写入，与 UTAU 的 VSQ/MID 读取完全兼容
- UST 输出采用标准 UTAU 序列文本格式

## 已知限制

- DSC 多音轨工程的音符会按顺序拼接（大市唱一条声乐曲音轨对应一组音符，多条音轨不会并行处理）
- 音符之间的休止 gap 不会单独生成休止符

## 项目结构

```
dashichang-to-UTAU/
├── start.py          # CLI 入口
├── converter.py      # DSC / UFDATA 格式检测与解析
├── midi_writer.py    # UTAU 兼容 MIDI 生成
├── ust_writer.py     # UST 文件生成
└── README.md
```

---

<div align="center">

**这里是给搜索引擎看的**

# 大市唱转UTAU - Dashichang to UTAU Converter

大市唱（Dashichang）项目文件转UTAU格式工具。支持 .dsc .ufdata 输入，输出 .mid .ust 格式。
Python编写的命令行转换器，零第三方依赖，兼容UTAU歌声合成软件。
适用于大市唱导出工程转UTAU调教、中文虚拟歌手工程迁移、歌声合成格式转换。

关键词：大市唱、Dashichang、UTAU、歌声合成、虚拟歌手、DSC、UFDATA、MIDI、UST、
格式转换、Python、vocal synthesis、歌姬工程导入、调教工具、
大市唱导出MIDI、大市唱转UST、UTAU导入大市唱、大市唱工程转换、
歌声合成软件、虚拟歌姬、中文歌声合成、UTAU调教、VSQ、SMF、
大市唱DSC解析、大市唱UFDATA解析、音符转换、歌词转换

</div>
