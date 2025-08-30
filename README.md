# B站直播数据实时监控系统

一个用于监控B站直播间数据的实时系统，支持多房间同时监控，实时采集弹幕、礼物、人气等数据，并提供双Y轴可视化图表。

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
└── README.md
```

## 安装依赖

```bash
pip install bilibili-api matplotlib numpy asyncio
```

## 使用方法

1. 修改 `get_data_with_visualization.py` 中的房间ID列表
2. 运行主程序：
   ```bash
   python spider_live_data/get_data_with_visualization.py
   ```

## 数据格式

### JSON存储结构
- `room_info`: 房间基本信息
- `data`: 时序数据（人气、观看、点赞、累计弹幕/礼物）
- `real_time`: 实时状态数据
- `recent_danmaku`: 最近弹幕记录
- `recent_gifts`: 最近礼物记录

## 可视化特性

- **左图表**: 双Y轴显示累计弹幕数和礼物数
- **中间面板**: 实时状态信息
- **右侧面板**: 实时弹幕滚动显示

## 后续计划

- [ ] 集成Django Web界面
- [ ] 使用Redis缓存数据
- [ ] MySQL数据库存储
- [ ] ECharts图表展示
- [ ] 数据分析功能
- [ ] 直播间对比分析

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

MIT License