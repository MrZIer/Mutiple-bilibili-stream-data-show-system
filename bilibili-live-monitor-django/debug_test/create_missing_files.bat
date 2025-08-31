@echo off
echo 🔧 创建缺失的Django管理命令文件结构...

echo 1. 创建 live_data/management/ 目录...
if not exist live_data\management mkdir live_data\management

echo 2. 创建 live_data/management/commands/ 目录...
if not exist live_data\management\commands mkdir live_data\management\commands

echo 3. 创建 live_data/management/__init__.py...
echo. > live_data\management\__init__.py

echo 4. 创建 live_data/management/commands/__init__.py...
echo. > live_data\management\commands\__init__.py

echo 5. 创建 utils/ 目录（如果不存在）...
if not exist utils mkdir utils
echo. > utils\__init__.py

echo 6. 验证文件结构...
echo 📁 检查创建的文件:
if exist live_data\management\__init__.py (
    echo ✅ live_data\management\__init__.py
) else (
    echo ❌ live_data\management\__init__.py
)

if exist live_data\management\commands\__init__.py (
    echo ✅ live_data\management\commands\__init__.py
) else (
    echo ❌ live_data\management\commands\__init__.py
)

if exist utils\__init__.py (
    echo ✅ utils\__init__.py
) else (
    echo ❌ utils\__init__.py
)

echo 7. 检查管理命令文件是否存在...
if exist live_data\management\commands\sync_redis_to_db.py (
    echo ✅ sync_redis_to_db.py 存在
) else (
    echo ❌ sync_redis_to_db.py 不存在，需要创建
)

if exist live_data\management\commands\start_sync_scheduler.py (
    echo ✅ start_sync_scheduler.py 存在
) else (
    echo ❌ start_sync_scheduler.py 不存在，需要创建
)

if exist live_data\management\commands\check_redis_keys.py (
    echo ✅ check_redis_keys.py 存在
) else (
    echo ❌ check_redis_keys.py 不存在，需要创建
)

echo.
echo ✅ 文件结构创建完成！
echo 💡 接下来请运行: python debug_sync_issues.py 重新检查
pause