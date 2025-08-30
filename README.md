# B站直播数据实时监控系统

一个用于监控B站直播间数据的实时系统，支持多房间同时监控，实时采集弹幕、礼物、人气等数据，并提供双Y轴可视化图表。

[English Documentation](README_EN.md) | 中文文档

## 功能特点

- 🎯 **多房间监控**：同时监控多个直播间
- 💬 **实时弹幕采集**：实时获取弹幕内容和用户信息
- 🎁 **礼物数据统计**：统计礼物数量和价值
- 📊 **双Y轴可视化**：独立显示弹幕和礼物数据趋势
- 💾 **JSON数据存储**：结构化存储所有采集数据
- ⚡ **实时更新**：1秒间隔更新图表和数据

## 项目结构

```
bilibili_data/
├── spider_live_data/
│   ├── live_data_visualizer.py    # 数据可视化模块
│   ├── data_storage.py            # 数据存储模块
│   ├── get_data_with_visualization.py  # 主程序入口
│   └── data/                      # 数据存储目录
├── live_data/                     # 历史数据文件
├── README.md                      # 中文文档
├── README_EN.md                   # 英文文档
└── requirements.txt               # 依赖列表
```

## 安装依赖

```bash
pip install -r requirements.txt
```

或手动安装：
```bash
pip install bilibili-api matplotlib numpy asyncio
```

## 使用方法

1. **配置房间ID**
   
   修改 `get_data_with_visualization.py` 中的房间ID列表：
   ```python
   room_ids = [6, 7720242]  # 替换为你要监控的房间ID
   ```

2. **运行程序**
   ```bash
   cd spider_live_data
   python get_data_with_visualization.py
   ```

3. **查看结果**
   - 实时可视化窗口会自动打开
   - 数据文件保存在 `data/` 目录，格式为JSON

## 数据格式

### JSON存储结构
```json
{
  "room_info": {
    "room_id": 6,
    "uname": "主播名称",
    "title": "直播标题",
    "created_at": "2025-08-30T18:59:39.598094"
  },
  "data": {
    "timestamps": ["2025-08-30T19:05:59.307459"],
    "popularity": [9999],
    "watched": [181948010],
    "likes": [275274],
    "total_danmaku_at_time": [346],
    "total_gifts_at_time": [0]
  },
  "real_time": {
    "current_popularity": 9999,
    "current_watched": 181948010,
    "current_likes": 275274,
    "total_danmaku": 346,
    "total_gifts": 0,
    "last_update": "2025-08-30T19:06:01.469806"
  },
  "recent_danmaku": [...],
  "recent_gifts": [...]
}
```

### 字段说明
- **room_info**: 房间基本信息
- **data**: 时序数据（人气、观看、点赞、累计弹幕/礼物）
- **real_time**: 实时状态数据
- **recent_danmaku**: 最近弹幕记录（最新100条）
- **recent_gifts**: 最近礼物记录（最新50条）

## 可视化特性

### 界面布局
- **左图表**: 双Y轴显示累计弹幕数和礼物数
  - 蓝色线条（左Y轴）：累计弹幕数
  - 绿色线条（右Y轴）：累计礼物数
- **中间面板**: 实时状态信息
- **右侧面板**: 实时弹幕滚动显示

### 核心特性
- **独立刻度**: 每个Y轴独立缩放，优化数据显示
- **实时更新**: 1秒刷新频率
- **数据持久化**: 所有数据保存到JSON文件
- **多房间支持**: 同时监控多个直播间

## 后续计划

- [ ] **Django Web界面**: 基于Web的远程监控仪表板
- [ ] **Redis缓存**: 高性能数据缓存层
- [ ] **MySQL数据库**: 持久化数据库存储
- [ ] **ECharts集成**: 高级交互式图表库
- [ ] **数据分析功能**: 统计分析和报告工具
- [ ] **直播间对比**: 多个直播间的并排比较
- [ ] **告警系统**: 重要事件或里程碑通知
- [ ] **导出功能**: 多种格式的数据导出

## 贡献指南

欢迎提交Issue和Pull Request！

### 开发规范
- 遵循PEP 8代码风格
- 为复杂逻辑添加注释
- 包含外部API调用的错误处理
- 提交前使用多个房间ID测试

## 许可证

MIT License - 详见 [LICENSE](LICENSE) 文件

## 致谢

- [bilibili-api](https://github.com/Nemo2011/bilibili-api) - B站API的Python库
- [matplotlib](https://matplotlib.org/) - Python绘图库
- [numpy](https://numpy.org/) - 数值计算库

## 免责声明

本项目仅用于教育和研究目的。使用时请遵守B站的服务条款和频率限制。作者不对软件的误用承担责任。

---

**注意**: 本系统仅监控公开的直播数据，不收集或存储任何私人或敏感信息。